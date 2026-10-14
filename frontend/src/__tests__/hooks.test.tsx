import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { makeQueryClient } from "@/components/Providers";
import { setAccessToken } from "@/lib/api";
import { AuthProvider } from "@/lib/auth";
import { keys, useCheckin, useCreateCheckin, useTomorrow } from "@/lib/hooks";

const user = { id: 1, email: "a@b.co", display_name: "Sid", timezone: "Asia/Singapore", onboarding_completed: true, created_at: "2026-10-01T00:00:00Z" };

function json(status: number, body: unknown): Response {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/** Routes fetch calls by method + path. */
function server(routes: Record<string, () => Response>) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url.replace("/api/v1", "")}`;
    const route = routes[key];
    if (!route) throw new Error(`unexpected ${key}`);
    return route();
  });
}

function setup() {
  const qc = makeQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
  return { qc, wrapper };
}

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
});

describe("data hooks", () => {
  it("useTomorrow waits for the session, then loads the forecast state", async () => {
    vi.stubGlobal("fetch", server({
      "POST /auth/refresh": () => json(200, { access_token: "t", token_type: "bearer", expires_in: 900, user }),
      "GET /predictions/tomorrow": () => json(200, { status: "collecting", days_logged: 3, days_needed: 4 }),
    }));
    const { wrapper } = setup();
    const { result } = renderHook(() => useTomorrow(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toMatchObject({ status: "collecting", days_needed: 4 });
  });

  it("does not fetch while signed out", async () => {
    const fetchMock = server({ "POST /auth/refresh": () => json(401, { detail: "no" }) });
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = setup();
    const { result } = renderHook(() => useTomorrow(), { wrapper });
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("useCheckin returns null for a day without a page", async () => {
    vi.stubGlobal("fetch", server({
      "POST /auth/refresh": () => json(200, { access_token: "t", token_type: "bearer", expires_in: 900, user }),
      "GET /checkins/2026-10-14": () => json(404, { detail: "No check-in for that day." }),
    }));
    const { wrapper } = setup();
    const { result } = renderHook(() => useCheckin("2026-10-14"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });

  it("saving a check-in refreshes forecasts and the twin", async () => {
    vi.stubGlobal("fetch", server({
      "POST /auth/refresh": () => json(200, { access_token: "t", token_type: "bearer", expires_in: 900, user }),
      "POST /checkins": () => json(201, { checkin: { date: "2026-10-14" }, support: null }),
    }));
    const { qc, wrapper } = setup();
    qc.setQueryData(keys.tomorrow, { status: "collecting", days_logged: 3, days_needed: 4 });
    qc.setQueryData(keys.twin, { stage: 0 });
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useCreateCheckin(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ mood: 5, energy: 5, stress: 5, anxiety: 5, focus: 5 });
    });
    const invalidated = spy.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(invalidated).toContain(JSON.stringify(["predictions"]));
    expect(invalidated).toContain(JSON.stringify(["twin"]));
    expect(invalidated).toContain(JSON.stringify(["checkins"]));
  });
});
