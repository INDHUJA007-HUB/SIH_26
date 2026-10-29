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
