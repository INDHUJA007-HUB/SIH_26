variable "environment" {
  description = "Deployment environment name"
  type        = string
}

variable "bucket_suffix" {
  description = "Unique account/region suffix for S3 bucket globally unique names"
  type        = string
  default     = "wb"
}

variable "app_kms_key_arn" {
  description = "KMS Key ARN for application evidence and reports"
  type        = string
}

variable "audit_kms_key_arn" {
  description = "Dedicated KMS Key ARN for the independent audit vault"
  type        = string
}

variable "enable_object_lock" {
  description = "Whether to enable S3 Object Lock on the audit vault bucket"
  type        = bool
  default     = false
}

variable "object_lock_mode" {
  description = "Object lock mode (COMPLIANCE or GOVERNANCE)"
  type        = string
  default     = "GOVERNANCE"
}

variable "object_lock_retention_days" {
  description = "Default object lock retention period in days"
  type        = number
  default     = 2555 # 7 years statutory retention
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
