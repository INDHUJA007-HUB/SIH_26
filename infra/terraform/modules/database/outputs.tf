output "domain_db_endpoint" {
  description = "Connection endpoint for the domain RDS PostgreSQL instance"
  value       = aws_db_instance.domain.endpoint
}

output "domain_db_address" {
  description = "Address hostname for the domain RDS PostgreSQL instance"
  value       = aws_db_instance.domain.address
}

output "domain_db_port" {
  description = "Port for the domain RDS PostgreSQL instance"
  value       = aws_db_instance.domain.port
}

output "temporal_db_endpoint" {
  description = "Connection endpoint for the Temporal persistence RDS instance"
  value       = aws_db_instance.temporal.endpoint
}

output "db_security_group_id" {
  description = "Security group ID of the database tier"
  value       = aws_security_group.db.id
}
