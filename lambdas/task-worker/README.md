# OpsFlow Task Worker

The OpsFlow Task Worker is a Python AWS Lambda function that consumes asynchronous tasks from the primary Amazon SQS task queue.

## Runtime

Target AWS Lambda runtime:

`python3.14`

## Responsibilities

The worker:

- receives batches from Amazon SQS through a Lambda event-source mapping
- parses each SQS message body
- validates each task against the canonical OpsFlow v1 task contract
- dispatches supported task types to task-specific handlers
- emits structured JSON logs
- reports individual failed records through `batchItemFailures`

## Canonical Contract

The source contract remains:

`../../contracts/tasks/task-envelope-v1.schema.json`

The deployment build copies that canonical schema into the Lambda package.

The worker source does not maintain an independent schema copy.

## Delivery Semantics

Amazon SQS and Lambda provide at-least-once processing semantics.

The worker must therefore assume that a task can be delivered more than once.

Phase 11.4 establishes:

- batch-aware processing
- contract validation
- task dispatch
- partial batch failure reporting

Phase 11.5 adds durable business idempotency.

Phase 11.6 expands retry and delivery-guarantee behavior.

## Local Development

Create a Python 3.14 virtual environment:

`py -3.14 -m venv .venv`

Activate it from Git Bash:

`source .venv/Scripts/activate`

Install development dependencies:

`python -m pip install -r requirements-dev.txt`

Run tests:

`python -m pytest`

## Lambda Handler

The Lambda handler will be:

`task_worker.handler.lambda_handler`
