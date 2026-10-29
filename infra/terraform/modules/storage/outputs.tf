output "quarantine_bucket_name" {
  description = "Name of the quarantine S3 bucket"
  value       = aws_s3_bucket.buckets["quarantine"].id
}

output "quarantine_bucket_arn" {
  description = "ARN of the quarantine S3 bucket"
  value       = aws_s3_bucket.buckets["quarantine"].arn
}

output "clean_bucket_name" {
  description = "Name of the clean accepted evidence S3 bucket"
  value       = aws_s3_bucket.buckets["clean"].id
}

output "clean_bucket_arn" {
  description = "ARN of the clean accepted evidence S3 bucket"
  value       = aws_s3_bucket.buckets["clean"].arn
}

output "derivatives_bucket_name" {
  description = "Name of the derivatives S3 bucket"
  value       = aws_s3_bucket.buckets["derivatives"].id
}

output "derivatives_bucket_arn" {
  description = "ARN of the derivatives S3 bucket"
  value       = aws_s3_bucket.buckets["derivatives"].arn
}

output "reports_bucket_name" {
  description = "Name of the reports S3 bucket"
  value       = aws_s3_bucket.buckets["reports"].id
}

output "reports_bucket_arn" {
  description = "ARN of the reports S3 bucket"
  value       = aws_s3_bucket.buckets["reports"].arn
}

output "audit_vault_bucket_name" {
  description = "Name of the audit vault S3 bucket"
  value       = aws_s3_bucket.buckets["audit_vault"].id
}

output "audit_vault_bucket_arn" {
  description = "ARN of the audit vault S3 bucket"
  value       = aws_s3_bucket.buckets["audit_vault"].arn
}
