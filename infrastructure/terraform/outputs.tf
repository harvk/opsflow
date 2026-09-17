output "aws_region" {
  description = "AWS Region containing OpsFlow infrastructure."
  value       = var.aws_region
}

output "task_queue_name" {
  description = "Name of the primary OpsFlow task queue."
  value       = aws_sqs_queue.task.name
}

output "task_queue_url" {
  description = "URL of the primary OpsFlow task queue."
  value       = aws_sqs_queue.task.id
}

output "task_queue_arn" {
  description = "ARN of the primary OpsFlow task queue."
  value       = aws_sqs_queue.task.arn
}

output "task_dlq_name" {
  description = "Name of the OpsFlow task dead-letter queue."
  value       = aws_sqs_queue.task_dlq.name
}

output "task_dlq_url" {
  description = "URL of the OpsFlow task dead-letter queue."
  value       = aws_sqs_queue.task_dlq.id
}

output "task_dlq_arn" {
  description = "ARN of the OpsFlow task dead-letter queue."
  value       = aws_sqs_queue.task_dlq.arn
}

output "task_queue_visibility_timeout_seconds" {
  description = "Visibility timeout configured for the primary task queue."
  value       = aws_sqs_queue.task.visibility_timeout_seconds
}

output "task_publisher_sqs_send_policy_arn" {
  description = "IAM policy allowing the Node task publisher to send to the primary task queue."
  value       = aws_iam_policy.task_publisher_sqs_send.arn
}