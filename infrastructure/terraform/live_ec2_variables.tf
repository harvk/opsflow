# ==========================================================
# OPSFLOW PHASE 12.4 - LIVE EC2 INPUTS
# ==========================================================
# Keep this separate from the pre-existing variables.tf and
# live_deployment_variables.tf to avoid duplicate declarations.

variable "live_ec2_instance_type" {
  description = "Single x86_64 EC2 host. Verify t3.small Free Tier eligibility for this AWS account before apply."
  type        = string
  default     = "t3.small"

  validation {
    condition     = contains(["t3.micro", "t3.small"], var.live_ec2_instance_type)
    error_message = "Phase 12.4 permits only x86_64 t3.micro or t3.small."
  }
}

variable "live_ec2_root_volume_gib" {
  description = "Encrypted gp3 EC2 root disk size in GiB. This is separate from RDS storage."
  type        = number
  default     = 30

  validation {
    condition     = var.live_ec2_root_volume_gib >= 20 && var.live_ec2_root_volume_gib <= 100
    error_message = "Choose a root volume between 20 and 100 GiB."
  }
}
