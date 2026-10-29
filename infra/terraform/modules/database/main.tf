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
# Database Subnet Group & Security Group
# ---------------------------------------------------------------------------

resource "aws_db_subnet_group" "db" {
  name       = "${var.environment}-db-subnet-group"
  subnet_ids = var.database_subnet_ids

  tags = merge(var.tags, {
    Name = "${var.environment}-db-subnet-group"
  })
}

resource "aws_security_group" "db" {
  name        = "${var.environment}-rds-postgres-sg"
  description = "Access to domain and temporal PostgreSQL from private application tasks"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from Application Tasks"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.app_security_group_ids
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.environment}-rds-postgres-sg"
  })
}

# ---------------------------------------------------------------------------
# RDS Parameter Group (Enforce TLS and Row Level Security logging)
# ---------------------------------------------------------------------------

resource "aws_db_parameter_group" "postgres16" {
  name   = "${var.environment}-postgres16-params"
  family = "postgres16"

  parameter {
    name  = "rds.force_ssl"
    value = "1" # Force SSL/TLS encrypted connections
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_line_prefix"
    value = "%m [%p] %q%u@%d "
  }
}

# ---------------------------------------------------------------------------
# 1. Domain PostgreSQL RDS Instance (Multi-AZ for Pilot / Production)
# ---------------------------------------------------------------------------

resource "aws_db_instance" "domain" {
  identifier                  = "${var.environment}-aicte-domain-db"
  engine                      = "postgres"
  engine_version              = "16.4"
  instance_class              = var.instance_class
  allocated_storage           = var.allocated_storage
  max_allocated_storage       = var.max_allocated_storage
  storage_type                = "gp3"
  storage_encrypted           = true
  kms_key_id                  = var.kms_key_arn
  multi_az                    = var.multi_az
  publicly_accessible         = false
  db_subnet_group_name        = aws_db_subnet_group.db.name
  vpc_security_group_ids      = [aws_security_group.db.id]
  parameter_group_name        = aws_db_parameter_group.postgres16.name
  auto_minor_version_upgrade  = true
  allow_major_version_upgrade = false
  backup_retention_period     = var.backup_retention_days
  backup_window               = "02:00-03:00"
  maintenance_window          = "Sun:04:00-Sun:05:00"
  deletion_protection         = var.environment == "production"
  skip_final_snapshot         = var.environment != "production"
  final_snapshot_identifier   = "${var.environment}-aicte-domain-db-final"

  db_name  = "workbench"
  username = "wb_admin" # Administrative owner role (used ONLY for Alembic migrations)
  manage_master_user_password = true

  tags = merge(var.tags, {
    Name        = "${var.environment}-aicte-domain-db"
    Role        = "domain_database"
    Environment = var.environment
  })
}

# ---------------------------------------------------------------------------
# 2. Temporal Workflow Persistence RDS Instance (Separate from Domain)
# ---------------------------------------------------------------------------

resource "aws_db_instance" "temporal" {
  identifier                  = "${var.environment}-aicte-temporal-db"
  engine                      = "postgres"
  engine_version              = "16.4"
  instance_class              = var.temporal_instance_class
  allocated_storage           = var.allocated_storage
  max_allocated_storage       = var.max_allocated_storage
  storage_type                = "gp3"
  storage_encrypted           = true
  kms_key_id                  = var.kms_key_arn
  multi_az                    = var.multi_az
  publicly_accessible         = false
  db_subnet_group_name        = aws_db_subnet_group.db.name
  vpc_security_group_ids      = [aws_security_group.db.id]
  parameter_group_name        = aws_db_parameter_group.postgres16.name
  auto_minor_version_upgrade  = true
  allow_major_version_upgrade = false
  backup_retention_period     = var.backup_retention_days
  backup_window               = "03:00-04:00"
  maintenance_window          = "Sun:05:00-Sun:06:00"
  deletion_protection         = var.environment == "production"
  skip_final_snapshot         = var.environment != "production"
  final_snapshot_identifier   = "${var.environment}-aicte-temporal-db-final"

  db_name  = "temporal"
  username = "temporal_admin"
  manage_master_user_password = true

  tags = merge(var.tags, {
    Name        = "${var.environment}-aicte-temporal-db"
    Role        = "temporal_persistence"
    Environment = var.environment
  })
}
