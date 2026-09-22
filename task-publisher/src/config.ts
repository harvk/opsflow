export interface PublisherConfig {
  taskQueueUrl: string;
  producerName: string;
}

function requireEnvironmentVariable(
  environment: NodeJS.ProcessEnv,
  name: string,
): string {
  const value = environment[name]?.trim();

  if (!value) {
    throw new Error(`Required environment variable is missing: ${name}`);
  }

  return value;
}

export function loadPublisherConfig(
  environment: NodeJS.ProcessEnv = process.env,
): PublisherConfig {
  return {
    taskQueueUrl: requireEnvironmentVariable(environment, "TASK_QUEUE_URL"),
    producerName:
      environment.TASK_PRODUCER_NAME?.trim() || "opsflow-task-publisher",
  };
}
