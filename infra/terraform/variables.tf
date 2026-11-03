variable "aws_region" {
  description = "AWS region for the demo server"
  type        = string
  default     = "ap-south-1"
}

variable "instance_type" {
  description = "EC2 instance size"
  type        = string
  default     = "t3.small"
}

variable "key_name" {
  description = "Existing EC2 key pair name"
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "Your public IP in CIDR form, for example 203.0.113.10/32"
  type        = string
}

variable "app_image" {
  description = "Published Roadwise Docker image"
  type        = string
  default     = "roadwise:latest"
}
