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
# S3 Buckets across Evidence, Reports, and Audit Trust Boundaries
# ---------------------------------------------------------------------------

locals {
  bucket_keys = {
    quarantine  = { desc = "quarantined uploads prior to screening", lock = false },
    clean       = { desc = "accepted original evidence versions", lock = false },
    derivatives = { desc = "safe derivative renderings and contact sheets", lock = false },
    reports     = { desc = "immutable generated evaluation and audit reports", lock = false },
    audit_vault = { desc = "regulatory audit logs and signed replay bundles", lock = var.enable_object_lock },
  }
}

resource "aws_s3_bucket" "buckets" {
  for_each      = local.bucket_keys
  bucket        = "${var.environment}-aicte-${replace(each.key, "_", "-")}-${var.bucket_suffix}"
  force_destroy = var.environment != "production"

  tags = merge(var.tags, {
    Name        = "${var.environment}-aicte-${each.key}"
    Role        = each.key
    Environment = var.environment
    ManagedBy   = "Terraform"
  })
}

# Object Lock Configuration for Audit Vault
resource "aws_s3_bucket_object_lock_configuration" "audit_vault_lock" {
  count  = var.enable_object_lock ? 1 : 0
  bucket = aws_s3_bucket.buckets["audit_vault"].id

  rule {
    default_retention {
      mode = var.object_lock_mode # COMPLIANCE or GOVERNANCE
      days = var.object_lock_retention_days
    }
  }
}

# Versioning on ALL evidence, report, and audit buckets
resource "aws_s3_bucket_versioning" "versioning" {
  for_each = local.bucket_keys
  bucket   = aws_s3_bucket.buckets[each.key].id

  versioning_configuration {
    status = "Enabled"
  }
}

# Server-Side Encryption using Customer-Managed KMS Key
resource "aws_s3_bucket_server_side_encryption_configuration" "encryption" {
  for_each = local.bucket_keys
  bucket   = aws_s3_bucket.buckets[each.key].id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = each.key == "audit_vault" ? var.audit_kms_key_arn : var.app_kms_key_arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# Block ALL Public Access (Public Edge strictly prohibited)
resource "aws_s3_bucket_public_access_block" "public_block" {
  for_each = local.bucket_keys
  bucket   = aws_s3_bucket.buckets[each.key].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enforce TLS / HTTPS Only on all buckets
resource "aws_s3_bucket_policy" "enforce_tls" {
  for_each = local.bucket_keys
  bucket   = aws_s3_bucket.buckets[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureHTTP"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.buckets[each.key].arn,
          "${aws_s3_bucket.buckets[each.key].arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}
