output "task_worker_idempotency_table_name" {
  description = "Name of the DynamoDB table used for task-worker idempotency records."
  value       = aws_dynamodb_table.task_worker_idempotency.name
}

output "task_worker_idempotency_table_arn" {
  description = "ARN of the DynamoDB table used for task-worker idempotency records."
  value       = aws_dynamodb_table.task_worker_idempotency.arn
}
