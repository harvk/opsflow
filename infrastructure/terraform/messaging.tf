locals {
  name_prefix = "${var.project_name}-${var.environment}"

  messaging_tags = {
    Environment = var.environment
    Component   = "event-driven-messaging"
    Phase       = "11.3"
  }
}

resource "aws_sqs_queue" "task_dlq" {
  name = "${local.name_prefix}-task-dlq"

  message_retention_seconds = (
    var.task_dlq_retention_seconds
  )

  sqs_managed_sse_enabled = true

  tags = merge(
    local.messaging_tags,
    {
      QueueRole = "dead-letter"
    },
  )
}

resource "aws_sqs_queue" "task" {
  name = "${local.name_prefix}-task-queue"

  visibility_timeout_seconds = (
    var.task_queue_visibility_timeout_seconds
  )

  message_retention_seconds = (
    var.task_queue_retention_seconds
  )

  sqs_managed_sse_enabled = true

  tags = merge(
    local.messaging_tags,
    {
      QueueRole = "primary"
    },
  )
}

resource "aws_sqs_queue_redrive_policy" "task" {
  queue_url = aws_sqs_queue.task.id

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.task_dlq.arn
    maxReceiveCount     = var.task_queue_max_receive_count
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "task_dlq" {
  queue_url = aws_sqs_queue.task_dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"

    sourceQueueArns = [
      aws_sqs_queue.task.arn,
    ]
  })
}

data "aws_iam_policy_document" "task_publisher_sqs_send" {
  statement {
    sid    = "SendOpsFlowTasks"
    effect = "Allow"

    actions = [
      "sqs:SendMessage",
    ]

    resources = [
      aws_sqs_queue.task.arn,
    ]
  }
}

resource "aws_iam_policy" "task_publisher_sqs_send" {
  name = "${local.name_prefix}-task-publisher-sqs-send"

  description = "Allows the OpsFlow task publisher to send messages only to the primary task queue."

  policy = data.aws_iam_policy_document.task_publisher_sqs_send.json

  tags = local.messaging_tags
}