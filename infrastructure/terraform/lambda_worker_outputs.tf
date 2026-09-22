output "task_worker_function_name" {
  description = "Name of the OpsFlow Python task worker Lambda."

  value = (
    aws_lambda_function
    .task_worker
    .function_name
  )
}

output "task_worker_function_arn" {
  description = "ARN of the OpsFlow Python task worker Lambda."

  value = (
    aws_lambda_function
    .task_worker
    .arn
  )
}

output "task_worker_role_arn" {
  description = "Execution role ARN for the OpsFlow task worker."

  value = (
    aws_iam_role
    .task_worker
    .arn
  )
}

output "task_worker_sqs_policy_arn" {
  description = "IAM policy allowing the worker to consume from the task queue."

  value = (
    aws_iam_policy
    .task_worker_sqs
    .arn
  )
}

output "task_worker_execution_state_policy_arn" {
  description = "IAM policy allowing the worker to create Incident task execution-state records."

  value = (
    aws_iam_policy
    .task_worker_execution_state
    .arn
  )
}

output "task_worker_log_group_name" {
  description = "CloudWatch log group for the OpsFlow task worker."

  value = (
    aws_cloudwatch_log_group
    .task_worker
    .name
  )
}