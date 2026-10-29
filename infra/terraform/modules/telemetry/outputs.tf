output "ecr_repository_url" {
  description = "URL of the application ECR repository"
  value       = aws_ecr_repository.app.repository_url
}

output "ecr_repository_arn" {
  description = "ARN of the application ECR repository"
  value       = aws_ecr_repository.app.arn
}

output "log_group_arns" {
  description = "Map of CloudWatch log group ARNs by unit"
  value       = { for k, v in aws_cloudwatch_log_group.units : k => v.arn }
}
