output "app_kms_key_arn" {
  description = "ARN of the application KMS CMK"
  value       = aws_kms_key.app.arn
}

output "audit_kms_key_arn" {
  description = "ARN of the audit vault KMS CMK"
  value       = aws_kms_key.audit.arn
}

output "db_credentials_secret_arn" {
  description = "ARN of the database credentials secret"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "temporal_db_credentials_secret_arn" {
  description = "ARN of the Temporal database credentials secret"
  value       = aws_secretsmanager_secret.temporal_db_credentials.arn
}

output "provider_credentials_secret_arn" {
  description = "ARN of the external statutory provider credentials secret"
  value       = aws_secretsmanager_secret.provider_credentials.arn
}

output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.pool.id
}

output "cognito_user_pool_client_id" {
  description = "ID of the Cognito User Pool Client"
  value       = aws_cognito_user_pool_client.client.id
}
