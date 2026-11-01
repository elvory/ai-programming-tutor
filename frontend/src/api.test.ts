import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

afterEach(() => vi.unstubAllGlobals());
describe("local Python API boundary", () => {
  it("sends a snapshot unchanged and includes the currently viewed level in hint requests", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ request_id: "one", revision: 7 }),
      });
    vi.stubGlobal("fetch", fetch);
    const snapshot = {
      workspace_id: "workspace",
      problem_id: 1,
      code: "# 中文\npass",
      revision: 7,
    };
    await api.diagnose(snapshot);
    expect(fetch).toHaveBeenCalledWith(
      "/api/diagnoses",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(snapshot),
      }),
    );
    await api.hint("workspace", "diagnosis-one", 7, 1);
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
      workspace_id: "workspace",
      diagnosis_id: "diagnosis-one",
      revision: 7,
      expected_hint_level: 1,
    });
  });
  it("preserves server error messages and status without treating them as a diagnosis", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({
          ok: false,
          status: 502,
          json: async () => ({ detail: "DeepSeek 余额不足" }),
        }),
    );
    await expect(api.bootstrap()).rejects.toEqual(
      expect.objectContaining({ message: "DeepSeek 余额不足", status: 502 }),
    );
  });
  it("reports an unavailable backend clearly and never retries automatically", async () => {
    const fetch = vi
      .fn()
      .mockRejectedValue(new TypeError("internal transport details"));
    vi.stubGlobal("fetch", fetch);
    await expect(api.bootstrap()).rejects.toBeInstanceOf(ApiError);
    expect(fetch).toHaveBeenCalledOnce();
  });
});
