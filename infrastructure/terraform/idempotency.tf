resource "aws_dynamodb_table" "task_worker_idempotency" {
  name = "${local.name_prefix}-task-worker-idempotency"

  billing_mode = "PAY_PER_REQUEST"

  hash_key = "id"

  attribute {
    name = "id"
    type = "S"
  }

  ttl {
    attribute_name = "expiration"
    enabled        = true
  }

  tags = merge(
    local.messaging_tags,
    {
      Phase     = "11.5"
      TableRole = "task-worker-idempotency"
    },
  )
}
