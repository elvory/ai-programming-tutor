import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./api";
import { getExecutionSession, runExecution } from "./executionApi";
import type { ExecutionRequest, ExecutionResult } from "./executionTypes";

const payload: ExecutionRequest = {
  problem_id: 1,
  language: "python",
  code: "# 中文草稿\nclass Solution:\n    def twoSum(self, nums, target):\n        return []\n",
  request_id: "6d5f0ad9-1054-44f3-a546-c6eea1311ba2",
};
const result = (): ExecutionResult => ({
  status: "SUCCESS", stdout: "中文输出", stderr: "", exit_code: 0,
  execution_time_ms: 21.5, language: "python", problem_id: 1,
  request_id: payload.request_id, error_message: null, error_code: null,
  cleanup_confirmed: true, limits: { memory_mb: 128 },
  judge: {
    scope: "public_examples", suite_version: "two-sum-public-example-v1",
    passed: 0, total: 1, executed: 1, all_passed: false, official_accepted: false,
    cases: [{ case_id: "example-1", input: { nums: [4, 1, 6], target: 7 },
      expected: [1, 2], actual: [], passed: false, status: "failed", error_type: "invalid_index_count" }],
  },
});

function respond(body: unknown, status = 200) {
  const fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300, status, json: async () => body,
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("M1 execution transport", () => {
  it("requests a fresh session without browser storage or token persistence", async () => {
    const store = vi.spyOn(Storage.prototype, "setItem");
    const fetch = respond({ token: "memory-only-session", capabilities: { enabled: true } });
    const session = await getExecutionSession();
    expect(session.token).toBe("memory-only-session");
    expect(fetch).toHaveBeenCalledExactlyOnceWith("/api/execution/session",
      expect.objectContaining({ cache: "no-store" }));
    expect(store).not.toHaveBeenCalled();
  });

  it("preserves the UTF-8 source and sends the token only in the execution header", async () => {
    const store = vi.spyOn(Storage.prototype, "setItem");
    const body = result();
    const fetch = respond(body);
    expect(await runExecution(payload, "memory-only-session")).toEqual(body);
    expect(fetch).toHaveBeenCalledExactlyOnceWith("/api/execution/run", expect.objectContaining({
      method: "POST", body: JSON.stringify(payload), headers: {
        "Content-Type": "application/json", "X-Execution-Token": "memory-only-session",
      },
    }));
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(payload);
    expect(store).not.toHaveBeenCalled();
    expect(fetch.mock.calls[0][0]).not.toContain("memory-only-session");
  });

  it("accepts a disabled session as a capability result rather than fabricating an execution", async () => {
    const fetch = respond({ token: "disabled-session", capabilities: { enabled: false } });
    expect((await getExecutionSession()).capabilities.enabled).toBe(false);
    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch.mock.calls[0][0]).toBe("/api/execution/session");
  });

  it("sends only the four M1 request fields even when a caller object has extra properties", async () => {
    const fetch = respond(result());
    const internalObject = { ...payload, memory_mb: 8192, input: { nums: [1, 2], target: 3 }, image: "other" };
    await runExecution(internalObject, "memory-only-session");
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(payload);
  });

  it("rejects missing, empty and malformed session credentials", async () => {
    const invalidSessions: unknown[] = [null, {}, { token: "", capabilities: { enabled: true } },
      { token: "   ", capabilities: { enabled: true } }, { token: "x".repeat(257), capabilities: { enabled: true } },
      { token: "token", capabilities: { enabled: "true" } }, { token: "token" }];
    for (const body of invalidSessions) {
      respond(body);
      await expect(getExecutionSession()).rejects.toThrow("不完整或不匹配");
    }
  });

  it("rejects malformed successful responses and mismatched execution identities", async () => {
    const mutations: Record<string, unknown>[] = [
      { status: "Accepted" }, { language: "java" }, { problem_id: 217 }, { request_id: "another-request" },
      { stdout: null }, { stderr: 12 }, { execution_time_ms: -1 }, { execution_time_ms: Number.NaN },
      { execution_time_ms: Number.POSITIVE_INFINITY }, { exit_code: 0.5 }, { cleanup_confirmed: false },
      { limits: null }, { error_message: {} }, { error_code: 12 }, { judge: null },
    ];
    for (const change of mutations) {
      respond({ ...result(), ...change });
      await expect(runExecution(payload, "memory-only-session")).rejects.toThrow("不完整或不匹配");
    }
    respond(null);
    await expect(runExecution(payload, "memory-only-session")).rejects.toThrow("不完整或不匹配");
  });

  it("only accepts public-example provenance and coherent required counters", async () => {
    const mutations: Record<string, unknown>[] = [
      { scope: "local_suite" }, { official_accepted: true }, { total: 0 }, { passed: -1 },
      { passed: 2 }, { executed: 2 }, { passed: 1.5 }, { all_passed: true }, { cases: [] },
      { cases: [{ ...result().judge.cases[0], status: "Accepted" }] },
      { cases: [{ ...result().judge.cases[0], error_type: {} }] },
    ];
    for (const change of mutations) {
      respond({ ...result(), judge: { ...result().judge, ...change } });
      await expect(runExecution(payload, "memory-only-session")).rejects.toThrow("不完整或不匹配");
    }
  });

  it("preserves typed runtime failures without turning them into passed examples", async () => {
    const body = result();
    body.status = "TIME_LIMIT_EXCEEDED";
    body.exit_code = 137;
    body.error_code = "TIME_LIMIT_EXCEEDED";
    body.error_message = "代码运行超过墙钟时间上限。";
    body.judge.executed = 0;
    body.judge.cases[0] = { ...body.judge.cases[0], status: "not_run", actual: null, error_type: "not_run" };
    respond(body);
    const response = await runExecution(payload, "memory-only-session");
    expect(response.status).toBe("TIME_LIMIT_EXCEEDED");
    expect(response.judge.all_passed).toBe(false);
  });

  it("rejects contradictory case outcomes instead of showing a false passing summary", async () => {
    const passedSummary = result();
    passedSummary.judge = { ...passedSummary.judge, passed: 1, all_passed: true };
    const mismatchedCase = result();
    mismatchedCase.judge.cases[0].passed = true;
    const executedWithoutCase = result();
    executedWithoutCase.judge.cases[0].status = "not_run";
    for (const body of [passedSummary, mismatchedCase, executedWithoutCase]) {
      respond(body);
      await expect(runExecution(payload, "memory-only-session")).rejects.toThrow("不完整或不匹配");
    }
  });

  it("preserves permission failures and never repeats a run automatically", async () => {
    const fetch = respond({ detail: "执行权限已过期" }, 403);
    await expect(runExecution(payload, "expired-session")).rejects.toEqual(
      expect.objectContaining({ message: "执行权限已过期", status: 403 }));
    expect(fetch).toHaveBeenCalledOnce();
  });

  it("reports network and unreadable JSON failures without leaking transport details or retrying", async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError("synthetic internal path and credentials"));
    vi.stubGlobal("fetch", fetch);
    await expect(runExecution(payload, "memory-only-session")).rejects.toBeInstanceOf(ApiError);
    expect(fetch).toHaveBeenCalledOnce();
    fetch.mockResolvedValueOnce({ ok: true, status: 200, json: async () => { throw new SyntaxError("private parse details"); } });
    await expect(runExecution(payload, "memory-only-session")).rejects.toThrow("不完整或不匹配");
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
