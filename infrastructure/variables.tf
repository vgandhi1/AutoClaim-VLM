variable "project" {
  type        = string
  description = "Short project prefix for resource names"
  default     = "claimlens"
}

variable "environment" {
  type        = string
  description = "Deployment environment label"
  default     = "dev"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "raw_bucket_name" {
  type        = string
  description = "S3 bucket for raw claim images"
}

variable "processed_bucket_name" {
  type        = string
  description = "S3 bucket for processed images"
}

variable "opensource_raw_bucket_name" {
  type        = string
  description = "S3 bucket for open-source dataset landing"
}

variable "opensource_processed_bucket_name" {
  type        = string
  description = "S3 bucket for normalized open-source images"
}
