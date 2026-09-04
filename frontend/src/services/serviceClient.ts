import { services } from "../data/dashboardData";
import type { Service } from "../types/dashboard";

const MOCK_NETWORK_DELAY_MS = 700;

const SHOULD_SIMULATE_ERROR = false;

function wait(milliseconds: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

export async function getServices(): Promise<Service[]> {
  await wait(MOCK_NETWORK_DELAY_MS);

  if (SHOULD_SIMULATE_ERROR) {
    throw new Error("Unable to load services.");
  }

  return services.map((service) => ({
    ...service,
  }));
}
