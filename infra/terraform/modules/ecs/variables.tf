variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
}

variable "image_repository" {
  description = "ECR repository URL"
  type        = string
}

variable "image_tag" {
  description = "Immutable image digest / release tag"
  type        = string
  default     = "latest"
}

variable "quarantine_bucket_arn" {
  description = "Quarantine S3 bucket ARN"
  type        = string
}

variable "clean_bucket_arn" {
  description = "Clean accepted evidence S3 bucket ARN"
  type        = string
}

variable "derivatives_bucket_arn" {
  description = "Derivatives S3 bucket ARN"
  type        = string
}

variable "reports_bucket_arn" {
  description = "Reports S3 bucket ARN"
  type        = string
}

variable "audit_vault_bucket_arn" {
  description = "Audit vault S3 bucket ARN"
  type        = string
}

variable "app_kms_key_arn" {
  description = "Application KMS CMK ARN"
  type        = string
}

variable "audit_kms_key_arn" {
  description = "Audit KMS CMK ARN"
  type        = string
}

variable "db_credentials_secret_arn" {
  description = "DB credentials secret ARN"
  type        = string
}

variable "provider_credentials_secret_arn" {
  description = "Provider credentials secret ARN"
  type        = string
}

variable "otel_endpoint" {
  description = "OpenTelemetry collector endpoint"
  type        = string
  default     = "http://otel-collector.internal:4317"
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}

variable "enabled_units" {
  description = "Units explicitly approved for deployment; empty keeps infrastructure dormant"
  type        = set(string)
  default     = []
}
variable "private_subnet_ids" {
  type    = list(string)
  default = []
}
variable "unit_commands" {
  description = "Reviewed worker commands for units without a bundled entry point"
  type        = map(list(string))
  default     = {}
}
variable "runtime_environment" {
  description = "Non-secret WB_ runtime settings"
  type        = map(string)
  default     = {}
}
variable "runtime_secrets" {
  description = "Secret environment names mapped to Secrets Manager ARNs"
  type        = map(string)
  default     = {}
}

variable "unit_images" {
  description = "Immutable per-unit images, including the media build target for media_worker"
  type        = map(string)
  default     = {}
}
variable "public_subnet_ids" {
  type    = list(string)
  default = []
}
variable "tls_certificate_arn" {
  type    = string
  default = ""
}
