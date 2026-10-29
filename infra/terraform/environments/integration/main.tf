terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = "integration"
      Project     = "AICTE-Evidence-Workbench"
      ManagedBy   = "Terraform"
    }
  }
}

module "networking" {
  source      = "../../modules/networking"
  aws_region  = var.aws_region
  environment = "integration"
  vpc_cidr    = var.vpc_cidr
}

module "security" {
  source      = "../../modules/security"
  environment = "integration"
}

module "storage" {
  source             = "../../modules/storage"
  environment        = "integration"
  bucket_suffix      = var.bucket_suffix
  app_kms_key_arn    = module.security.app_kms_key_arn
  audit_kms_key_arn  = module.security.audit_kms_key_arn
  enable_object_lock = false
}

module "database" {
  source                  = "../../modules/database"
  environment             = "integration"
  vpc_id                  = module.networking.vpc_id
  database_subnet_ids     = module.networking.private_db_subnet_ids
  app_security_group_ids  = [module.ecs.app_tasks_security_group_id]
  kms_key_arn             = module.security.app_kms_key_arn
  instance_class          = "db.t4g.medium"
  temporal_instance_class = "db.t4g.medium"
  multi_az                = false
  backup_retention_days   = 7
}

module "telemetry" {
  source             = "../../modules/telemetry"
  environment        = "integration"
  kms_key_arn        = module.security.app_kms_key_arn
  log_retention_days = 14
}

module "ecs" {
  source                          = "../../modules/ecs"
  aws_region                      = var.aws_region
  environment                     = "integration"
  vpc_id                          = module.networking.vpc_id
  vpc_cidr                        = module.networking.vpc_cidr
  image_repository                = module.telemetry.ecr_repository_url
  image_tag                       = var.image_tag
  quarantine_bucket_arn           = module.storage.quarantine_bucket_arn
  clean_bucket_arn                = module.storage.clean_bucket_arn
  derivatives_bucket_arn          = module.storage.derivatives_bucket_arn
  reports_bucket_arn              = module.storage.reports_bucket_arn
  audit_vault_bucket_arn          = module.storage.audit_vault_bucket_arn
  app_kms_key_arn                 = module.security.app_kms_key_arn
  audit_kms_key_arn               = module.security.audit_kms_key_arn
  db_credentials_secret_arn       = module.security.db_credentials_secret_arn
  provider_credentials_secret_arn = module.security.provider_credentials_secret_arn
}
