output "websocket_connections_table_name" {
  description = "Name of the DynamoDB table storing active OpsFlow WebSocket connections."

  value = (
    aws_dynamodb_table
    .websocket_connections
    .name
  )
}

output "websocket_connections_table_arn" {
  description = "ARN of the DynamoDB table storing active OpsFlow WebSocket connections."

  value = (
    aws_dynamodb_table
    .websocket_connections
    .arn
  )
}

output "realtime_notification_queue_name" {
  description = "Name of the primary OpsFlow realtime notification queue."

  value = (
    aws_sqs_queue
    .realtime_notification
    .name
  )
}

output "realtime_notification_queue_url" {
  description = "URL of the primary OpsFlow realtime notification queue."

  value = (
    aws_sqs_queue
    .realtime_notification
    .id
  )
}

output "realtime_notification_queue_arn" {
  description = "ARN of the primary OpsFlow realtime notification queue."

  value = (
    aws_sqs_queue
    .realtime_notification
    .arn
  )
}

output "realtime_notification_dlq_name" {
  description = "Name of the OpsFlow realtime notification dead-letter queue."

  value = (
    aws_sqs_queue
    .realtime_notification_dlq
    .name
  )
}

output "realtime_notification_dlq_url" {
  description = "URL of the OpsFlow realtime notification dead-letter queue."

  value = (
    aws_sqs_queue
    .realtime_notification_dlq
    .id
  )
}

output "realtime_notification_dlq_arn" {
  description = "ARN of the OpsFlow realtime notification dead-letter queue."

  value = (
    aws_sqs_queue
    .realtime_notification_dlq
    .arn
  )
}

output "realtime_notifier_function_name" {
  description = "Name of the OpsFlow realtime notification Lambda."

  value = (
    aws_lambda_function
    .realtime_notifier
    .function_name
  )
}

output "realtime_notifier_function_arn" {
  description = "ARN of the OpsFlow realtime notification Lambda."

  value = (
    aws_lambda_function
    .realtime_notifier
    .arn
  )
}

output "realtime_notifier_role_arn" {
  description = "Execution-role ARN for the OpsFlow realtime notifier."

  value = (
    aws_iam_role
    .realtime_notifier
    .arn
  )
}

output "realtime_notifier_log_group_name" {
  description = "CloudWatch log group for the OpsFlow realtime notifier."

  value = (
    aws_cloudwatch_log_group
    .realtime_notifier
    .name
  )
}

output "realtime_websocket_api_id" {
  description = "API Gateway v2 identifier for the OpsFlow realtime WebSocket API."

  value = (
    aws_apigatewayv2_api
    .realtime
    .id
  )
}

output "realtime_websocket_api_endpoint" {
  description = "Base WebSocket endpoint for the OpsFlow realtime API."

  value = (
    aws_apigatewayv2_api
    .realtime
    .api_endpoint
  )
}

output "realtime_websocket_stage_name" {
  description = "Deployment stage for the OpsFlow realtime WebSocket API."

  value = (
    aws_apigatewayv2_stage
    .realtime
    .name
  )
}

output "realtime_websocket_url" {
  description = "Stage-qualified WebSocket URL used by OpsFlow clients."

  value = (
    aws_apigatewayv2_stage
    .realtime
    .invoke_url
  )
}

output "realtime_websocket_management_endpoint" {
  description = "HTTPS API Gateway management endpoint used for @connections callbacks."

  value = replace(
    aws_apigatewayv2_stage
    .realtime
    .invoke_url,
    "wss://",
    "https://",
  )
}

output "realtime_notifier_event_source_mapping_uuid" {
  description = "UUID of the SQS event-source mapping for the OpsFlow realtime notifier."

  value = (
    aws_lambda_event_source_mapping
    .realtime_notifier_sqs
    .uuid
  )
}