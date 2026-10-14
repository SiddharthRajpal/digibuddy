import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FeelingsFields } from "@/components/checkin/CheckInFields";
import { toPayload, useCheckInForm } from "@/components/checkin/useCheckInForm";
import { makeQueryClient } from "@/components/Providers";
import { AuthProvider } from "@/lib/auth";

function Harness({ onSaved }: { onSaved: () => void }) {
  const { form, submit } = useCheckInForm("2026-10-14", null, onSaved);
  return (
    <form onSubmit={submit} noValidate>
      <FeelingsFields form={form} />
      <button type="submit">Save</button>
    </form>
  );
}

function renderForm(onSaved = vi.fn()) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url.endsWith("/auth/refresh")
        ? new Response("{}", { status: 401, headers: { "content-type": "application/json" } })
        : new Response(JSON.stringify({ checkin: {}, support: null }), {
            status: 201,
            headers: { "content-type": "application/json" },
          }),
    ),
  );
  render(
    <QueryClientProvider client={makeQueryClient()}>
      <AuthProvider>
        <Harness onSaved={onSaved} />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return onSaved;
}

afterEach(() => vi.unstubAllGlobals());

describe("check-in form", () => {
  it("shows an error for each missing feeling and does not submit", async () => {
    const onSaved = renderForm();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.getAllByRole("alert")).toHaveLength(5));
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("submits once all five feelings are picked", async () => {
    const onSaved = renderForm();
    for (const legend of ["Mood", "Energy", "Stress", "Worry", "Focus"]) {
      const group = screen.getByRole("group", { name: new RegExp(legend) });
      await userEvent.click(group.querySelector('input[value="6"]') as HTMLInputElement);
    }
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("builds the API payload with nulls for empty optional fields", () => {
    const body = toPayload("2026-10-14", {
      mood: 6, energy: 5, stress: 4, anxiety: 3, focus: 7,
      sleep_hours: 7, sleep_quality: null, exercise_minutes: null, outdoor_minutes: null,
      screen_time_hours: null, caffeine_servings: null, alcohol_units: null, meals_eaten: null,
      social_interaction: null, workload: 3, tags: ["exam"], notes: "", custom_metrics: { "2": 1.5, "4": null },
    });
    expect(body).toMatchObject({ date: "2026-10-14", sleep_hours: 7, workload: 3, notes: null, tags: ["exam"] });
    expect(body.custom_metrics).toEqual([{ metric_id: 2, value: 1.5 }]);
  });
});
