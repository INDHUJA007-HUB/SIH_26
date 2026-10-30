terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ---------------------------------------------------------------------------
# ECS Cluster
# ---------------------------------------------------------------------------

resource "aws_ecs_cluster" "main" {
  name = "${var.environment}-aicte-workbench"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(var.tags, {
    Name        = "${var.environment}-ecs-cluster"
    Environment = var.environment
  })
}

# ---------------------------------------------------------------------------
# Security Groups for ECS Services across Trust Zones
# ---------------------------------------------------------------------------

# Public Edge Application Load Balancer SG
resource "aws_security_group" "alb" {
  name        = "${var.environment}-alb-sg"
  description = "Ingress for public application load balancer"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTPS from edge"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Forward to API containers"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = merge(var.tags, {
    Zone = "public_edge"
  })
}

# Application Zone SG (API, Evidence Delivery, Outbox Relay)
resource "aws_security_group" "app_tasks" {
  name        = "${var.environment}-app-tasks-sg"
  description = "Application zone tasks (API, Delivery, Relay)"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Inbound from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Egress to VPC endpoints and DB"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = merge(var.tags, {
    Zone = "application_zone"
  })
}

# Untrusted Processing Zone SG (Scan, Document, Media)
# NO outbound internet access; traffic restricted strictly to VPC endpoints (S3, Logs)
resource "aws_security_group" "untrusted_workers" {
  name        = "${var.environment}-untrusted-workers-sg"
  description = "Isolated processing tasks with zero internet egress"
  vpc_id      = var.vpc_id

  egress {
    description = "TLS only to VPC endpoints within VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = merge(var.tags, {
    Zone = "untrusted_processing_zone"
  })
}

# Integration Zone SG (Connector Workers)
# Allowed HTTPS outbound through NAT to statutory domains only
resource "aws_security_group" "connector_workers" {
  name        = "${var.environment}-connector-workers-sg"
  description = "Connector tasks with egress to allowlisted statutory services"
  vpc_id      = var.vpc_id

  egress {
    description = "HTTPS to statutory external endpoints"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Zone = "integration_zone"
  })
}

# ---------------------------------------------------------------------------
# IAM Roles across the 6 Trust Zones
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Task Execution Role (Pulls images from ECR, sends logs to CloudWatch)
resource "aws_iam_role" "task_execution" {
  name               = "${var.environment}-ecs-task-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# 1. Application Zone Task Role (API & Evidence Delivery)
resource "aws_iam_role" "app_role" {
  name               = "${var.environment}-application-zone-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = merge(var.tags, {
    Zone = "application_zone"
  })
}

resource "aws_iam_role_policy" "app_policy" {
  name = "${var.environment}-app-policy"
  role = aws_iam_role.app_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3EvidenceAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.quarantine_bucket_arn,
          "${var.quarantine_bucket_arn}/*",
          var.clean_bucket_arn,
          "${var.clean_bucket_arn}/*",
          var.reports_bucket_arn,
          "${var.reports_bucket_arn}/*"
        ]
      },
      {
        Sid    = "KMSDecryptAppKey"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = [var.app_kms_key_arn]
      },
      {
        Sid    = "ReadAppSecrets"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          var.db_credentials_secret_arn
        ]
      }
    ]
  })
}

# 2. Untrusted Processing Zone Task Role (Scan, Document, Media Workers)
# CRITICAL RESTRICTION: No access to provider secrets, no rule publication, no audit bucket
resource "aws_iam_role" "untrusted_role" {
  name               = "${var.environment}-untrusted-processing-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = merge(var.tags, {
    Zone = "untrusted_processing_zone"
  })
}

resource "aws_iam_role_policy" "untrusted_policy" {
  name = "${var.environment}-untrusted-policy"
  role = aws_iam_role.untrusted_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3QuarantineAndDerivativesOnly"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          "${var.quarantine_bucket_arn}/*",
          "${var.clean_bucket_arn}/*",
          "${var.derivatives_bucket_arn}/*"
        ]
      },
      {
        Sid    = "KMSAppKeyDecryptOnly"
        Effect = "Allow"
        Action = ["kms:Decrypt"]
        Resource = [var.app_kms_key_arn]
      },
      {
        Sid       = "ExplicitDenyAuditAndProviderSecrets"
        Effect    = "Deny"
        Action    = [
          "s3:PutBucketObjectLockConfiguration",
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          var.audit_vault_bucket_arn,
          "${var.audit_vault_bucket_arn}/*",
          var.provider_credentials_secret_arn
        ]
      }
    ]
  })
}

# 3. Integration Zone Task Role (Connector Workers)
resource "aws_iam_role" "connector_role" {
  name               = "${var.environment}-integration-connector-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = merge(var.tags, {
    Zone = "integration_zone"
  })
}

resource "aws_iam_role_policy" "connector_policy" {
  name = "${var.environment}-connector-policy"
  role = aws_iam_role.connector_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadProviderSecretsOnly"
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [var.provider_credentials_secret_arn]
      },
      {
        Sid      = "KMSDecryptAppKey"
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = [var.app_kms_key_arn]
      }
    ]
  })
}

# 4. Audit & Recovery Zone Task Role (Audit Worker)
# Holds exclusive rights to write signed checkpoints to the audit vault
resource "aws_iam_role" "audit_role" {
  name               = "${var.environment}-audit-recovery-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json

  tags = merge(var.tags, {
    Zone = "audit_and_recovery_zone"
  })
}

resource "aws_iam_role_policy" "audit_policy" {
  name = "${var.environment}-audit-policy"
  role = aws_iam_role.audit_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AuditVaultAccess"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.audit_vault_bucket_arn,
          "${var.audit_vault_bucket_arn}/*"
        ]
      },
      {
        Sid    = "KMSAuditKeyEncrypt"
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = [var.audit_kms_key_arn]
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# ECS Fargate Task Definitions for Section 3.2 Deployment Units
# ---------------------------------------------------------------------------

locals {
  deployment_units = {
    api = {
      cpu    = 2048,
      memory = 4096,
      role   = aws_iam_role.app_role.arn,
      port   = 8000
    },
    evidence_delivery = {
      cpu    = 1024,
      memory = 2048,
      role   = aws_iam_role.app_role.arn,
      port   = 8001
    },
    outbox_relay = {
      cpu    = 512,
      memory = 1024,
      role   = aws_iam_role.app_role.arn,
      port   = 0
    },
    workflow_worker = {
      cpu    = 2048,
      memory = 4096,
      role   = aws_iam_role.app_role.arn,
      port   = 0
    },
    scan_worker = {
      cpu    = 1024,
      memory = 2048,
      role   = aws_iam_role.untrusted_role.arn,
      port   = 0
    },
    document_worker = {
      cpu    = 2048,
      memory = 4096,
      role   = aws_iam_role.untrusted_role.arn,
      port   = 0
    },
    connector_worker = {
      cpu    = 1024,
      memory = 2048,
      role   = aws_iam_role.connector_role.arn,
      port   = 0
    },
    evaluation_worker = {
      cpu    = 2048,
      memory = 4096,
      role   = aws_iam_role.app_role.arn,
      port   = 0
    },
    media_worker = {
      cpu    = 2048,
      memory = 4096,
      role   = aws_iam_role.untrusted_role.arn,
      port   = 0
    },
    report_worker = {
      cpu    = 1024,
      memory = 2048,
      role   = aws_iam_role.app_role.arn,
      port   = 0
    },
    audit_worker = {
      cpu    = 1024,
      memory = 2048,
      role   = aws_iam_role.audit_role.arn,
      port   = 0
    }
  }
}

resource "aws_ecs_task_definition" "tasks" {
  for_each                 = local.deployment_units
  family                   = "${var.environment}-aicte-${replace(each.key, "_", "-")}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = tostring(each.value.cpu)
  memory                   = tostring(each.value.memory)
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = each.value.role

  container_definitions = jsonencode([
    {
      name      = replace(each.key, "_", "-")
      image     = lookup(var.unit_images, each.key, "${var.image_repository}:${var.image_tag}")
      command   = lookup(merge(local.unit_commands, var.unit_commands), each.key, ["python", "-c", "raise SystemExit('Configure an approved worker entry point')"])
      secrets   = [for name, arn in var.runtime_secrets : { name = name, valueFrom = arn }]
      essential = true
      portMappings = each.value.port > 0 ? [
        {
          containerPort = each.value.port
          hostPort      = each.value.port
          protocol      = "tcp"
        }
      ] : []
      environment = concat([
        { name = "WB_ENVIRONMENT", value = var.environment },
        { name = "UNIT_NAME", value = each.key },
        { name = "WB_OTLP_ENDPOINT", value = var.otel_endpoint }
      ], [for name, value in var.runtime_environment : { name = name, value = value }])
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.environment}/aicte-${replace(each.key, "_", "-")}"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = merge(var.tags, {
    Unit = each.key
  })
}


locals {
  unit_commands = {
    api               = ["uvicorn", "workbench.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
    evidence_delivery = ["uvicorn", "workbench.api.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"]
    outbox_relay      = ["python", "-m", "workbench.platform.outbox"]
    workflow_worker   = ["python", "-m", "workbench.processing.lifecycle_worker"]
    scan_worker       = ["python", "-m", "workbench.processing.scan_worker"]
    media_worker      = ["python", "-m", "workbench.processing.media_worker"]
  }
}

resource "aws_cloudwatch_log_group" "units" {
  for_each          = local.deployment_units
  name              = "/ecs/${var.environment}/aicte-${replace(each.key, "_", "-")}"
  retention_in_days = 90
  tags              = var.tags
}

resource "aws_ecs_service" "units" {
  for_each        = var.enabled_units
  name            = "${var.environment}-${replace(each.key, "_", "-")}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.tasks[each.key].arn
  desired_count   = 1
  launch_type     = "FARGATE"
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = var.private_subnet_ids
    assign_public_ip = false
    security_groups  = [aws_security_group.app_tasks.id]
  }
  lifecycle {
    precondition {
      condition     = length(var.private_subnet_ids) > 0 && contains(keys(merge(local.unit_commands, var.unit_commands)), each.key)
      error_message = "Enabled units need private subnets and an explicit supported command."
    }
    precondition {
      condition     = contains(keys(var.runtime_environment), "WB_TEMPORAL_ADDRESS") && contains(keys(var.runtime_environment), "WB_AUTH_MODE")
      error_message = "Supply real runtime endpoints and authentication configuration before enabling services."
    }
  }
  dynamic "load_balancer" {
    for_each = each.key == "api" ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.api[0].arn
      container_name   = "api"
      container_port   = 8000
    }
  }
  depends_on = [aws_cloudwatch_log_group.units, aws_lb_listener.https]
}

resource "aws_lb" "api" {
  count              = contains(var.enabled_units, "api") ? 1 : 0
  name               = "${var.environment}-workbench"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids
  drop_invalid_header_fields = true
  lifecycle {
    precondition {
      condition     = length(var.public_subnet_ids) >= 2 && var.tls_certificate_arn != ""
      error_message = "API deployment requires public subnets in two AZs and an approved TLS certificate."
    }
  }
}
resource "aws_lb_target_group" "api" {
  count       = contains(var.enabled_units, "api") ? 1 : 0
  name        = "${var.environment}-workbench-api"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
  health_check {
    path    = "/health/live"
    matcher = "200"
  }
}
resource "aws_lb_listener" "https" {
  count             = contains(var.enabled_units, "api") ? 1 : 0
  load_balancer_arn  = aws_lb.api[0].arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.tls_certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api[0].arn
  }
}
resource "aws_iam_role_policy" "runtime_secret_injection" {
  count = length(var.runtime_secrets) > 0 ? 1 : 0
  role  = aws_iam_role.task_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = values(var.runtime_secrets)}]
  })
}
