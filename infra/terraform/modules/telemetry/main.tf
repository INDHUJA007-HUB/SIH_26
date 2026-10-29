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
# Amazon ECR Repository with Immutable Image Tags & Scan on Push
# ---------------------------------------------------------------------------

resource "aws_ecr_repository" "app" {
  name                 = "${var.environment}-aicte-workbench"
  image_tag_mutability = "IMMUTABLE" # Enforces immutable release digests

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = var.kms_key_arn
  }

  tags = merge(var.tags, {
    Name        = "${var.environment}-ecr-repo"
    Environment = var.environment
  })
}

# ECR Lifecycle Policy (Keep last 30 release images for rollback rehearsal)
resource "aws_ecr_lifecycle_policy" "retention" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Retain last 30 releases for rollback safety"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 30
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# CloudWatch Log Groups for Runtime Deployment Units
# ---------------------------------------------------------------------------

locals {
  units = [
    "api",
    "evidence-delivery",
    "outbox-relay",
    "workflow-worker",
    "scan-worker",
    "document-worker",
    "connector-worker",
    "evaluation-worker",
    "media-worker",
    "report-worker",
    "audit-worker"
  ]
}

resource "aws_cloudwatch_log_group" "units" {
  for_each          = toset(local.units)
  name              = "/ecs/${var.environment}/aicte-${each.key}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_arn

  tags = merge(var.tags, {
    Unit        = each.key
    Environment = var.environment
  })
}

# ---------------------------------------------------------------------------
# CloudWatch Alarms for Service Objectives (Section 12.2)
# ---------------------------------------------------------------------------

# 1. API High 5xx Error Rate Alarm
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.environment}-api-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "API 5xx errors exceed acceptable threshold"

  tags = var.tags
}

# 2. Audit Checkpoint Lag Alarm (Section 12.2: proposed max 15 minutes)
resource "aws_cloudwatch_metric_alarm" "audit_lag" {
  alarm_name          = "${var.environment}-audit-checkpoint-lag"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "AuditCheckpointLagMinutes"
  namespace           = "AICTE/Workbench"
  period              = 300
  statistic           = "Maximum"
  threshold           = 15
  alarm_description   = "Audit checkpoint lag exceeds 15 minutes target"

  tags = var.tags
}

# 3. Outbox Oldest Undelivered Event Age
resource "aws_cloudwatch_metric_alarm" "outbox_age" {
  alarm_name          = "${var.environment}-outbox-backlog-age"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "OldestUndeliveredEventSeconds"
  namespace           = "AICTE/Workbench"
  period              = 60
  statistic           = "Maximum"
  threshold           = 300 # 5 minutes
  alarm_description   = "Committed outbox events are stalling before relay processing"

  tags = var.tags
}
