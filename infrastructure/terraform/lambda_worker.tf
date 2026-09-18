locals {
  task_worker_function_name = "${local.name_prefix}-task-worker"

  task_worker_zip_path = (
    "${path.module}/../../lambdas/task-worker/dist/task-worker.zip"
  )
}

data "aws_iam_policy_document" "task_worker_assume_role" {
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

resource "aws_iam_role" "task_worker" {
  name = "${local.name_prefix}-task-worker-role"

  assume_role_policy = (
    data.aws_iam_policy_document.task_worker_assume_role.json
  )

  tags = local.messaging_tags
}

data "aws_iam_policy_document" "task_worker_sqs" {
  statement {
    sid    = "ConsumeOpsFlowTaskQueue"
    effect = "Allow"

    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
    ]

    resources = [
      aws_sqs_queue.task.arn,
    ]
  }
}

resource "aws_iam_policy" "task_worker_sqs" {
  name = "${local.name_prefix}-task-worker-sqs-consume"

  description = (
    "Allows the OpsFlow task worker to consume messages from the primary task queue."
  )

  policy = data.aws_iam_policy_document.task_worker_sqs.json

  tags = local.messaging_tags
}

resource "aws_iam_role_policy_attachment" "task_worker_sqs" {
  role = aws_iam_role.task_worker.name

  policy_arn = aws_iam_policy.task_worker_sqs.arn
}

data "aws_iam_policy_document" "task_worker_logging" {
  statement {
    sid    = "WriteTaskWorkerLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.task_worker.arn}:*",
    ]
  }
}

resource "aws_iam_policy" "task_worker_logging" {
  name = "${local.name_prefix}-task-worker-logging"

  description = (
    "Allows the OpsFlow task worker to write to its CloudWatch log group."
  )

  policy = data.aws_iam_policy_document.task_worker_logging.json

  tags = local.messaging_tags
}

resource "aws_iam_role_policy_attachment" "task_worker_logging" {
  role = aws_iam_role.task_worker.name

  policy_arn = aws_iam_policy.task_worker_logging.arn
}

resource "aws_cloudwatch_log_group" "task_worker" {
  name = "/aws/lambda/${local.task_worker_function_name}"

  retention_in_days = 14

  tags = local.messaging_tags
}

resource "aws_lambda_function" "task_worker" {
  function_name = local.task_worker_function_name

  filename = local.task_worker_zip_path

  source_code_hash = filebase64sha256(
    local.task_worker_zip_path
  )

  role = aws_iam_role.task_worker.arn

  runtime = "python3.14"

  handler = "task_worker.handler.lambda_handler"

  timeout = 30

  memory_size = 256

  architectures = [
    "x86_64",
  ]

  environment {
    variables = {
      TASK_CONTRACT_SCHEMA_PATH = (
        "/var/task/contracts/tasks/task-envelope-v1.schema.json"
      )
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.task_worker_logging,
    aws_iam_role_policy_attachment.task_worker_sqs,
    aws_cloudwatch_log_group.task_worker,
  ]

  tags = local.messaging_tags
}