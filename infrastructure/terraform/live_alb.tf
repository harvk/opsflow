# OpsFlow ALB connectivity probe.
#
# The temporary HTTP listener forwards ONLY /healthz.
# All other requests receive HTTP 403.
#
# Production HTTPS routing will be introduced after
# validating an ACM certificate and application origin.

variable "live_alb_probe_client_cidr" {
  description = "Trusted public IPv4 /32 for ALB testing."
  type        = string
}

# --------------------------------------------------
# APPLICATION LOAD BALANCER SECURITY GROUP
# --------------------------------------------------

resource "aws_security_group" "live_alb" {
  name        = "${local.live_name_prefix}-alb-sg"
  description = "OpsFlow restricted ALB connectivity testing"
  vpc_id      = aws_vpc.live.id

  ingress {
    description = "Temporary HTTP health testing"
    protocol    = "tcp"
    from_port   = 80
    to_port     = 80

    cidr_blocks = [
      var.live_alb_probe_client_cidr
    ]
  }

  ingress {
    description = "Public HTTPS application traffic"
    protocol    = "tcp"
    from_port   = 443
    to_port     = 443

    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Forward traffic to EC2 frontend"
    protocol    = "tcp"
    from_port   = 8080
    to_port     = 8080

    security_groups = [
      aws_security_group.live_ec2.id
    ]
  }

  tags = merge(local.live_common_tags, {
    Name = "${local.live_name_prefix}-alb-sg"
  })
}

# --------------------------------------------------
# ALLOW ALB ACCESS TO THE EXISTING EC2 INSTANCE
# --------------------------------------------------

resource "aws_vpc_security_group_ingress_rule" "live_ec2_from_alb" {
  security_group_id = aws_security_group.live_ec2.id

  referenced_security_group_id = aws_security_group.live_alb.id

  description = "Only the ALB can reach the EC2 frontend"

  ip_protocol = "tcp"
  from_port   = 8080
  to_port     = 8080
}

# --------------------------------------------------
# APPLICATION LOAD BALANCER
# --------------------------------------------------

resource "aws_lb" "live" {
  name = "${local.live_name_prefix}-alb"

  internal           = false
  load_balancer_type = "application"

  security_groups = [
    aws_security_group.live_alb.id
  ]

  subnets = aws_subnet.live_public[*].id

  enable_deletion_protection = false

  tags = merge(local.live_common_tags, {
    Name = "${local.live_name_prefix}-alb"
  })

  depends_on = [
    aws_route.live_public_internet
  ]
}

# --------------------------------------------------
# TARGET GROUP
# --------------------------------------------------

resource "aws_lb_target_group" "live_web" {
  name = "${local.live_name_prefix}-web-tg"

  port        = 8080
  protocol    = "HTTP"
  target_type = "instance"

  vpc_id = aws_vpc.live.id

  health_check {
    enabled             = true
    path                = "/healthz"
    protocol            = "HTTP"
    port                = "traffic-port"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    interval            = 15
    timeout             = 5
  }

  tags = merge(local.live_common_tags, {
    Name = "${local.live_name_prefix}-web-tg"
  })
}

# --------------------------------------------------
# REGISTER EXISTING EC2 INSTANCE
# --------------------------------------------------

resource "aws_lb_target_group_attachment" "live_web" {
  target_group_arn = aws_lb_target_group.live_web.arn

  target_id = aws_instance.live_ec2.id

  port = 8080
}

# --------------------------------------------------
# RESTRICTED HTTP LISTENER
# --------------------------------------------------

resource "aws_lb_listener" "live_http_probe" {
  load_balancer_arn = aws_lb.live.arn

  port     = 80
  protocol = "HTTP"

  default_action {
    type = "fixed-response"

    fixed_response {
      content_type = "text/plain"
      message_body = "OpsFlow HTTPS deployment is not enabled"
      status_code  = "403"
    }
  }
}

# --------------------------------------------------
# FORWARD HEALTH REQUESTS ONLY
# --------------------------------------------------

resource "aws_lb_listener_rule" "live_probe_health" {
  listener_arn = aws_lb_listener.live_http_probe.arn

  priority = 10

  action {
    type = "forward"

    target_group_arn = aws_lb_target_group.live_web.arn
  }

  condition {
    path_pattern {
      values = [
        "/healthz"
      ]
    }
  }
}

# --------------------------------------------------
# TERRAFORM OUTPUTS
# --------------------------------------------------

output "live_alb_dns_name" {
  description = "AWS-generated ALB hostname."

  value = aws_lb.live.dns_name
}

output "live_alb_target_group_arn" {
  description = "OpsFlow frontend target group ARN."

  value = aws_lb_target_group.live_web.arn
}

output "live_alb_security_group_id" {
  description = "ALB security group ID."

  value = aws_security_group.live_alb.id
}
