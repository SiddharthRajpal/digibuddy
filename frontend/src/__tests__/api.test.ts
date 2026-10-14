import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, getAccessToken, setAccessToken } from "@/lib/api";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  setAccessToken(null);
});

describe("api client", () => {
  it("sends the bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("abc");
    await apiFetch("/me");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/me");
    expect(init.headers.Authorization).toBe("Bearer abc");
    expect(init.credentials).toBe("include");
  });

  it("refreshes once on 401 and retries with the new token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json(401, { detail: "expired" }))
      .mockResolvedValueOnce(json(200, { access_token: "new", user: {} }))
      .mockResolvedValueOnce(json(200, { id: 1 }));
    vi.stubGlobal("fetch", fetchMock);
    setAccessToken("old");
    const data = await apiFetch<{ id: number }>("/me");
    expect(data.id).toBe(1);
    expect(fetchMock.mock.calls[1]![0]).toBe("/api/v1/auth/refresh");
    expect(fetchMock.mock.calls[2]![1].headers.Authorization).toBe("Bearer new");
    expect(getAccessToken()).toBe("new");
  });

  it("surfaces the API's message in ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(422, { detail: [{ msg: "Value error, Unknown timezone" }] })));
    await expect(apiFetch("/me", { method: "PATCH", body: {} })).rejects.toMatchObject({
      status: 422,
      message: "Unknown timezone",
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(409, { detail: "That email already has an account." })));
    const err = (await apiFetch("/auth/signup", { auth: false }).catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe("That email already has an account.");
  });
});
