import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";
import { getExecutionSession, runExecution } from "./executionApi";
import type { ExecutionViewState } from "./executionTypes";
import type { Language } from "./types";

interface Source { problem_id: number; language: Language; code: string }

export function useExecution() {
  const [state, setState] = useState<ExecutionViewState>({ busy: false, result: null, error: "", stale: false });
  const token = useRef<string | null>(null);
  const busy = useRef(false);
  const sourceEpoch = useRef(0);
  const generation = useRef(0);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; sourceEpoch.current++; token.current = null; };
  }, []);

  // Explicit intent changes protect A -> B -> A even within a single React batch.
  // This counter is independent of AI's revision and never changes draft storage.
  const invalidate = useCallback(() => {
    sourceEpoch.current++;
    setState((previous) => ({ busy: busy.current, result: null, error: "",
      stale: previous.busy || previous.result !== null || previous.stale }));
  }, []);

  const run = useCallback(async (source: Source) => {
    if (busy.current) return;
    if (source.language !== "python" || source.problem_id !== 1 || !source.code.trim()) {
      setState({ busy: false, result: null, stale: false, error: "当前仅开放 Python 两数之和，请先填写代码。" });
      return;
    }
    busy.current = true; // Synchronous guard, before React updates the button.
    const epoch = sourceEpoch.current;
    const runGeneration = ++generation.current;
    const current = () => mounted.current && sourceEpoch.current === epoch && generation.current === runGeneration;
    setState({ busy: true, result: null, error: "", stale: false });
    try {
      const request_id = crypto.randomUUID();
      const payload = { problem_id: 1, language: "python" as const, code: source.code, request_id };
      let access = token.current;
      if (!access) {
        const session = await getExecutionSession();
        if (!session.capabilities.enabled) throw new Error("本机执行服务尚未启用，请启动支持执行的后端后重试。");
        access = token.current = session.token;
      }
      if (!current()) return;
      // Do not abort an in-flight POST on edit: M1 has no server cancellation.
      // Keep the slot busy until the original request actually settles.
      const result = await runExecution(payload, access);
      if (result.request_id !== request_id || result.problem_id !== payload.problem_id || result.language !== payload.language)
        throw new Error("执行结果与当前请求不匹配，请重新运行。");
      if (current()) setState({ busy: true, result, error: "", stale: false });
    } catch (reason) {
      if (reason instanceof ApiError && (reason.status === 401 || reason.status === 403)) token.current = null;
      if (current()) setState({ busy: true, result: null, stale: false,
        error: reason instanceof Error ? reason.message : "运行未能完成，请重试。" });
    } finally {
      busy.current = false;
      if (mounted.current) setState((previous) => ({ ...previous, busy: false }));
    }
  }, []);
  return { state, run, invalidate };
}
