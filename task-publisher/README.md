# OpsFlow Task Publisher

The Task Publisher is the Node.js serverless ingress component for the OpsFlow asynchronous messaging architecture.

It accepts task publication requests, creates the canonical OpsFlow task envelope, validates the envelope, and publishes the task to Amazon SQS.

## Runtime

Target AWS Lambda runtime:

`nodejs24.x`

The project is written in TypeScript and bundled with esbuild.

## Responsibilities

The publisher is responsible for:

- accepting a task publication request
- generating the task ID
- generating a correlation ID when one is not supplied
- assigning the canonical schema version
- assigning the trusted producer name
- generating the creation timestamp
- preserving the caller's business idempotency key
- validating the completed envelope
- serializing the task
- sending the task to Amazon SQS
- returning HTTP 202 when the task is accepted

The publisher is not responsible for executing the business task.

## Canonical Contract

The publisher validates messages against:

`../contracts/tasks/task-envelope-v1.schema.json`

The schema must not be duplicated inside this application.

## Request Shape

Example request:

```json
{
  "task_type": "incident.notification.requested",
  "idempotency_key": "incident:123:notification:opened",
  "payload": {
    "incident_id": 123,
    "notification_type": "incident-opened"
  }
}
```
