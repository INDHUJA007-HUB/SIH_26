variable "environment" {
  description = "Deployment environment name"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS CMK ARN for log encryption"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 90
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
