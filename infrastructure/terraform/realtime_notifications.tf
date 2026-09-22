locals {
  realtime_notifier_function_name = (
    "${local.name_prefix}-realtime-notifier"
  )

  realtime_notifier_zip_path = (
    "${path.module}/../../lambdas/realtime-notifier/dist/realtime-notifier.zip"
  )

  realtime_websocket_api_name = (
    "${local.name_prefix}-realtime-websocket"
  )

  realtime_websocket_channel = "incidents"

  realtime_tags = merge(
    local.messaging_tags,
    {
      Component = "realtime-notifications"
      Phase     = "11.5"
    },
  )
}

resource "aws_dynamodb_table" "websocket_connections" {
  name = "${local.name_prefix}-websocket-connections"

  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "channel"
  range_key = "connection_id"

  attribute {
    name = "channel"
    type = "S"
  }

  attribute {
    name = "connection_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = merge(
    local.realtime_tags,
    {
      TableRole = "websocket-connections"
    },
  )
}

resource "aws_sqs_queue" "realtime_notification_dlq" {
  name = "${local.name_prefix}-realtime-notification-dlq"

  message_retention_seconds = (
    var.realtime_notification_dlq_retention_seconds
  )

  sqs_managed_sse_enabled = true

  tags = merge(
    local.realtime_tags,
    {
      QueueRole = "realtime-dead-letter"
    },
  )
}

resource "aws_sqs_queue" "realtime_notification" {
  name = "${local.name_prefix}-realtime-notification-queue"

  visibility_timeout_seconds = (
    var.realtime_notification_queue_visibility_timeout_seconds
  )

  message_retention_seconds = (
    var.realtime_notification_queue_retention_seconds
  )

  sqs_managed_sse_enabled = true

  tags = merge(
    local.realtime_tags,
    {
      QueueRole = "realtime-primary"
    },
  )
}

resource "aws_sqs_queue_redrive_policy" "realtime_notification" {
  queue_url = (
    aws_sqs_queue
    .realtime_notification
    .id
  )

  redrive_policy = jsonencode({
    deadLetterTargetArn = (
      aws_sqs_queue
      .realtime_notification_dlq
      .arn
    )

    maxReceiveCount = (
      var.realtime_notification_queue_max_receive_count
    )
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "realtime_notification_dlq" {
  queue_url = (
    aws_sqs_queue
    .realtime_notification_dlq
    .id
  )

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"

    sourceQueueArns = [
      aws_sqs_queue
      .realtime_notification
      .arn,
    ]
  })
}

resource "aws_apigatewayv2_api" "realtime" {
  name = (
    local.realtime_websocket_api_name
  )

  protocol_type = "WEBSOCKET"

  route_selection_expression = (
    "$request.body.action"
  )

  tags = local.realtime_tags
}

data "aws_iam_policy_document" "realtime_notifier_assume_role" {
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

resource "aws_iam_role" "realtime_notifier" {
  name = "${local.name_prefix}-realtime-notifier-role"

  assume_role_policy = (
    data
    .aws_iam_policy_document
    .realtime_notifier_assume_role
    .json
  )

  tags = local.realtime_tags
}

data "aws_iam_policy_document" "realtime_notifier_sqs" {
  statement {
    sid    = "ConsumeRealtimeNotificationQueue"
    effect = "Allow"

    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
    ]

    resources = [
      aws_sqs_queue
      .realtime_notification
      .arn,
    ]
  }
}

resource "aws_iam_policy" "realtime_notifier_sqs" {
  name = "${local.name_prefix}-realtime-notifier-sqs-consume"

  description = (
    "Allows the OpsFlow realtime notifier to consume messages from the realtime notification queue."
  )

  policy = (
    data
    .aws_iam_policy_document
    .realtime_notifier_sqs
    .json
  )

  tags = local.realtime_tags
}

resource "aws_iam_role_policy_attachment" "realtime_notifier_sqs" {
  role = (
    aws_iam_role
    .realtime_notifier
    .name
  )

  policy_arn = (
    aws_iam_policy
    .realtime_notifier_sqs
    .arn
  )
}

data "aws_iam_policy_document" "realtime_notifier_connections" {
  statement {
    sid    = "ManageWebSocketConnectionRegistry"
    effect = "Allow"

    actions = [
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
    ]

    resources = [
      aws_dynamodb_table
      .websocket_connections
      .arn,
    ]
  }
}

resource "aws_iam_policy" "realtime_notifier_connections" {
  name = "${local.name_prefix}-realtime-notifier-connections"

  description = (
    "Allows the OpsFlow realtime notifier to manage WebSocket connection-registry records."
  )

  policy = (
    data
    .aws_iam_policy_document
    .realtime_notifier_connections
    .json
  )

  tags = local.realtime_tags
}

resource "aws_iam_role_policy_attachment" "realtime_notifier_connections" {
  role = (
    aws_iam_role
    .realtime_notifier
    .name
  )

  policy_arn = (
    aws_iam_policy
    .realtime_notifier_connections
    .arn
  )
}

data "aws_iam_policy_document" "realtime_notifier_manage_connections" {
  statement {
    sid    = "ManageApiGatewayWebSocketConnections"
    effect = "Allow"

    actions = [
      "execute-api:ManageConnections",
    ]

    resources = [
      (
        "${aws_apigatewayv2_api.realtime.execution_arn}/${var.environment}/POST/@connections/*"
      ),
    ]
  }
}

resource "aws_iam_policy" "realtime_notifier_manage_connections" {
  name = "${local.name_prefix}-realtime-notifier-manage-connections"

  description = (
    "Allows the OpsFlow realtime notifier to deliver messages through the API Gateway WebSocket management API."
  )

  policy = (
    data
    .aws_iam_policy_document
    .realtime_notifier_manage_connections
    .json
  )

  tags = local.realtime_tags
}

resource "aws_iam_role_policy_attachment" "realtime_notifier_manage_connections" {
  role = (
    aws_iam_role
    .realtime_notifier
    .name
  )

  policy_arn = (
    aws_iam_policy
    .realtime_notifier_manage_connections
    .arn
  )
}

resource "aws_cloudwatch_log_group" "realtime_notifier" {
  name = (
    "/aws/lambda/${local.realtime_notifier_function_name}"
  )

  retention_in_days = 14

  tags = local.realtime_tags
}

data "aws_iam_policy_document" "realtime_notifier_logging" {
  statement {
    sid    = "WriteRealtimeNotifierLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "${aws_cloudwatch_log_group.realtime_notifier.arn}:*",
    ]
  }
}

resource "aws_iam_policy" "realtime_notifier_logging" {
  name = "${local.name_prefix}-realtime-notifier-logging"

  description = (
    "Allows the OpsFlow realtime notifier to write to its CloudWatch log group."
  )

  policy = (
    data
    .aws_iam_policy_document
    .realtime_notifier_logging
    .json
  )

  tags = local.realtime_tags
}

resource "aws_iam_role_policy_attachment" "realtime_notifier_logging" {
  role = (
    aws_iam_role
    .realtime_notifier
    .name
  )

  policy_arn = (
    aws_iam_policy
    .realtime_notifier_logging
    .arn
  )
}

resource "aws_lambda_function" "realtime_notifier" {
  function_name = (
    local.realtime_notifier_function_name
  )

  filename = (
    local.realtime_notifier_zip_path
  )

  source_code_hash = filebase64sha256(
    local.realtime_notifier_zip_path
  )

  role = (
    aws_iam_role
    .realtime_notifier
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
      WEBSOCKET_CONNECTIONS_TABLE_NAME = (
        aws_dynamodb_table
        .websocket_connections
        .name
      )

      WEBSOCKET_CONNECTION_TTL_SECONDS = tostring(
        var.realtime_connection_ttl_seconds
      )

      WEBSOCKET_CHANNEL = (
        local.realtime_websocket_channel
      )
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.realtime_notifier_connections,
    aws_iam_role_policy_attachment.realtime_notifier_logging,
    aws_iam_role_policy_attachment.realtime_notifier_manage_connections,
    aws_iam_role_policy_attachment.realtime_notifier_sqs,
    aws_cloudwatch_log_group.realtime_notifier,
  ]

  tags = local.realtime_tags
}

resource "aws_apigatewayv2_integration" "realtime_notifier" {
  api_id = (
    aws_apigatewayv2_api
    .realtime
    .id
  )

  integration_type = "AWS_PROXY"

  connection_type = "INTERNET"

  content_handling_strategy = "CONVERT_TO_TEXT"

  integration_method = "POST"

  integration_uri = (
    aws_lambda_function
    .realtime_notifier
    .invoke_arn
  )

  passthrough_behavior = "WHEN_NO_MATCH"

  description = (
    "Lambda proxy integration for OpsFlow realtime WebSocket lifecycle routes."
  )
}

resource "aws_apigatewayv2_route" "realtime_connect" {
  api_id = (
    aws_apigatewayv2_api
    .realtime
    .id
  )

  route_key = "$connect"

  authorization_type = "NONE"

  target = (
    "integrations/${aws_apigatewayv2_integration.realtime_notifier.id}"
  )
}

resource "aws_apigatewayv2_route" "realtime_disconnect" {
  api_id = (
    aws_apigatewayv2_api
    .realtime
    .id
  )

  route_key = "$disconnect"

  authorization_type = "NONE"

  target = (
    "integrations/${aws_apigatewayv2_integration.realtime_notifier.id}"
  )
}

resource "aws_apigatewayv2_route" "realtime_default" {
  api_id = (
    aws_apigatewayv2_api
    .realtime
    .id
  )

  route_key = "$default"

  authorization_type = "NONE"

  target = (
    "integrations/${aws_apigatewayv2_integration.realtime_notifier.id}"
  )
}

resource "aws_apigatewayv2_deployment" "realtime" {
  api_id = (
    aws_apigatewayv2_api
    .realtime
    .id
  )

  description = (
    "OpsFlow realtime WebSocket deployment."
  )

  triggers = {
    redeployment = sha1(
      jsonencode(
        {
          integration = (
            aws_apigatewayv2_integration
            .realtime_notifier
            .id
          )

          routes = [
            aws_apigatewayv2_route
            .realtime_connect
            .id,

            aws_apigatewayv2_route
            .realtime_disconnect
            .id,

            aws_apigatewayv2_route
            .realtime_default
            .id,
          ]
        },
      )
    )
  }

  depends_on = [
    aws_apigatewayv2_route.realtime_connect,
    aws_apigatewayv2_route.realtime_default,
    aws_apigatewayv2_route.realtime_disconnect,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_apigatewayv2_stage" "realtime" {
  api_id = (
    aws_apigatewayv2_api
    .realtime
    .id
  )

  name = var.environment

  deployment_id = (
    aws_apigatewayv2_deployment
    .realtime
    .id
  )

  description = (
    "OpsFlow ${var.environment} realtime WebSocket stage."
  )

  tags = local.realtime_tags
}

resource "aws_lambda_permission" "realtime_notifier_websocket" {
  statement_id = "AllowApiGatewayWebSocketInvoke"

  action = "lambda:InvokeFunction"

  function_name = (
    aws_lambda_function
    .realtime_notifier
    .function_name
  )

  principal = "apigateway.amazonaws.com"

  source_arn = (
    "${aws_apigatewayv2_api.realtime.execution_arn}/${var.environment}/*"
  )
}

resource "aws_lambda_event_source_mapping" "realtime_notifier_sqs" {
  event_source_arn = (
    aws_sqs_queue
    .realtime_notification
    .arn
  )

  function_name = (
    aws_lambda_function
    .realtime_notifier
    .arn
  )

  enabled = true

  batch_size = 10

  maximum_batching_window_in_seconds = 0

  function_response_types = [
    "ReportBatchItemFailures",
  ]

  depends_on = [
    aws_iam_role_policy_attachment.realtime_notifier_sqs,
  ]
}