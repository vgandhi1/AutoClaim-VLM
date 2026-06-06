terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "raw" {
  bucket = var.raw_bucket_name
}

resource "aws_s3_bucket" "processed" {
  bucket = var.processed_bucket_name
}

resource "aws_s3_bucket" "opensource_raw" {
  bucket = var.opensource_raw_bucket_name
}

resource "aws_s3_bucket" "opensource_processed" {
  bucket = var.opensource_processed_bucket_name
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "processed" {
  bucket                  = aws_s3_bucket.processed.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "opensource_raw" {
  bucket                  = aws_s3_bucket.opensource_raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "opensource_processed" {
  bucket                  = aws_s3_bucket.opensource_processed.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

locals {
  buckets = {
    raw                  = aws_s3_bucket.raw.id
    processed            = aws_s3_bucket.processed.id
    opensource_raw       = aws_s3_bucket.opensource_raw.id
    opensource_processed = aws_s3_bucket.opensource_processed.id
  }
}

# Encrypt all objects at rest (claim images may contain PII).
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = local.buckets
  bucket   = each.value

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# Versioning provides a recovery path for accidental overwrite / delete.
resource "aws_s3_bucket_versioning" "this" {
  for_each = local.buckets
  bucket   = each.value

  versioning_configuration {
    status = "Enabled"
  }
}

# Expire old noncurrent versions and clean up incomplete multipart uploads.
resource "aws_s3_bucket_lifecycle_configuration" "this" {
  for_each = local.buckets
  bucket   = each.value

  rule {
    id     = "expire-noncurrent-and-abort-mpu"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
