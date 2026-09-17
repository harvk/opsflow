variable "aws_region" {
  description = "AWS Region used for OpsFlow development infrastructure."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project identifier used for AWS resource names."
  type        = string
  default     = "opsflow"

  validation {
    condition = (
      length(var.project_name) >= 2
      && length(var.project_name) <= 30
      && can(regex("^[a-z][a-z0-9-]*$", var.project_name))
    )

    error_message = "project_name must start with a lowercase letter and contain only lowercase letters, digits, and hyphens."
  }
}

variable "environment" {
  description = "Deployment environment for OpsFlow AWS resources."
  type        = string
  default     = "dev"

  validation {
    condition = contains(
      [
        "dev",
        "test",
        "staging",
        "prod",
      ],
      var.environment,
    )

    error_message = "environment must be one of: dev, test, staging, prod."
  }
}

variable "task_queue_visibility_timeout_seconds" {
  description = "Visibility timeout for the primary OpsFlow task queue."
  type        = number
  default     = 180

  validation {
    condition = (
      var.task_queue_visibility_timeout_seconds >= 0
      && var.task_queue_visibility_timeout_seconds <= 43200
    )

    error_message = "task_queue_visibility_timeout_seconds must be between 0 and 43200."
  }
}

variable "task_queue_retention_seconds" {
  description = "Message retention period for the primary OpsFlow task queue."
  type        = number
  default     = 345600

  validation {
    condition = (
      var.task_queue_retention_seconds >= 60
      && var.task_queue_retention_seconds <= 1209600
    )

    error_message = "task_queue_retention_seconds must be between 60 and 1209600."
  }
}

variable "task_dlq_retention_seconds" {
  description = "Message retention period for the OpsFlow task dead-letter queue."
  type        = number
  default     = 1209600

  validation {
    condition = (
      var.task_dlq_retention_seconds >= 60
      && var.task_dlq_retention_seconds <= 1209600
    )

    error_message = "task_dlq_retention_seconds must be between 60 and 1209600."
  }
}

variable "task_queue_max_receive_count" {
  description = "Number of unsuccessful receives before SQS moves a task to the dead-letter queue."
  type        = number
  default     = 5

  validation {
    condition = (
      var.task_queue_max_receive_count >= 1
      && var.task_queue_max_receive_count <= 1000
    )

    error_message = "task_queue_max_receive_count must be between 1 and 1000."
  }
}