variable "aws_region" {
  description = "AWS deployment region"
  type        = string
  default     = "ap-south-1" # Mumbai reference region
}

variable "environment" {
  description = "Deployment environment name (integration, staging, production)"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.100.0.0/16"
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}
