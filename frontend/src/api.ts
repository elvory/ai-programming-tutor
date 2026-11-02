import type {
  Bootstrap,
  DiagnosisResult,
  History,
  Language,
  Problem,
  Snapshot,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(
      "无法连接本地服务，请确认 Python 后端正在运行。草稿已保留。",
      0,
    );
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : null;
    throw new ApiError(
      typeof detail === "string"
        ? detail
        : "操作未完成，请检查输入或稍后重试。",
      response.status,
    );
  }
  return body as T;
}
const post = <T>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body), signal });
export const api = {
  bootstrap: () => request<Bootstrap>("/bootstrap"),
  problems: (
    query: string,
    difficulty: string,
    tags: string[],
    signal?: AbortSignal,
  ) => {
    const params = new URLSearchParams();
    if (query) params.set("query", query);
    if (difficulty) params.set("difficulty", difficulty);
    tags.forEach((tag) => params.append("tags", tag));
    return request<{ problems: Problem[] }>(`/problems?${params}`, { signal });
  },
  history: (problemId?: number) =>
    request<History>(`/history${problemId ? `?problem_id=${problemId}` : ""}`),
  sync: (snapshot: Snapshot) =>
    post<{ revision: number; problem_id: number }>("/workspace/sync", snapshot),
  diagnose: (snapshot: Snapshot, signal?: AbortSignal) =>
    post<{ request_id: string; revision: number }>(
      "/diagnoses",
      snapshot,
      signal,
    ),
  accept: (
    workspace_id: string,
    request_id: string,
    revision: number,
    signal?: AbortSignal,
  ) =>
    post<DiagnosisResult>(
      "/diagnoses/accept",
      { workspace_id, request_id, revision },
      signal,
    ),
  hint: (
    workspace_id: string,
    diagnosis_id: string,
    revision: number,
    expected_hint_level: number,
  ) =>
    post<DiagnosisResult>("/hints", {
      workspace_id,
      diagnosis_id,
      revision,
      expected_hint_level,
    }),
  submission: (snapshot: Snapshot) =>
    post<{ ok: boolean }>("/submissions", {
      ...snapshot,
      submission_id: crypto.randomUUID(),
    }),
  accepted: (problem_id: number, language: Language = "python") =>
    post<{ ok: boolean }>("/accepted", {
      problem_id,
      language,
      confirmed: true,
      event_id: crypto.randomUUID(),
    }),
};
