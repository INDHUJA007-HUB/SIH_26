output "vpc_id" {
  value = module.networking.vpc_id
}

output "domain_db_endpoint" {
  value = module.database.domain_db_endpoint
}

output "ecr_repository_url" {
  value = module.telemetry.ecr_repository_url
}
