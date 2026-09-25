variable "live_acm_certificate_arn" {
  description = "Issued ACM certificate for the OpsFlow HTTPS hostname."
  type        = string
}

resource "aws_lb_listener" "live_https" {
  load_balancer_arn = aws_lb.live.arn

  port            = 443
  protocol        = "HTTPS"
  ssl_policy      = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn = var.live_acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.live_web.arn
  }
}

resource "aws_lb_listener_rule" "live_https_health" {
  listener_arn = aws_lb_listener.live_https.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.live_web.arn
  }

  condition {
    path_pattern {
      values = ["/healthz"]
    }
  }
}