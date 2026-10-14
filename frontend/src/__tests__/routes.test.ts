import { describe, expect, it } from "vitest";

import { routeRank, transitionBetween } from "@/components/book/routes";

describe("page-turn direction", () => {
  it("turns forward going deeper into the book and back going out", () => {
    expect(transitionBetween("/login", "/")).toBe("forward");
    expect(transitionBetween("/signup", "/onboarding")).toBe("forward");
    expect(transitionBetween("/onboarding", "/")).toBe("forward");
    expect(transitionBetween("/", "/history")).toBe("forward");
    expect(transitionBetween("/history", "/twin")).toBe("forward");
    expect(transitionBetween("/twin", "/checkin/2026-10-15")).toBe("back");
    expect(transitionBetween("/settings", "/login")).toBe("back");
  });

  it("orders check-in pages by date and cross-fades the same page", () => {
    expect(transitionBetween("/checkin/2026-10-14", "/checkin/2026-10-15")).toBe("forward");
    expect(transitionBetween("/checkin/2026-10-15", "/checkin/2026-10-12")).toBe("back");
    expect(transitionBetween("/history", "/history")).toBe("fade");
  });

  it("puts unknown pages at the end of the book", () => {
    expect(routeRank("/nope")).toBeGreaterThan(routeRank("/settings"));
    expect(routeRank("/checkin/2026-10-15")).toBe(routeRank("/checkin"));
  });
});
