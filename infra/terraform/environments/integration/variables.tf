variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.10.0.0/16"
}

variable "bucket_suffix" {
  type    = string
  default = "integration"
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "enabled_units" {
  type    = set(string)
  default = []
}
variable "tls_certificate_arn" {
  type    = string
  default = ""
}
variable "runtime_environment" {
  type    = map(string)
  default = {}
}
variable "runtime_secrets" {
  type    = map(string)
  default = {}
}
variable "unit_images" {
  type    = map(string)
  default = {}
}
