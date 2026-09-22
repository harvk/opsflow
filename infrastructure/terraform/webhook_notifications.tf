locals {
  webhook_notification_queue_name = replace(
    aws_sqs_queue.realtime_notification.name,
    "realtime-notification-queue",
    "webhook-notification-queue",
  )

  webhook_notification_dlq_name = replace(
    aws_sqs_queue.realtime_notification_dlq.name,
    "realtime-notification-dlq",
    "webhook-notification-dlq",
  )
}


resource "aws_sqs_queue" "webhook_notification_dlq" {
  name = local.webhook_notification_dlq_name

  delay_seconds = (
    aws_sqs_queue.realtime_notification_dlq.delay_seconds
  )

  max_message_size = (
    aws_sqs_queue.realtime_notification_dlq.max_message_size
  )

  message_retention_seconds = (
    aws_sqs_queue
    .realtime_notification_dlq
    .message_retention_seconds
  )

  receive_wait_time_seconds = (
    aws_sqs_queue
    .realtime_notification_dlq
    .receive_wait_time_seconds
  )

  visibility_timeout_seconds = (
    aws_sqs_queue
    .realtime_notification_dlq
    .visibility_timeout_seconds
  )

  /*
   * Use Amazon SQS-managed server-side encryption.
   *
   * Do not configure kms_master_key_id on this resource.
   * The AWS provider treats SSE-SQS and SSE-KMS as
   * mutually exclusive encryption mechanisms.
   */
  sqs_managed_sse_enabled = true

  tags = merge(
    aws_sqs_queue.realtime_notification_dlq.tags,
    {
      Component = "webhook-notifications"
    },
  )
}


resource "aws_sqs_queue" "webhook_notification" {
  name = local.webhook_notification_queue_name

  delay_seconds = (
    aws_sqs_queue.realtime_notification.delay_seconds
  )

  max_message_size = (
    aws_sqs_queue.realtime_notification.max_message_size
  )

  message_retention_seconds = (
    aws_sqs_queue
    .realtime_notification
    .message_retention_seconds
  )

  receive_wait_time_seconds = (
    aws_sqs_queue
    .realtime_notification
    .receive_wait_time_seconds
  )

  visibility_timeout_seconds = (
    aws_sqs_queue
    .realtime_notification
    .visibility_timeout_seconds
  )

  /*
   * Use the same explicit SSE-SQS encryption strategy as
   * the webhook notification DLQ.
   *
   * KMS-specific queue arguments are intentionally absent.
   */
  sqs_managed_sse_enabled = true

  redrive_policy = jsonencode(
    {
      deadLetterTargetArn = (
        aws_sqs_queue
        .webhook_notification_dlq
        .arn
      )

      maxReceiveCount = try(
        jsondecode(
          aws_sqs_queue
          .realtime_notification
          .redrive_policy
        ).maxReceiveCount,
        5,
      )
    }
  )

  tags = merge(
    aws_sqs_queue.realtime_notification.tags,
    {
      Component = "webhook-notifications"
    },
  )
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