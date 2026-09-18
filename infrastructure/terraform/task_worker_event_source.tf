resource "aws_lambda_event_source_mapping" "task_worker_sqs" {
  event_source_arn = aws_sqs_queue.task.arn
  function_name    = aws_lambda_function.task_worker.arn

  enabled = true

  batch_size = 10

  maximum_batching_window_in_seconds = 0

  function_response_types = [
    "ReportBatchItemFailures",
  ]

  depends_on = [
    aws_iam_role_policy_attachment.task_worker_sqs,
  ]
}