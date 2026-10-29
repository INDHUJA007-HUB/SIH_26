variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "bucket_suffix" {
  type    = string
  default = "prod"
}

variable "image_tag" {
  type    = string
  default = "v1.0.0"
}
