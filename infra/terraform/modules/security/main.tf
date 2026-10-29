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
# AWS KMS Customer Managed Keys (Separate App vs Audit Administration)
# ---------------------------------------------------------------------------

# Application CMK (Evidence, Reports, RDS, Secrets)
resource "aws_kms_key" "app" {
  description             = "${var.environment} AICTE Workbench Application Key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(var.tags, {
    Name        = "${var.environment}-app-kms-key"
    Zone        = "application_zone"
    Environment = var.environment
  })
}

resource "aws_kms_alias" "app" {
  name          = "alias/${var.environment}-aicte-app"
  target_key_id = aws_kms_key.app.key_id
}

# Audit & Recovery Zone CMK (Separate key administration, legal hold protection)
resource "aws_kms_key" "audit" {
  description             = "${var.environment} AICTE Workbench Independent Audit Vault Key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = merge(var.tags, {
    Name        = "${var.environment}-audit-kms-key"
    Zone        = "audit_and_recovery_zone"
    Environment = var.environment
  })
}

resource "aws_kms_alias" "audit" {
  name          = "alias/${var.environment}-aicte-audit"
  target_key_id = aws_kms_key.audit.key_id
}

# ---------------------------------------------------------------------------
# AWS Secrets Manager
# ---------------------------------------------------------------------------

# Domain Database Credentials
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${var.environment}/aicte/database/credentials"
  kms_key_id              = aws_kms_key.app.arn
  recovery_window_in_days = var.environment == "production" ? 30 : 0

  tags = merge(var.tags, {
    Name = "${var.environment}-db-credentials"
  })
}

# Temporal Database Credentials
resource "aws_secretsmanager_secret" "temporal_db_credentials" {
  name                    = "${var.environment}/aicte/temporal/credentials"
  kms_key_id              = aws_kms_key.app.arn
  recovery_window_in_days = var.environment == "production" ? 30 : 0

  tags = merge(var.tags, {
    Name = "${var.environment}-temporal-db-credentials"
  })
}

# Provider Connector Secrets (Integration Zone only)
resource "aws_secretsmanager_secret" "provider_credentials" {
  name                    = "${var.environment}/aicte/connectors/providers"
  kms_key_id              = aws_kms_key.app.arn
  recovery_window_in_days = var.environment == "production" ? 30 : 0

  tags = merge(var.tags, {
    Name = "${var.environment}-provider-credentials"
    Zone = "integration_zone"
  })
}

# JWT Signing Secret & Webhook HMAC Secret
resource "aws_secretsmanager_secret" "auth_secrets" {
  name                    = "${var.environment}/aicte/auth/tokens"
  kms_key_id              = aws_kms_key.app.arn
  recovery_window_in_days = var.environment == "production" ? 30 : 0

  tags = merge(var.tags, {
    Name = "${var.environment}-auth-tokens"
  })
}

# ---------------------------------------------------------------------------
# Amazon Cognito User Pool with TOTP MFA (Pilot OIDC)
# ---------------------------------------------------------------------------

resource "aws_cognito_user_pool" "pool" {
  name = "${var.environment}-aicte-workbench-users"

  mfa_configuration        = "ON" # Mandatory TOTP MFA for all users
  software_token_mfa_configuration {
    enabled = true
  }

  password_policy {
    minimum_length    = 14
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  tags = merge(var.tags, {
    Name        = "${var.environment}-cognito-user-pool"
    Environment = var.environment
  })
}

resource "aws_cognito_user_pool_client" "client" {
  name         = "${var.environment}-aicte-workbench-client"
  user_pool_id = aws_cognito_user_pool.pool.id

  generate_secret = true
  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  prevent_user_existence_errors = "ENABLED"
}
