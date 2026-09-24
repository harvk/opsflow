# ==========================================================
# OPSFLOW PHASE 12.4 - EC2 OUTPUTS (NON-SECRET)
# ==========================================================

output "live_ec2_instance_id" {
  description = "Phase 12.4 EC2 application host instance ID."
  value       = aws_instance.live_ec2.id
}

output "live_ec2_private_ip" {
  description = "Host private VPC IPv4."
  value       = aws_instance.live_ec2.private_ip
}

output "live_ec2_public_ip" {
  description = "Outbound-only public IPv4. NOT an application URL."
  value       = aws_instance.live_ec2.public_ip
}

output "live_ec2_instance_profile_name" {
  description = "EC2 IAM instance profile with SSM-only baseline."
  value       = aws_iam_instance_profile.live_ec2.name
}

output "live_ec2_ami_id" {
  description = "Resolved AL2023 x86_64 AMI selected at deployment."
  value       = aws_instance.live_ec2.ami
}
