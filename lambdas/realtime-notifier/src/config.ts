export const CONNECTIONS_TABLE_NAME_ENV = "WEBSOCKET_CONNECTIONS_TABLE_NAME";

export const CONNECTION_TTL_SECONDS_ENV = "WEBSOCKET_CONNECTION_TTL_SECONDS";

export const WEBSOCKET_CHANNEL_ENV = "WEBSOCKET_CHANNEL";

export interface RealtimeNotifierConfig {
  connectionsTableName: string;

  connectionTtlSeconds: number;

  websocketChannel: string;
}

export class RealtimeNotifierConfigurationError extends Error {
  constructor(message: string) {
    super(message);

    this.name = "RealtimeNotifierConfigurationError";
  }
}

function requireEnvironmentVariable(name: string): string {
  const value = process.env[name]?.trim();

  if (!value) {
    throw new RealtimeNotifierConfigurationError(`${name} must be configured`);
  }

  return value;
}

function requirePositiveInteger(name: string): number {
  const rawValue = requireEnvironmentVariable(name);

  const value = Number(rawValue);

  if (!Number.isInteger(value) || value <= 0) {
    throw new RealtimeNotifierConfigurationError(
      `${name} must be a positive integer`,
    );
  }

  return value;
}

export function loadRealtimeNotifierConfig(): RealtimeNotifierConfig {
  return {
    connectionsTableName: requireEnvironmentVariable(
      CONNECTIONS_TABLE_NAME_ENV,
    ),

    connectionTtlSeconds: requirePositiveInteger(CONNECTION_TTL_SECONDS_ENV),

    websocketChannel: requireEnvironmentVariable(WEBSOCKET_CHANNEL_ENV),
  };
}
