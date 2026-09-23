import {
  cleanup,
  fireEvent,
  render,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import RecentActivity from "./RecentActivity";
import type { ActivityItem } from "../types/dashboard";

const ACTIVITY: ActivityItem = {
  id: "90b0df11-af28-4697-a97f-0926cf703676",
  kind: "incident",
  severity: "SEV-2",
  title: "Checkout latency",
  description: "Checkout requests are above the latency objective.",
  occurredAt: "2026-09-23T12:30:00Z",
  reportedByEmail: "operator@example.com",
  status: "Investigating",
  assignee: "Platform Team",
  customerImpacting: true,
};

function buildActivity(index: number): ActivityItem {
  return {
    ...ACTIVITY,
    id: `activity-${index}`,
    title: `Incident ${index}`,
    occurredAt: `2026-09-${String(
      23 - Math.min(index, 20),
    ).padStart(2, "0")}T12:30:00Z`,
  };
}

afterEach(() => {
  cleanup();
});

describe("RecentActivity", () => {
  it(
    "shows mapped severity, provenance, report time, ownership, and impact",
    () => {
      const { container } = render(
        <RecentActivity
          activities={[ACTIVITY]}
          incidentDataAvailable
        />,
      );

      const view = within(container);

      expect(view.getByText("High")).toBeInTheDocument();
      expect(view.getByText(ACTIVITY.title)).toBeInTheDocument();
      expect(view.queryByText(/SEV-2/)).not.toBeInTheDocument();
      expect(
        view.getByText(ACTIVITY.description),
      ).toBeInTheDocument();
      expect(
        view.getByText("operator@example.com"),
      ).toBeInTheDocument();
      expect(
        view.getByText("Investigating"),
      ).toBeInTheDocument();
      expect(
        view.getByText("Platform Team"),
      ).toBeInTheDocument();
      expect(
        view.getByText("Customer impacting"),
      ).toBeInTheDocument();

      const activity = container.querySelector(
        ".ops-activity-item",
      );

      expect(activity).toHaveClass(
        "ops-severity-tone--sev-2",
      );

      const time = container.querySelector("time");

      expect(time).not.toBeNull();
      expect(time).toHaveAttribute(
        "dateTime",
        ACTIVITY.occurredAt,
      );
      expect(time?.textContent).toBeTruthy();
    },
  );

  it(
    "applies the SEV-1 shared tone class for critical activity",
    () => {
      const { container } = render(
        <RecentActivity
          activities={[
            {
              ...ACTIVITY,
              severity: "SEV-1",
            },
          ]}
          incidentDataAvailable
        />,
      );

      const view = within(container);

      expect(
        view.getByText("Critical"),
      ).toBeInTheDocument();

      expect(
        container.querySelector(".ops-activity-item"),
      ).toHaveClass("ops-severity-tone--sev-1");
    },
  );

  it("styles resolved activity as completed and stops marker pulsing", () => {
    const { container } = render(
      <RecentActivity
        activities={[
          {
            ...ACTIVITY,
            id: "resolved-activity",
            status: "Resolved",
          },
        ]}
        incidentDataAvailable
      />,
    );

    const view = within(container);
    const item = container.querySelector(".ops-activity-item");
    const marker = container.querySelector(".ops-activity-marker");
    const status = view.getByText("Resolved");

    expect(item).toHaveClass("ops-activity-item--resolved");
    expect(marker?.closest(".ops-activity-item")).toBe(item);
    expect(status).toHaveClass("ops-activity-status--resolved");
  });

  it(
    "labels historical incidents without reporter provenance safely",
    () => {
      const { container } = render(
        <RecentActivity
          activities={[
            {
              ...ACTIVITY,
              reportedByEmail: null,
            },
          ]}
          incidentDataAvailable
        />,
      );

      const view = within(container);

      expect(
        view.getByText("Legacy / system record"),
      ).toBeInTheDocument();
    },
  );

  it("renders at most four incidents per page", () => {
    const activities = Array.from(
      { length: 7 },
      (_, index) => buildActivity(index + 1),
    );

    const { container } = render(
      <RecentActivity
        activities={activities}
        incidentDataAvailable
      />,
    );

    const view = within(container);

    expect(
      container.querySelectorAll(".ops-activity-item"),
    ).toHaveLength(4);

    expect(
      view.getByText("1 of 2"),
    ).toBeInTheDocument();

    expect(
      view.getByText("Incident 1"),
    ).toBeInTheDocument();

    expect(
      view.getByText("Incident 4"),
    ).toBeInTheDocument();

    expect(
      view.queryByText("Incident 5"),
    ).not.toBeInTheDocument();
  });

  it(
    "supports next, previous, first, and last page navigation",
    () => {
      const activities = Array.from(
        { length: 12 },
        (_, index) => buildActivity(index + 1),
      );

      const { container } = render(
        <RecentActivity
          activities={activities}
          incidentDataAvailable
        />,
      );

      const view = within(container);

      const first = view.getByRole("button", {
        name: "Go to first page",
      });

      const previous = view.getByRole("button", {
        name: "Go to previous page",
      });

      const next = view.getByRole("button", {
        name: "Go to next page",
      });

      const last = view.getByRole("button", {
        name: "Go to last page",
      });

      expect(
        view.getByText("1 of 3"),
      ).toBeInTheDocument();

      expect(first).toBeDisabled();
      expect(previous).toBeDisabled();

      fireEvent.click(next);

      expect(
        view.getByText("2 of 3"),
      ).toBeInTheDocument();

      expect(
        view.getByText("Incident 5"),
      ).toBeInTheDocument();

      expect(
        view.queryByText("Incident 1"),
      ).not.toBeInTheDocument();

      expect(
        container.querySelectorAll(".ops-activity-item"),
      ).toHaveLength(4);

      fireEvent.click(last);

      expect(
        view.getByText("3 of 3"),
      ).toBeInTheDocument();

      expect(
        view.getByText("Incident 9"),
      ).toBeInTheDocument();

      expect(
        view.getByText("Incident 12"),
      ).toBeInTheDocument();

      expect(
        container.querySelectorAll(".ops-activity-item"),
      ).toHaveLength(4);

      expect(next).toBeDisabled();
      expect(last).toBeDisabled();

      fireEvent.click(previous);

      expect(
        view.getByText("2 of 3"),
      ).toBeInTheDocument();

      fireEvent.click(first);

      expect(
        view.getByText("1 of 3"),
      ).toBeInTheDocument();

      expect(
        view.getByText("Incident 1"),
      ).toBeInTheDocument();
    },
  );
});
