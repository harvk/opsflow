# OpsFlow Asynchronous Task Contract

This directory contains the language-neutral message contract used by OpsFlow asynchronous task producers and consumers.

The canonical version 1 task contract is:

`task-envelope-v1.schema.json`

Both Node.js producers and Python consumers must validate task envelopes against the same contract.

## Contract Responsibilities

The producer is responsible for creating a complete valid task envelope before sending the task to the message transport.

Amazon SQS transports the task but does not define the business contract.

The consumer must validate the received envelope before performing a business operation.

A consumer must never assume that a message is unique simply because it has a unique `task_id`.

## Task Identity

`task_id` uniquely identifies a message instance.

A producer retry may produce a second message with a different `task_id` while still referring to the same logical business operation.

For this reason, `task_id` must not be used as the sole business-level deduplication mechanism.

## Idempotency

`idempotency_key` identifies the logical business operation.

Messages representing the same logical operation must use the same idempotency key.

Consumers must use the idempotency key to prevent duplicate business side effects.

Example:

`incident:123:notification:opened`

The idempotency key must not contain secrets, passwords, authentication tokens, private keys, or other sensitive credentials.

## Correlation

`correlation_id` identifies the overall distributed workflow.

All tasks produced as part of the same logical workflow should preserve the same correlation ID.

This allows logs and traces from different services and Lambda invocations to be connected.

## Causation

`causation_id` identifies the task or event that directly caused another message to be created.

A task that begins a new workflow may use:

`null`

A task created because of another task should normally use the parent message's identifier as its causation ID.

## Task Types

Task types use stable lowercase dot-delimited names.

Examples:

`incident.notification.requested`

`incident.escalation.requested`

`service.healthcheck.requested`

Task type names describe the requested operation and should not contain implementation-specific details such as Lambda function names or SQS queue names.

## Payload

`payload` contains task-specific business data.

The envelope contract defines the transport-independent fields that every task requires.

Individual task types may later define their own payload schemas.

For example:

`incident.notification.requested`

may eventually have its own payload contract.

## Metadata

`metadata` is optional.

It may contain non-business execution or tracing information.

Metadata must not contain passwords, bearer tokens, refresh tokens, API secrets, AWS credentials, private keys, or other authentication secrets.

## Versioning

Version 1 uses:

`schema_version = "1.0"`

Backward-incompatible changes require a new contract version.

Existing versioned schemas must not be silently repurposed to mean something materially different.

Future breaking versions should use separate files such as:

`task-envelope-v2.schema.json`

## Transport Independence

The task contract intentionally contains no SQS-specific properties.

Fields such as the following are transport metadata and do not belong in the OpsFlow task envelope:

- SQS message ID
- SQS receipt handle
- SQS approximate receive count
- SQS queue ARN

The Lambda adapter may use those transport values while processing a message, but they remain separate from the business task contract.

## Delivery Semantics

OpsFlow assumes that asynchronous tasks may be delivered more than once.

Consumers must therefore be idempotent.

The architecture targets:

at-least-once delivery + idempotent processing = effectively-once business effects

The system must not claim that transport-level execution is exactly once.
