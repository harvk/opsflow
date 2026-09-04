import type { Metric, Service } from "../types/dashboard";

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

export const services: Service[] = [
  {
    id: "order-api",
    name: "Order API",
    owner: "Fulfillment",
    status: "Healthy",
    uptime: "99.99%",
    latencyMs: 118,
  },
  {
    id: "inventory-sync",
    name: "Inventory Sync",
    owner: "Inventory",
    status: "Degraded",
    uptime: "99.82%",
    latencyMs: 284,
  },
  {
    id: "notification-worker",
    name: "Notification Worker",
    owner: "Platform",
    status: "Healthy",
    uptime: "99.97%",
    latencyMs: 146,
  },
  {
    id: "payment-webhook",
    name: "Payment Webhook",
    owner: "Payments",
    status: "Critical",
    uptime: "98.91%",
    latencyMs: 621,
  },
];
