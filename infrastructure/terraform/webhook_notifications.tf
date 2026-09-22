locals {
  webhook_notifier_function_name = (
    "${local.name_prefix}-webhook-notifier"
  )

  webhook_notifier_zip_path = (
    "${path.module}/../../lambdas/webhook-notifier/dist/webhook-notifier.zip"
  )

  webhook_notifier_secret_name = (
    "${local.name_prefix}-webhook-notifier-config"
  )

  webhook_tags = merge(
    local.realtime_tags,
    {
      Component = "webhook-notifications"
      Phase     = "11.5"
    },
  )
}

resource "aws_sqs_queue" "webhook_notification_dlq" {
  name = "${local.name_prefix}-webhook-notification-dlq"

  message_retention_seconds = (
    var.realtime_notification_dlq_retention_seconds
  )

  sqs_managed_sse_enabled = true

  tags = merge(
    local.webhook_tags,
    {
      QueueRole = "webhook-dead-letter"
    },
  )
}

resource "aws_sqs_queue" "webhook_notification" {
  name = "${local.name_prefix}-webhook-notification-queue"

  visibility_timeout_seconds = (
    var.realtime_notification_queue_visibility_timeout_seconds
  )

  message_retention_seconds = (
    var.realtime_notification_queue_retention_seconds
  )

  sqs_managed_sse_enabled = true

  tags = merge(
    local.webhook_tags,
    {
      QueueRole = "webhook-primary"
    },
  )
}

resource "aws_sqs_queue_redrive_policy" "webhook_notification" {
  queue_url = (
    aws_sqs_queue
    .webhook_notification
    .id
  )

  redrive_policy = jsonencode({
    deadLetterTargetArn = (
      aws_sqs_queue
      .webhook_notification_dlq
      .arn
    )

    maxReceiveCount = (
      var.realtime_notification_queue_max_receive_count
    )
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "webhook_notification_dlq" {
  queue_url = (
    aws_sqs_queue
    .webhook_notification_dlq
    .id
  )

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"

    sourceQueueArns = [
      aws_sqs_queue
      .webhook_notification
      .arn,
    ]
  })
}

resource "aws_secretsmanager_secret" "webhook_notifier_config" {
  name = local.webhook_notifier_secret_name

  description = (
    "Runtime configuration for the OpsFlow webhook notifier. The secret value is populated out-of-band so webhook credentials do not enter Terraform state."
  )

  recovery_window_in_days = 7

  tags = local.webhook_tags
}

data "aws_iam_policy_document" "webhook_notifier_assume_role" {
  statement {
    sid    = "LambdaAssumeRole"
    effect = "Allow"

    principals {
      type = "Service"

      identifiers = [
        "lambda.amazonaws.com",
      ]
    }

    actions = [
      "sts:AssumeRole",
    ]
  }
}

resource "aws_iam_role" "webhook_notifier" {
  name = "${local.name_prefix}-webhook-notifier-role"

  assume_role_policy = (
    data
    .aws_iam_policy_document
    .webhook_notifier_assume_role
    .json
  )

  tags = local.webhook_tags
}

data "aws_iam_policy_document" "webhook_notifier_sqs" {
  statement {
    sid    = "ConsumeWebhookNotificationQueue"
    effect = "Allow"

    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
    ]

    resources = [
      aws_sqs_queue
      .webhook_notification
      .arn,
    ]
  }
}

resource "aws_iam_policy" "webhook_notifier_sqs" {
  name = "${local.name_prefix}-webhook-notifier-sqs-consume"

  description = (
    "Allows the OpsFlow webhook notifier to consume messages from the dedicated webhook notification queue."
  )

  policy = (
    data
    .aws_iam_policy_document
    .webhook_notifier_sqs
    .json
  )

  tags = local.webhook_tags
}

resource "aws_iam_role_policy_attachment" "webhook_notifier_sqs" {
  role = (
    aws_iam_role
    .webhook_notifier
    .name
  )

  policy_arn = (
    aws_iam_policy
    .webhook_notifier_sqs
    .arn
  )
}

data "aws_iam_policy_document" "webhook_notifier_secrets" {
  statement {
    sid    = "ReadWebhookNotifierConfig"
    effect = "Allow"

    actions = [
      "secretsmanager:GetSecretValue",
    ]

    resources = [
      aws_secretsmanager_secret
      .webhook_notifier_config
      .arn,
    ]
  }
}

resource "aws_iam_policy" "webhook_notifier_secrets" {
  name = "${local.name_prefix}-webhook-notifier-secrets"

  description = (
    "Allows the OpsFlow webhook notifier to read its target URL and HMAC signing secret."
  )

  policy = (
    data
    .aws_iam_policy_document
    .webhook_notifier_secrets
    .json
  )

  tags = local.webhook_tags
}

resource "aws_iam_role_policy_attachment" "webhook_notifier_secrets" {
  role = (
    aws_iam_role
    .webhook_notifier
    .name
  )

  policy_arn = (
    aws_iam_policy
    .webhook_notifier_secrets
    .arn
  )
}

resource "aws_cloudwatch_log_group" "webhook_notifier" {
  name = (
    "/aws/lambda/${local.webhook_notifier_function_name}"
  )

  retention_in_days = 14

  tags = local.webhook_tags
}

data "aws_iam_policy_document" "webhook_notifier_logging" {
  statement {
    sid    = "WriteWebhookNotifierLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.webhook_notifier.arn}:*",
    ]
  }
}

resource "aws_iam_policy" "webhook_notifier_logging" {
  name = "${local.name_prefix}-webhook-notifier-logging"

  description = (
    "Allows the OpsFlow webhook notifier to write to its CloudWatch log group."
  )

  policy = (
    data
    .aws_iam_policy_document
    .webhook_notifier_logging
    .json
  )

  tags = local.webhook_tags
}

resource "aws_iam_role_policy_attachment" "webhook_notifier_logging" {
  role = (
    aws_iam_role
    .webhook_notifier
    .name
  )

  policy_arn = (
    aws_iam_policy
    .webhook_notifier_logging
    .arn
  )
}

resource "aws_lambda_function" "webhook_notifier" {
  function_name = (
    local.webhook_notifier_function_name
  )

  filename = (
    local.webhook_notifier_zip_path
  )

  source_code_hash = filebase64sha256(
    local.webhook_notifier_zip_path
  )

  role = (
    aws_iam_role
    .webhook_notifier
    .arn
  )

  runtime = "nodejs24.x"

  handler = "index.handler"

  timeout = 30

  memory_size = 256

  architectures = [
    "x86_64",
  ]

  environment {
    variables = {
      WEBHOOK_CONFIG_SECRET_ARN = (
        aws_secretsmanager_secret
        .webhook_notifier_config
        .arn
      )

      WEBHOOK_HTTP_TIMEOUT_MS = "5000"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.webhook_notifier,
    aws_iam_role_policy_attachment.webhook_notifier_logging,
    aws_iam_role_policy_attachment.webhook_notifier_secrets,
    aws_iam_role_policy_attachment.webhook_notifier_sqs,
  ]

  tags = local.webhook_tags
}

resource "aws_lambda_event_source_mapping" "webhook_notifier_sqs" {
  event_source_arn = (
    aws_sqs_queue
    .webhook_notification
    .arn
  )

  function_name = (
    aws_lambda_function
    .webhook_notifier
    .arn
  )

  /*
   * 4F.5 creates the complete event-source mapping but leaves
   * it disabled. 4F.6 first populates the Secrets Manager
   * secret, proves runtime configuration, and then enables
   * consumption for the live end-to-end delivery test.
   */
  enabled = false

  batch_size = 10

  maximum_batching_window_in_seconds = 0

  function_response_types = [
    "ReportBatchItemFailures",
  ]

  depends_on = [
    aws_iam_role_policy_attachment.webhook_notifier_sqs,
  ]
}

output "webhook_notification_queue_url" {
  description = (
    "URL of the dedicated OpsFlow webhook notification SQS queue."
  )

  value = (
    aws_sqs_queue
    .webhook_notification
    .url
  )
}

output "webhook_notification_queue_arn" {
  description = (
    "ARN of the dedicated OpsFlow webhook notification SQS queue."
  )

  value = (
    aws_sqs_queue
    .webhook_notification
    .arn
  )
}

output "webhook_notification_dlq_url" {
  description = (
    "URL of the OpsFlow webhook notification dead-letter queue."
  )

  value = (
    aws_sqs_queue
    .webhook_notification_dlq
    .url
  )
}

output "webhook_notification_dlq_arn" {
  description = (
    "ARN of the OpsFlow webhook notification dead-letter queue."
  )

  value = (
    aws_sqs_queue
    .webhook_notification_dlq
    .arn
  )
}

output "webhook_notifier_function_name" {
  description = (
    "Name of the OpsFlow webhook notifier Lambda function."
  )

  value = (
    aws_lambda_function
    .webhook_notifier
    .function_name
  )
}

output "webhook_notifier_function_arn" {
  description = (
    "ARN of the OpsFlow webhook notifier Lambda function."
  )

  value = (
    aws_lambda_function
    .webhook_notifier
    .arn
  )
}

output "webhook_notifier_log_group_name" {
  description = (
    "CloudWatch log group used by the OpsFlow webhook notifier."
  )

  value = (
    aws_cloudwatch_log_group
    .webhook_notifier
    .name
  )
}

output "webhook_notifier_secret_arn" {
  description = (
    "ARN of the Secrets Manager container for webhook notifier runtime configuration."
  )

  value = (
    aws_secretsmanager_secret
    .webhook_notifier_config
    .arn
  )
}

output "webhook_notifier_event_source_mapping_uuid" {
  description = (
    "UUID of the dedicated webhook-notifier SQS event-source mapping."
  )

  value = (
    aws_lambda_event_source_mapping
    .webhook_notifier_sqs
    .uuid
  )
}
