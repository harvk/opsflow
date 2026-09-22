output "task_worker_event_source_mapping_uuid" {
  description = "UUID of the SQS event-source mapping for the OpsFlow task worker."
  value       = aws_lambda_event_source_mapping.task_worker_sqs.uuid
}