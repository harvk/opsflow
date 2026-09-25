# OpsFlow public application DNS.
#
# The public hosted zone already exists in Route 53.
# Terraform must not create another hosted zone.
#
# The existing Application Load Balancer is defined
# in live_alb.tf.

data "aws_route53_zone" "opsflow_public" {
  name         = "opsflow-demo.com."
  private_zone = false
}

resource "aws_route53_record" "opsflow_app" {
  zone_id = data.aws_route53_zone.opsflow_public.zone_id

  name = "app.opsflow-demo.com"
  type = "A"

  alias {
    name                   = aws_lb.live.dns_name
    zone_id                = aws_lb.live.zone_id
    evaluate_target_health = false
  }
}
