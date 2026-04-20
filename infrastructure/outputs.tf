output "raw_bucket" {
  value = aws_s3_bucket.raw.bucket
}

output "processed_bucket" {
  value = aws_s3_bucket.processed.bucket
}

output "opensource_raw_bucket" {
  value = aws_s3_bucket.opensource_raw.bucket
}

output "opensource_processed_bucket" {
  value = aws_s3_bucket.opensource_processed.bucket
}
