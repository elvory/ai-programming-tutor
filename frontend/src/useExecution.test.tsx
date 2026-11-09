import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "./api";
import { getExecutionSession, runExecution } from "./executionApi";
import { useExecution } from "./useExecution";
import type { ExecutionResult } from "./executionTypes";

vi.mock("./executionApi", () => ({ getExecutionSession: vi.fn(), runExecution: vi.fn() }));

const input = { problem_id: 1, language: "python" as const, code: "original source" };
const result = (request_id: string): ExecutionResult => ({
  status: "SUCCESS", stdout: "original output", stderr: "", exit_code: 0,
  execution_time_ms: 42, language: "python", problem_id: 1, request_id,
  error_message: null, error_code: null, cleanup_confirmed: true, limits: {},
  judge: { scope: "public_examples", suite_version: "v1", passed: 1, total: 1, executed: 1,
    all_passed: true, official_accepted: false, cases: [] },
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
beforeEach(() => {
  vi.mocked(getExecutionSession).mockResolvedValue({ token: "memory-only", capabilities: {
    enabled: true, engine_verified: false, configuration_valid: true, languages: ["python"],
    problem_ids: [1], judging_scope: "public_examples", official_accepted: false, max_concurrent: 1, note: "M1",
  } });
  vi.mocked(runExecution).mockImplementation(async (payload) => result(payload.request_id));
});
afterEach(() => vi.resetAllMocks());

it("uses the existing session token and captures code without writing browser storage", async () => {
  const local = vi.spyOn(Storage.prototype, "setItem");
  const hook = renderHook(() => useExecution());
  await act(async () => { await hook.result.current.run(input); });
  expect(hook.result.current.state.result?.judge.all_passed).toBe(true);
  expect(runExecution).toHaveBeenCalledWith(expect.objectContaining(input), "memory-only");
  expect(local).not.toHaveBeenCalled();
  local.mockRestore();
});

it("blocks rapid duplicate clicks while the original request is still pending", async () => {
  const pending = deferred<ExecutionResult>();
  vi.mocked(runExecution).mockReturnValue(pending.promise);
  const hook = renderHook(() => useExecution());
  act(() => { void hook.result.current.run(input); void hook.result.current.run(input); });
  await waitFor(() => expect(runExecution).toHaveBeenCalledTimes(1));
  expect(hook.result.current.state.busy).toBe(true);
  await act(async () => { pending.resolve(result(vi.mocked(runExecution).mock.calls[0][0].request_id)); });
  expect(hook.result.current.state.busy).toBe(false);
});

it("invalidates A to B to A without unlocking or accepting the old result", async () => {
  const pending = deferred<ExecutionResult>();
  vi.mocked(runExecution).mockReturnValue(pending.promise);
  const hook = renderHook(() => useExecution());
  act(() => { void hook.result.current.run(input); });
  await waitFor(() => expect(runExecution).toHaveBeenCalledOnce());
  act(() => { hook.result.current.invalidate(); hook.result.current.invalidate(); });
  expect(hook.result.current.state.busy).toBe(true);
  act(() => { void hook.result.current.run(input); });
  expect(runExecution).toHaveBeenCalledOnce();
  await act(async () => { pending.resolve(result(vi.mocked(runExecution).mock.calls[0][0].request_id)); });
  expect(hook.result.current.state.result).toBeNull();
  expect(hook.result.current.state.stale).toBe(true);
  expect(hook.result.current.state.busy).toBe(false);
});

it("does not post a source invalidated while the session request is pending", async () => {
  const session = deferred<Awaited<ReturnType<typeof getExecutionSession>>>();
  vi.mocked(getExecutionSession).mockReturnValue(session.promise);
  const hook = renderHook(() => useExecution());
  act(() => { void hook.result.current.run(input); hook.result.current.invalidate(); });
  await act(async () => { session.resolve({ token: "memory-only", capabilities: { enabled: true } } as Awaited<ReturnType<typeof getExecutionSession>>); });
  expect(runExecution).not.toHaveBeenCalled();
  expect(hook.result.current.state.busy).toBe(false);
});

it("clears expired tokens and only retries when the user runs again", async () => {
  vi.mocked(runExecution).mockRejectedValueOnce(new ApiError("expired", 403));
  const hook = renderHook(() => useExecution());
  await act(async () => { await hook.result.current.run(input); });
  expect(runExecution).toHaveBeenCalledOnce();
  expect(hook.result.current.state.error).toContain("expired");
  await act(async () => { await hook.result.current.run(input); });
  expect(getExecutionSession).toHaveBeenCalledTimes(2);
  expect(hook.result.current.state.result?.status).toBe("SUCCESS");
});

it("rejects disabled sessions, unsupported inputs and mismatched responses", async () => {
  const hook = renderHook(() => useExecution());
  await act(async () => { await hook.result.current.run({ ...input, language: "java" }); });
  expect(getExecutionSession).not.toHaveBeenCalled();
  vi.mocked(getExecutionSession).mockResolvedValueOnce({ capabilities: { enabled: false } } as Awaited<ReturnType<typeof getExecutionSession>>);
  await act(async () => { await hook.result.current.run(input); });
  expect(runExecution).not.toHaveBeenCalled();
  vi.mocked(runExecution).mockResolvedValueOnce(result("not-the-current-request"));
  await act(async () => { await hook.result.current.run(input); });
  expect(hook.result.current.state.result).toBeNull();
  expect(hook.result.current.state.error).not.toBe("");
});
