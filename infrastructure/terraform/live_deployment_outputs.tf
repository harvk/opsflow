# ==========================================================
# OPSFLOW LIVE DEPLOYMENT OUTPUTS
# ==========================================================


output "live_vpc_id" {
  description = "OpsFlow live VPC ID."

  value = (
    aws_vpc.live.id
  )
}


output "live_public_subnet_ids" {
  description = "Public subnet IDs for the live deployment."

  value = [
    for subnet
    in aws_subnet.live_public :
    subnet.id
  ]
}


output "live_database_subnet_ids" {
  description = "Private RDS subnet IDs."

  value = [
    for subnet
    in aws_subnet.live_database :
    subnet.id
  ]
}


output "live_ec2_security_group_id" {
  description = "Security group reserved for live EC2 application instances."

  value = (
    aws_security_group.live_ec2.id
  )
}


output "live_rds_security_group_id" {
  description = "Private PostgreSQL security group."

  value = (
    aws_security_group.live_rds.id
  )
}


output "live_rds_identifier" {
  description = "RDS PostgreSQL DB instance identifier."

  value = (
    aws_db_instance.live_postgres.identifier
  )
}


output "live_rds_endpoint" {
  description = "Private RDS PostgreSQL endpoint."

  value = (
    aws_db_instance.live_postgres.address
  )
}


output "live_rds_port" {
  description = "PostgreSQL listener port."

  value = (
    aws_db_instance.live_postgres.port
  )
}


output "live_rds_master_secret_arn" {
  description = "Secrets Manager ARN for the RDS-managed master credential."

  value = (
    aws_db_instance.live_postgres
    .master_user_secret[0]
    .secret_arn
  )
}