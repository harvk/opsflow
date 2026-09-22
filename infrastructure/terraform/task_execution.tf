locals {
  incident_task_execution_status_index_name = (
    "status-created-at-index"
  )
}

resource "aws_dynamodb_table" "incident_task_execution" {
  name = "${local.name_prefix}-incident-task-executions"

  billing_mode = "PAY_PER_REQUEST"

  hash_key = "task_id"

  attribute {
    name = "task_id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name = local.incident_task_execution_status_index_name

    hash_key = "status"

    range_key = "created_at"

    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expiration"
    enabled        = true
  }

  tags = merge(
    local.messaging_tags,
    {
      Phase     = "11.5"
      TableRole = "incident-task-execution"
    },
  )
}