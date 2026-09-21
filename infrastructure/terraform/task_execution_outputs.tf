output "incident_task_execution_table_name" {
  description = "Name of the DynamoDB table used for asynchronous Incident task execution state."

  value = (
    aws_dynamodb_table
    .incident_task_execution
    .name
  )
}

output "incident_task_execution_table_arn" {
  description = "ARN of the DynamoDB table used for asynchronous Incident task execution state."

  value = (
    aws_dynamodb_table
    .incident_task_execution
    .arn
  )
}

output "incident_task_execution_status_index_name" {
  description = "GSI used to query Incident task executions by reconciliation status."

  value = (
    local
    .incident_task_execution_status_index_name
  )
}