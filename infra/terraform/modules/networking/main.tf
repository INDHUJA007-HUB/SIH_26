terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ---------------------------------------------------------------------------
# Virtual Private Cloud (VPC) & Multi-AZ Subnets
# ---------------------------------------------------------------------------

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name        = "${var.environment}-aicte-workbench-vpc"
    Environment = var.environment
    ManagedBy   = "Terraform"
  })
}

# Availability Zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Public Subnets (Edge / ALB)
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = false

  tags = merge(var.tags, {
    Name        = "${var.environment}-public-subnet-${count.index + 1}"
    Zone        = "public_edge"
    Environment = var.environment
  })
}

# Private Application Subnets (API, Workers, Relay)
resource "aws_subnet" "private_app" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 2)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = merge(var.tags, {
    Name        = "${var.environment}-private-app-subnet-${count.index + 1}"
    Zone        = "application_zone"
    Environment = var.environment
  })
}

# Private Isolated Subnets (Untrusted Processing: Scan, Document, Media)
# No default route to Internet or NAT Gateway
resource "aws_subnet" "private_isolated" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 4)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = merge(var.tags, {
    Name        = "${var.environment}-private-isolated-subnet-${count.index + 1}"
    Zone        = "untrusted_processing_zone"
    Environment = var.environment
  })
}

# Private Database Subnets (RDS PostgreSQL Domain & Temporal)
resource "aws_subnet" "private_db" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 6)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = merge(var.tags, {
    Name        = "${var.environment}-private-db-subnet-${count.index + 1}"
    Zone        = "database_zone"
    Environment = var.environment
  })
}

# Internet Gateway for Public Edge (Inbound ALB only)
resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = merge(var.tags, {
    Name        = "${var.environment}-aicte-igw"
    Environment = var.environment
  })
}

# Elastic IPs for NAT Gateways (One per AZ for High Availability)
resource "aws_eip" "nat" {
  count  = 2
  domain = "vpc"

  tags = merge(var.tags, {
    Name        = "${var.environment}-nat-eip-${count.index + 1}"
    Environment = var.environment
  })
}

# NAT Gateways in Public Subnets (For outbound Integration Zone connectors only)
resource "aws_nat_gateway" "nat" {
  count         = 2
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(var.tags, {
    Name        = "${var.environment}-nat-gw-${count.index + 1}"
    Environment = var.environment
  })

  depends_on = [aws_internet_gateway.igw]
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }

  tags = merge(var.tags, {
    Name        = "${var.environment}-public-rt"
    Environment = var.environment
  })
}

resource "aws_route_table" "private_app" {
  count  = 2
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat[count.index].id
  }

  tags = merge(var.tags, {
    Name        = "${var.environment}-private-app-rt-${count.index + 1}"
    Environment = var.environment
  })
}

# Isolated Route Table (No egress routes whatsoever)
resource "aws_route_table" "isolated" {
  vpc_id = aws_vpc.main.id

  tags = merge(var.tags, {
    Name        = "${var.environment}-isolated-rt"
    Zone        = "untrusted_processing_zone"
    Environment = var.environment
  })
}

# Subnet Route Table Associations
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private_app" {
  count          = 2
  subnet_id      = aws_subnet.private_app[count.index].id
  route_table_id = aws_route_table.private_app[count.index].id
}

resource "aws_route_table_association" "private_isolated" {
  count          = 2
  subnet_id      = aws_subnet.private_isolated[count.index].id
  route_table_id = aws_route_table.isolated.id
}

resource "aws_route_table_association" "private_db" {
  count          = 2
  subnet_id      = aws_subnet.private_db[count.index].id
  route_table_id = aws_route_table.isolated.id
}

# ---------------------------------------------------------------------------
# VPC Endpoints (Private AWS API Access for Isolated / App Tasks)
# ---------------------------------------------------------------------------

# Gateway Endpoint for S3 (Zero NAT cost, private access from all subnets)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = concat([aws_route_table.public.id, aws_route_table.isolated.id], aws_route_table.private_app[*].id)

  tags = merge(var.tags, {
    Name = "${var.environment}-s3-vpc-endpoint"
  })
}

# Interface Endpoints for Secrets Manager, KMS, CloudWatch Logs, ECR
resource "aws_security_group" "vpc_endpoints" {
  name        = "${var.environment}-vpc-endpoints-sg"
  description = "Allow TLS traffic from private subnets to VPC interface endpoints"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "TLS from VPC subnets"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.environment}-vpc-endpoints-sg"
  })
}

locals {
  interface_services = ["secretsmanager", "kms", "logs", "ecr.api", "ecr.dkr"]
}

resource "aws_vpc_endpoint" "interfaces" {
  for_each            = toset(locals.interface_services)
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.${each.key}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private_app[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(var.tags, {
    Name = "${var.environment}-${each.key}-endpoint"
  })
}
