# ==========================================================
# OPSFLOW LIVE SECURITY GROUPS
# ==========================================================
#
# This phase establishes:
#
#   EC2 application security group
#       |
#       | PostgreSQL 5432
#       v
#   RDS security group
#
# No direct Internet ingress is granted to either group.
#
# ALB ingress will be added in the ALB phase.
#
# ==========================================================


# ==========================================================
# EC2 APPLICATION SECURITY GROUP
# ==========================================================
#
# No inbound rules yet.
#
# Later:
#
#   ALB security group
#       |
#       v
#   EC2 application port
#
# Administration will use AWS Systems Manager rather than
# opening SSH port 22.
#
# ==========================================================

resource "aws_security_group" "live_ec2" {
  name = (
    "${local.live_name_prefix}-ec2-sg"
  )

  description = (
    "OpsFlow live EC2 application security group"
  )

  vpc_id = aws_vpc.live.id

  egress {
    description = "Allow application outbound traffic"

    from_port = 0

    to_port = 0

    protocol = "-1"

    cidr_blocks = [
      "0.0.0.0/0",
    ]
  }

  tags = merge(
    local.live_common_tags,
    {
      Name = "${local.live_name_prefix}-ec2-sg"
    },
  )
}


# ==========================================================
# RDS SECURITY GROUP
# ==========================================================
#
# PostgreSQL is not allowed from:
#
#   0.0.0.0/0
#
# It is allowed ONLY from resources carrying the EC2
# application security group.
#
# ==========================================================

resource "aws_security_group" "live_rds" {
  name = (
    "${local.live_name_prefix}-rds-sg"
  )

  description = (
    "OpsFlow live private PostgreSQL security group"
  )

  vpc_id = aws_vpc.live.id

  ingress {
    description = (
      "PostgreSQL from OpsFlow EC2 application hosts"
    )

    from_port = 5432

    to_port = 5432

    protocol = "tcp"

    security_groups = [
      aws_security_group.live_ec2.id,
    ]
  }

  egress {
    description = "Allow RDS response traffic"

    from_port = 0

    to_port = 0

    protocol = "-1"

    cidr_blocks = [
      "0.0.0.0/0",
    ]
  }

  tags = merge(
    local.live_common_tags,
    {
      Name = "${local.live_name_prefix}-rds-sg"
    },
  )
}