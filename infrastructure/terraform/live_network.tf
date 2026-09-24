# ==========================================================
# OPSFLOW LIVE NETWORK
# ==========================================================
#
# Network topology:
#
#   Internet
#       |
#   Internet Gateway
#       |
#   +-----------------------+
#   |                       |
# Public A               Public B
#   AZ A                    AZ B
#
#   +-----------------------+
#   |                       |
# Database A             Database B
# PRIVATE                  PRIVATE
#
# Database subnets have no default Internet route.
#
# ==========================================================


data "aws_availability_zones" "live_available" {
  state = "available"

  filter {
    name = "opt-in-status"

    values = [
      "opt-in-not-required",
      "opted-in",
    ]
  }
}


locals {
  live_name_prefix = "${var.project_name}-${var.environment}"

  live_availability_zones = slice(
    data.aws_availability_zones.live_available.names,
    0,
    2,
  )

  live_common_tags = {
    Project = var.project_name

    Environment = var.environment

    ManagedBy = "Terraform"

    Deployment = "live"

    Phase = "12"
  }
}


# ==========================================================
# VPC
# ==========================================================

resource "aws_vpc" "live" {
  cidr_block = var.live_vpc_cidr

  enable_dns_support = true

  enable_dns_hostnames = true

  tags = merge(
    local.live_common_tags,
    {
      Name = "${local.live_name_prefix}-vpc"
    },
  )
}


# ==========================================================
# INTERNET GATEWAY
# ==========================================================

resource "aws_internet_gateway" "live" {
  vpc_id = aws_vpc.live.id

  tags = merge(
    local.live_common_tags,
    {
      Name = "${local.live_name_prefix}-igw"
    },
  )
}


# ==========================================================
# PUBLIC SUBNETS
# ==========================================================
#
# These subnets will eventually contain:
#
#   - the internet-facing ALB in both AZs
#   - the initial EC2 application host in one AZ
#
# map_public_ip_on_launch remains false.
#
# EC2 public addressing will be an explicit instance-level
# decision rather than an implicit subnet behavior.
#
# ==========================================================

resource "aws_subnet" "live_public" {
  count = 2

  vpc_id = aws_vpc.live.id

  cidr_block = (
    var.live_public_subnet_cidrs[
      count.index
    ]
  )

  availability_zone = (
    local.live_availability_zones[
      count.index
    ]
  )

  map_public_ip_on_launch = false

  tags = merge(
    local.live_common_tags,
    {
      Name = (
        "${local.live_name_prefix}-public-${count.index + 1}"
      )

      Tier = "public"
    },
  )
}


# ==========================================================
# PRIVATE DATABASE SUBNETS
# ==========================================================

resource "aws_subnet" "live_database" {
  count = 2

  vpc_id = aws_vpc.live.id

  cidr_block = (
    var.live_database_subnet_cidrs[
      count.index
    ]
  )

  availability_zone = (
    local.live_availability_zones[
      count.index
    ]
  )

  map_public_ip_on_launch = false

  tags = merge(
    local.live_common_tags,
    {
      Name = (
        "${local.live_name_prefix}-database-${count.index + 1}"
      )

      Tier = "database"
    },
  )
}


# ==========================================================
# PUBLIC ROUTE TABLE
# ==========================================================

resource "aws_route_table" "live_public" {
  vpc_id = aws_vpc.live.id

  tags = merge(
    local.live_common_tags,
    {
      Name = "${local.live_name_prefix}-public-rt"
    },
  )
}


resource "aws_route" "live_public_internet" {
  route_table_id = (
    aws_route_table.live_public.id
  )

  destination_cidr_block = "0.0.0.0/0"

  gateway_id = (
    aws_internet_gateway.live.id
  )
}


resource "aws_route_table_association" "live_public" {
  count = 2

  subnet_id = (
    aws_subnet.live_public[
      count.index
    ].id
  )

  route_table_id = (
    aws_route_table.live_public.id
  )
}


# ==========================================================
# DATABASE ROUTE TABLE
# ==========================================================
#
# Deliberately has NO:
#
#   0.0.0.0/0 -> Internet Gateway
#   0.0.0.0/0 -> NAT Gateway
#
# RDS communicates with application resources through
# private VPC routing.
#
# ==========================================================

resource "aws_route_table" "live_database" {
  vpc_id = aws_vpc.live.id

  tags = merge(
    local.live_common_tags,
    {
      Name = "${local.live_name_prefix}-database-rt"
    },
  )
}


resource "aws_route_table_association" "live_database" {
  count = 2

  subnet_id = (
    aws_subnet.live_database[
      count.index
    ].id
  )

  route_table_id = (
    aws_route_table.live_database.id
  )
}