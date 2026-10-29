variable "environment" {
  description = "Deployment environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "database_subnet_ids" {
  description = "Subnet IDs for the RDS database subnet group"
  type        = list(string)
}

variable "app_security_group_ids" {
  description = "Security groups of application and worker tasks permitted to connect"
  type        = list(string)
}

variable "kms_key_arn" {
  description = "KMS Key ARN for storage encryption"
  type        = string
}

variable "instance_class" {
  description = "RDS instance class for domain DB"
  type        = string
  default     = "db.r6g.xlarge"
}

variable "temporal_instance_class" {
  description = "RDS instance class for Temporal persistence"
  type        = string
  default     = "db.r6g.large"
}

variable "allocated_storage" {
  description = "Initial allocated storage in GB"
  type        = number
  default     = 100
}

variable "max_allocated_storage" {
  description = "Storage autoscaling upper limit in GB"
  type        = number
  default     = 1000
}

variable "multi_az" {
  description = "Enable Multi-AZ failover deployment"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Automated backup retention days (PITR)"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
