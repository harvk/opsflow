# ==========================================================
# OPSFLOW LIVE DEPLOYMENT VARIABLES
# ==========================================================
#
# Phase 12:
#
#   - live VPC
#   - public ingress subnets
#   - private RDS subnets
#   - EC2 application security boundary
#   - PostgreSQL RDS configuration
#
# Existing project_name, environment, and aws_region
# variables remain owned by variables.tf.
#
# ==========================================================


variable "live_vpc_cidr" {
  description = "IPv4 CIDR block for the OpsFlow live deployment VPC."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition = can(
      cidrnetmask(
        var.live_vpc_cidr
      )
    )

    error_message = "live_vpc_cidr must be a valid IPv4 CIDR block."
  }
}


variable "live_public_subnet_cidrs" {
  description = "CIDRs for the two public ingress/application subnets."
  type        = list(string)

  default = [
    "10.42.0.0/24",
    "10.42.1.0/24",
  ]

  validation {
    condition = (
      length(
        var.live_public_subnet_cidrs
      )
      == 2
    )

    error_message = "Exactly two public subnet CIDRs are required."
  }
}


variable "live_database_subnet_cidrs" {
  description = "CIDRs for the two private RDS database subnets."
  type        = list(string)

  default = [
    "10.42.10.0/24",
    "10.42.11.0/24",
  ]

  validation {
    condition = (
      length(
        var.live_database_subnet_cidrs
      )
      == 2
    )

    error_message = "Exactly two database subnet CIDRs are required."
  }
}


variable "live_rds_engine_version" {
  description = "Exact PostgreSQL version used by the live RDS instance."
  type        = string
  default     = "18.6"
}


variable "live_rds_parameter_group_family" {
  description = "RDS PostgreSQL parameter-group family."
  type        = string
  default     = "postgres18"
}


variable "live_rds_instance_class" {
  description = "AWS-validated RDS instance class for the live database."
  type        = string

  validation {
    condition = (
      length(
        trimspace(
          var.live_rds_instance_class
        )
      )
      > 0
      &&
      startswith(
        var.live_rds_instance_class,
        "db."
      )
    )

    error_message = "live_rds_instance_class must be a valid RDS class beginning with db."
  }
}


variable "live_rds_allocated_storage_gib" {
  description = "Initial allocated PostgreSQL storage in GiB."
  type        = number
  default     = 20

  validation {
    condition = (
      var.live_rds_allocated_storage_gib
      >= 20
    )

    error_message = "Initial RDS storage must be at least 20 GiB."
  }
}


variable "live_rds_max_allocated_storage_gib" {
  description = "Maximum RDS storage-autoscaling threshold in GiB."
  type        = number
  default     = 100

  validation {
    condition = (
      var.live_rds_max_allocated_storage_gib
      >
      var.live_rds_allocated_storage_gib
    )

    error_message = "Maximum RDS storage must exceed initial allocated storage."
  }
}