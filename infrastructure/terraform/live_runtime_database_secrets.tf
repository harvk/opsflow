# Phase 12.6B. Permanent Secrets Manager metadata; secret VALUES are generated
# on EC2 at bootstrap time, never supplied to Terraform or committed to Git.
resource "aws_secretsmanager_secret" "live_core_db_login" {
  name                    = "${local.live_name_prefix}/runtime/core-db-login"
  description             = "OpsFlow core application's restricted RDS login"
  recovery_window_in_days = 7
  tags                    = local.live_common_tags
}

resource "aws_secretsmanager_secret" "live_incident_db_login" {
  name                    = "${local.live_name_prefix}/runtime/incident-db-login"
  description             = "OpsFlow incident service's restricted RDS login"
  recovery_window_in_days = 7
  tags                    = local.live_common_tags
}

# The initial single-host architecture shares one EC2 instance role. Hence
# processes on that host must be trusted: IAM does not isolate individual
# Docker containers on a shared EC2 instance profile.
data "aws_iam_policy_document" "live_runtime_db_secret_read" {
  statement {
    sid     = "ReadOnlyOpsFlowApplicationDatabaseSecrets"
    actions = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [
      aws_secretsmanager_secret.live_core_db_login.arn,
      aws_secretsmanager_secret.live_incident_db_login.arn,
    ]
  }
}

resource "aws_iam_role_policy" "live_runtime_db_secret_read" {
  name   = "${local.live_name_prefix}-runtime-db-secret-read"
  role   = aws_iam_role.live_ec2.id
  policy = data.aws_iam_policy_document.live_runtime_db_secret_read.json
}

output "live_core_database_secret_arn" {
  description = "Metadata-only secret ARN; Terraform never stores the password."
  value       = aws_secretsmanager_secret.live_core_db_login.arn
}

output "live_incident_database_secret_arn" {
  description = "Metadata-only secret ARN; Terraform never stores the password."
  value       = aws_secretsmanager_secret.live_incident_db_login.arn
}
