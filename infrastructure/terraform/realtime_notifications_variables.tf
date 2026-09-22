variable "realtime_connection_ttl_seconds" {
  description = "TTL assigned to WebSocket connection-registry records."
  type        = number
  default     = 10800

  validation {
    condition = (
      var.realtime_connection_ttl_seconds >= 7200
      && var.realtime_connection_ttl_seconds
      == floor(
        var.realtime_connection_ttl_seconds
      )
    )

    error_message = "realtime_connection_ttl_seconds must be a whole number greater than or equal to 7200."
  }
}

variable "realtime_notification_queue_visibility_timeout_seconds" {
  description = "Visibility timeout for realtime notification messages consumed by the notifier Lambda."
  type        = number
  default     = 180

  validation {
    condition = (
      var.realtime_notification_queue_visibility_timeout_seconds >= 180
      && var.realtime_notification_queue_visibility_timeout_seconds <= 43200
      && var.realtime_notification_queue_visibility_timeout_seconds
      == floor(
        var.realtime_notification_queue_visibility_timeout_seconds
      )
    )

    error_message = "realtime_notification_queue_visibility_timeout_seconds must be a whole number between 180 and 43200."
  }
}

variable "realtime_notification_queue_retention_seconds" {
  description = "Retention period for the primary realtime notification queue."
  type        = number
  default     = 345600

  validation {
    condition = (
      var.realtime_notification_queue_retention_seconds >= 60
      && var.realtime_notification_queue_retention_seconds <= 1209600
      && var.realtime_notification_queue_retention_seconds
      == floor(
        var.realtime_notification_queue_retention_seconds
      )
    )

    error_message = "realtime_notification_queue_retention_seconds must be a whole number between 60 and 1209600."
  }
}

variable "realtime_notification_dlq_retention_seconds" {
  description = "Retention period for failed realtime notification messages."
  type        = number
  default     = 1209600

  validation {
    condition = (
      var.realtime_notification_dlq_retention_seconds >= 60
      && var.realtime_notification_dlq_retention_seconds <= 1209600
      && var.realtime_notification_dlq_retention_seconds
      == floor(
        var.realtime_notification_dlq_retention_seconds
      )
    )

    error_message = "realtime_notification_dlq_retention_seconds must be a whole number between 60 and 1209600."
  }
}

variable "realtime_notification_queue_max_receive_count" {
  description = "Number of unsuccessful receives before a realtime notification moves to the DLQ."
  type        = number
  default     = 5

  validation {
    condition = (
      var.realtime_notification_queue_max_receive_count >= 5
      && var.realtime_notification_queue_max_receive_count <= 1000
      && var.realtime_notification_queue_max_receive_count
      == floor(
        var.realtime_notification_queue_max_receive_count
      )
    )

    error_message = "realtime_notification_queue_max_receive_count must be a whole number between 5 and 1000."
  }
}