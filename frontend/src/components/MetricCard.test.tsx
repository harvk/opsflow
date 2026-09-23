import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MetricCard from "./MetricCard";

describe("MetricCard", () => {
  it.each(["primary", "success", "warning", "danger"] as const)(
    "applies the %s visual tone",
    (accent) => {
      const { container } = render(
        <MetricCard
          label="Metric"
          value="9"
          supportingText="Supporting text"
          accent={accent}
        />,
      );

      expect(container.querySelector(".ops-stat-card")).toHaveClass(
        `ops-stat-card--${accent}`,
      );
    },
  );
});
