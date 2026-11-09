import { request } from "./api";
import type { ExecutionRequest, ExecutionResult, ExecutionSession } from "./executionTypes";

const statuses = new Set(["SUCCESS", "COMPILE_ERROR", "RUNTIME_ERROR", "TIME_LIMIT_EXCEEDED",
  "OUTPUT_LIMIT_EXCEEDED", "MEMORY_LIMIT_EXCEEDED", "SYSTEM_ERROR"]);
const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const count = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 0;
const nullableText = (value: unknown) => value === null || typeof value === "string";
const invalid = () => new Error("执行服务返回了不完整或不匹配的结果，请重新运行。");

export async function getExecutionSession(): Promise<ExecutionSession> {
  const body = await request<unknown>("/execution/session", { cache: "no-store" });
  if (!object(body) || typeof body.token !== "string" || !body.token.trim() || body.token.length > 256
      || !object(body.capabilities) || typeof body.capabilities.enabled !== "boolean") throw invalid();
  return body as unknown as ExecutionSession;
}

export async function runExecution(payload: ExecutionRequest, token: string): Promise<ExecutionResult> {
  const body = await request<unknown>("/execution/run", {
    method: "POST", headers: { "X-Execution-Token": token }, body: JSON.stringify({
      problem_id: payload.problem_id, language: payload.language, code: payload.code, request_id: payload.request_id,
    }),
  });
  if (!object(body) || !statuses.has(String(body.status)) || body.language !== "python" || body.problem_id !== 1
      || typeof body.request_id !== "string" || body.request_id !== payload.request_id
      || typeof body.stdout !== "string" || typeof body.stderr !== "string"
      || !(body.exit_code === null || Number.isSafeInteger(body.exit_code))
      || !(body.execution_time_ms === null || (typeof body.execution_time_ms === "number"
        && Number.isFinite(body.execution_time_ms) && body.execution_time_ms >= 0))
      || !nullableText(body.error_message) || !nullableText(body.error_code)
      || typeof body.cleanup_confirmed !== "boolean" || !object(body.limits) || !object(body.judge)) throw invalid();
  const judge = body.judge;
  if (judge.scope !== "public_examples" || judge.official_accepted !== false
      || typeof judge.suite_version !== "string" || !count(judge.passed) || !count(judge.total)
      || !count(judge.executed) || judge.total < 1 || judge.passed > judge.executed || judge.executed > judge.total
      || typeof judge.all_passed !== "boolean"
      || judge.all_passed !== (judge.passed === judge.total && judge.executed === judge.total)
      || !Array.isArray(judge.cases) || judge.cases.length !== judge.total || judge.cases.length > 16
      || !judge.cases.every((entry) => object(entry) && typeof entry.case_id === "string"
        && typeof entry.passed === "boolean" && ["passed", "failed", "not_run"].includes(String(entry.status))
        && nullableText(entry.error_type) && "input" in entry && "expected" in entry && "actual" in entry)) throw invalid();
  if (judge.cases.filter((entry) => entry.passed).length !== judge.passed
      || judge.cases.filter((entry) => entry.status !== "not_run").length !== judge.executed
      || judge.cases.some((entry) => entry.passed !== (entry.status === "passed"))) throw invalid();
  if (body.status === "SUCCESS" && !body.cleanup_confirmed) throw invalid();
  return body as unknown as ExecutionResult;
}
