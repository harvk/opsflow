# ==========================================================
# OPSFLOW LIVE AMAZON RDS POSTGRESQL
# ==========================================================
#
# Migration target:
#
#   Local PostgreSQL 18.6
#             |
#             v
#   Amazon RDS PostgreSQL 18.6
#
# Runtime application databases:
#
#   opsflow
#   opsflow_incidents
#
# Test databases remain local/CI only.
#
# ==========================================================


# ==========================================================
# DB SUBNET GROUP
# ==========================================================

resource "aws_db_subnet_group" "live" {
  name = (
    "${local.live_name_prefix}-postgres-subnets"
  )

  description = (
    "Private database subnets for OpsFlow live PostgreSQL"
  )

  subnet_ids = [
    for subnet
    in aws_subnet.live_database :
    subnet.id
  ]

  tags = merge(
    local.live_common_tags,
    {
      Name = (
        "${local.live_name_prefix}-postgres-subnets"
      )
    },
  )
}


# ==========================================================
# POSTGRESQL PARAMETER GROUP
# ==========================================================
#
# PostgreSQL 15+ defaults rds.force_ssl to enabled.
#
# OpsFlow still configures it explicitly so that TLS is an
# infrastructure contract rather than an undocumented AWS
# default. The static parameter is applied on DB reboot.
#
# ==========================================================

resource "aws_db_parameter_group" "live_postgres" {
  name = (
    "${local.live_name_prefix}-postgres18"
  )

  family = (
    var.live_rds_parameter_group_family
  )

  description = (
    "OpsFlow live PostgreSQL 18 parameters"
  )

  parameter {
    name = "rds.force_ssl"

    value = "1"

    apply_method = "pending-reboot"
  }

  tags = merge(
    local.live_common_tags,
    {
      Name = (
        "${local.live_name_prefix}-postgres18"
      )
    },
  )
}


# ==========================================================
# RDS POSTGRESQL INSTANCE
# ==========================================================

resource "aws_db_instance" "live_postgres" {
  identifier = (
    "${local.live_name_prefix}-postgres"
  )

  engine = "postgres"

  engine_version = (
    var.live_rds_engine_version
  )

  instance_class = (
    var.live_rds_instance_class
  )

  # --------------------------------------------------------
  # DATABASE
  # --------------------------------------------------------

  db_name = "opsflow"

  username = "opsflow_admin"

  manage_master_user_password = true

  port = 5432

  # --------------------------------------------------------
  # STORAGE
  # --------------------------------------------------------

  allocated_storage = (
    var.live_rds_allocated_storage_gib
  )

  max_allocated_storage = (
    var.live_rds_max_allocated_storage_gib
  )

  storage_type = "gp3"

  storage_encrypted = true

  # --------------------------------------------------------
  # NETWORK
  # --------------------------------------------------------

  db_subnet_group_name = (
    aws_db_subnet_group.live.name
  )

  vpc_security_group_ids = [
    aws_security_group.live_rds.id,
  ]

  publicly_accessible = false

  # --------------------------------------------------------
  # AVAILABILITY
  # --------------------------------------------------------
  #
  # Initial portfolio deployment:
  #
  #   Single-AZ RDS
  #
  # The DB subnet group already spans two AZs so the
  # architecture can later move to Multi-AZ.
  #
  # --------------------------------------------------------

  multi_az = false

  # --------------------------------------------------------
  # BACKUPS
  # --------------------------------------------------------
  #
  # AWS Free Plan-compatible retention.
  #
  # Retain one day of automated backups rather than
  # disabling backups entirely.
  #
  # --------------------------------------------------------

  backup_retention_period = 1

  copy_tags_to_snapshot = true

  # --------------------------------------------------------
  # ENGINE MANAGEMENT
  # --------------------------------------------------------
  #
  # Keep 18.6 pinned during the migration.
  #
  # Minor upgrades will be handled deliberately through
  # Terraform after the live migration is stable.
  #
  # --------------------------------------------------------

  auto_minor_version_upgrade = false

  allow_major_version_upgrade = false

  parameter_group_name = (
    aws_db_parameter_group.live_postgres.name
  )

  # --------------------------------------------------------
  # DELETION SAFETY
  # --------------------------------------------------------

  deletion_protection = true

  skip_final_snapshot = false

  final_snapshot_identifier = (
    "${local.live_name_prefix}-postgres-final"
  )

  # --------------------------------------------------------
  # TAGS
  # --------------------------------------------------------

  tags = merge(
    local.live_common_tags,
    {
      Name = (
        "${local.live_name_prefix}-postgres"
      )

      Service = "postgresql"
    },
  )
}