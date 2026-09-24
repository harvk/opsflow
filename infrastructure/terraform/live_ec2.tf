# ==========================================================
# OPSFLOW PHASE 12.4 - SINGLE EC2 DOCKER HOST
# ==========================================================
# References the Phase 12.3 VPC/subnet/security-group resources:
#   aws_subnet.live_public[0]
#   aws_route.live_public_internet
#   aws_security_group.live_ec2
#   local.live_name_prefix, local.live_common_tags
# Existing provider and aws_region variable remain untouched.

# Resolve the latest AWS-owned, standard (non-minimal) Amazon Linux
# 2023 x86_64 AMI offered in the configured Region. The previous
# kernel-6.1 public SSM parameter was missing in the target Region;
# EC2 AMI discovery avoids that dependency. The selected kernel may
# differ between releases. Review the resolved AMI name before apply.
# After launch, ignore_changes = [ami] prevents an incidental AMI
# catalog update from replacing the existing host.
data "aws_ami" "live_al2023_x86_64" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-kernel-*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_iam_policy_document" "live_ec2_assume_role" {
  statement {
    sid     = "AllowEC2ToAssumeRole"
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "live_ec2" {
  name               = "${local.live_name_prefix}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.live_ec2_assume_role.json
  tags               = local.live_common_tags
}

# 12.4 scope: SSM only. Do not give this host AdministratorAccess,
# wildcard Secrets Manager rights, SQS permissions or RDS master
# credentials at instance creation time. Subsequent phases add
# minimum viable AWS permissions only when needed.
resource "aws_iam_role_policy_attachment" "live_ec2_ssm" {
  role       = aws_iam_role.live_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "live_ec2" {
  name = "${local.live_name_prefix}-ec2-profile"
  role = aws_iam_role.live_ec2.name
  tags = local.live_common_tags
}

resource "aws_instance" "live_ec2" {
  ami                    = data.aws_ami.live_al2023_x86_64.id
  instance_type          = var.live_ec2_instance_type
  subnet_id              = aws_subnet.live_public[0].id
  vpc_security_group_ids = [aws_security_group.live_ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.live_ec2.name

  # Public IPv4 is for OUTBOUND NAT-less traffic to package registries
  # and AWS public endpoints, not for accepting inbound app/SSH traffic.
  associate_public_ip_address = true

  # No SSH key-pair. No SG inbound rule. Administration via SSM.
  user_data = file("${path.module}/bootstrap/live_ec2_user_data.sh")

  # Avoid surplus-credit charges while we measure workload demands.
  # Standard mode may throttle if sustained CPU credits are exhausted.
  credit_specification {
    cpu_credits = "standard"
  }

  monitoring = false # Basic EC2 monitoring, not paid detailed monitoring.

  # IMDSv2 required. Hop limit 2 accommodates potential Docker bridge
  # credential access later; the instance role MUST stay least-privilege.
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.live_ec2_root_volume_gib
    encrypted             = true
    delete_on_termination = true
  }

  tags = merge(local.live_common_tags, {
    Name    = "${local.live_name_prefix}-app-1"
    Service = "opsflow-app-host"
  })

  depends_on = [
    aws_route.live_public_internet,
    aws_iam_role_policy_attachment.live_ec2_ssm,
  ]

  lifecycle {
    # Prevent monthly AMI catalog updates from accidentally replacing
    # the EC2 host during unrelated Terraform deployments. Schedule
    # deliberate AMI rotation in a later deployment phase.
    ignore_changes = [ami, user_data]
  }
}
