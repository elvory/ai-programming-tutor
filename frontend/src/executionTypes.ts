/** M1 transport only: execution and public-example correctness are independent. */
export type ExecutionStatus = "SUCCESS" | "RUNTIME_ERROR" | "COMPILE_ERROR"
  | "TIME_LIMIT_EXCEEDED" | "OUTPUT_LIMIT_EXCEEDED" | "MEMORY_LIMIT_EXCEEDED" | "SYSTEM_ERROR";

export interface ExecutionRequest {
  problem_id: number;
  language: "python";
  code: string;
  request_id: string;
}

export interface ExecutionSession {
  token: string;
  capabilities: {
    enabled: boolean;
    engine_verified: boolean;
    configuration_valid: boolean;
    languages: string[];
    problem_ids: number[];
    judging_scope: "public_examples";
    official_accepted: false;
    max_concurrent: number;
    note: string;
  };
}

export interface ExecutionCase {
  case_id: string;
  input: unknown;
  expected: unknown;
  actual: unknown;
  passed: boolean;
  status: "passed" | "failed" | "not_run";
  error_type: string | null;
}

export interface ExecutionResult {
  status: ExecutionStatus;
  stdout: string;
  stderr: string;
  exit_code: number | null;
  execution_time_ms: number | null;
  language: "python";
  problem_id: number;
  request_id: string;
  error_message: string | null;
  error_code: string | null;
  cleanup_confirmed: boolean;
  limits: Record<string, unknown>;
  judge: {
    scope: "public_examples";
    suite_version: string;
    passed: number;
    total: number;
    executed: number;
    all_passed: boolean;
    official_accepted: false;
    cases: ExecutionCase[];
  };
}

export interface ExecutionViewState {
  busy: boolean;
  result: ExecutionResult | null;
  error: string;
  stale: boolean;
}
