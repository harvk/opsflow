import type { ActivityItem, Metric, ServiceDetails } from "../types/dashboard";

export const dashboardMetrics: Metric[] = [
  {
    id: "active-orders",
    label: "Active orders",
    value: "1,284",
    supportingText: "8.4% higher than yesterday",
    accent: "primary",
  },
  {
    id: "open-incidents",
    label: "Open incidents",
    value: "7",
    supportingText: "2 require immediate attention",
    accent: "danger",
  },
  {
    id: "fulfillment-sla",
    label: "Fulfillment SLA",
    value: "98.7%",
    supportingText: "Target: 98.0%",
    accent: "success",
  },
  {
    id: "processing-time",
    label: "Average processing",
    value: "4m 12s",
    supportingText: "18 seconds faster than yesterday",
    accent: "warning",
  },
];

export const services: ServiceDetails[] = [
  {
    id: "order-api",
    name: "Order API",
    owner: "Fulfillment",
    status: "Healthy",
    uptime: "99.99%",
    latencyMs: 118,
    description:
      "Processes order creation, validation, and fulfillment workflow requests.",
    region: "us-east-1",
    version: "2.8.1",
    lastDeployedAt: "2026-09-04T13:42:00Z",
    dependencies: ["Inventory Sync", "Payment Webhook"],
  },
  {
    id: "inventory-sync",
    name: "Inventory Sync",
    owner: "Inventory",
    status: "Degraded",
    uptime: "99.82%",
    latencyMs: 284,
    description:
      "Synchronizes warehouse inventory quantities and allocation state across fulfillment systems.",
    region: "us-east-1",
    version: "4.3.0",
    lastDeployedAt: "2026-09-03T21:15:00Z",
    dependencies: ["Order API"],
  },
  {
    id: "notification-worker",
    name: "Notification Worker",
    owner: "Platform",
    status: "Healthy",
    uptime: "99.97%",
    latencyMs: 146,
    description:
      "Processes asynchronous customer and operational notification jobs.",
    region: "us-east-1",
    version: "1.9.4",
    lastDeployedAt: "2026-09-04T08:05:00Z",
    dependencies: [],
  },
  {
    id: "payment-webhook",
    name: "Payment Webhook",
    owner: "Payments",
    status: "Critical",
    uptime: "98.91%",
    latencyMs: 621,
    description:
      "Receives and processes asynchronous payment-provider transaction events.",
    region: "us-east-1",
    version: "3.1.7",
    lastDeployedAt: "2026-09-02T18:30:00Z",
    dependencies: ["Order API"],
  },
];

export const recentActivity: ActivityItem[] = [
  {
    id: "activity-1",
    kind: "incident",
    title: "Payment Webhook entered critical state",
    description:
      "Latency exceeded the operational threshold for five consecutive minutes.",
    occurredAt: "2026-09-04T16:12:00Z",
  },
  {
    id: "activity-2",
    kind: "deployment",
    title: "Order API v2.8.1 deployed",
    description: "Production deployment completed successfully in us-east-1.",
    occurredAt: "2026-09-04T13:42:00Z",
  },
  {
    id: "activity-3",
    kind: "recovery",
    title: "Inventory Sync latency recovering",
    description: "Average latency returned below 300 milliseconds.",
    occurredAt: "2026-09-04T12:28:00Z",
  },
  {
    id: "activity-4",
    kind: "order",
    title: "Order volume increased",
    description:
      "Active order volume is 8.4% higher than the previous operating period.",
    occurredAt: "2026-09-04T10:15:00Z",
  },
];
