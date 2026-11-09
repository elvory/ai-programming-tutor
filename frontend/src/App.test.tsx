import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { api } from "./api";
import { getExecutionSession, runExecution } from "./executionApi";
import type { ExecutionResult, ExecutionViewState } from "./executionTypes";
import { draftKey } from "./storage";
import type { Bootstrap, DiagnosisResult, Problem } from "./types";

vi.mock("./components/CodePanel", () => ({
  CodePanel: ({
    code,
    onCode,
    language,
    onLanguage,
    execution,
    onRun,
  }: {
    code: string;
    onCode: (value: string) => void;
    language: string;
    onLanguage: (value: "python" | "java" | "c" | "cpp") => void;
    execution?: ExecutionViewState;
    onRun?: () => void;
  }) => (
    <>
    <select aria-label="编程语言" value={language} onChange={(event) => onLanguage(event.target.value as "python" | "java" | "c" | "cpp")}>
      <option value="python">Python 3</option><option value="java">Java</option><option value="c">C</option><option value="cpp">C++</option>
    </select>
    <textarea
      aria-label="test editor"
      value={code}
      onChange={(event) => onCode(event.target.value)}
    />
    <button aria-label="test run" disabled={execution?.busy} onClick={onRun}>Run</button>
    {execution?.result && <output data-testid="test-execution-output">{execution.result.stdout}</output>}
    </>
  ),
}));
vi.mock("./executionApi", () => ({ getExecutionSession: vi.fn(), runExecution: vi.fn() }));
vi.mock("./api", async () => {
  const actual = await vi.importActual<typeof import("./api")>("./api");
  return {
    ...actual,
    api: {
      bootstrap: vi.fn(),
      sync: vi.fn(),
      diagnose: vi.fn(),
      accept: vi.fn(),
      hint: vi.fn(),
      history: vi.fn(),
      problems: vi.fn(),
      submission: vi.fn(),
      accepted: vi.fn(),
    },
  };
});
const first: Problem = {
  id: 1,
  title_zh: "测试一",
  title_en: "First",
  tags: ["数组"],
  stage: 1,
  summary: "摘要",
  difficulty: "Easy",
  python_template: "first template",
  templates: { python: "first template", java: "first Java template", c: "first C template", cpp: "first CPP template" },
  examples: [{ input: "one", output: "two" }],
  constraints: ["约束"],
  official_url: "https://leetcode.cn/problems/two-sum/",
  slug: "two-sum",
  source_note: "来源",
};
const second: Problem = {
  ...first,
  id: 20,
  title_zh: "测试二",
  python_template: "second template",
  templates: { python: "second template", java: "second Java template", c: "second C template", cpp: "second CPP template" },
};
const bootstrap: Bootstrap = {
  problems: [first, second],
  route: [{ id: 1, title: "数组", problems: [first, second] }],
  summary: {
    total_submissions: 0,
    completed_problems: 0,
    streak_days: 0,
    recommended_stage: 1,
    completed_ids: [],
    counts_by_day: {},
  },
  heatmap: [],
};
const diagnosis: DiagnosisResult = {
  diagnosis: {
    error_type: "示例错误",
    knowledge: "数组",
    analysis: "分析",
    hints: ["first hint"],
    source: "deepseek",
    is_mock: false,
  },
  diagnosis_id: "diagnosis-one",
  record_id: "record-one",
  hint_level: 1,
  hint_count: 3,
  warning: null,
};
beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.mocked(api.bootstrap).mockResolvedValue(bootstrap);
  vi.mocked(api.sync).mockResolvedValue({ revision: 1, problem_id: 1 });
  vi.mocked(api.history).mockResolvedValue({ records: [], activities: [] });
  vi.mocked(api.accept).mockResolvedValue(diagnosis);
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const executionResult = (request_id: string): ExecutionResult => ({
  status: "SUCCESS", stdout: "fresh execution output", stderr: "", exit_code: 0,
  execution_time_ms: 30, language: "python", problem_id: 1, request_id,
  cleanup_confirmed: true, error_message: null, error_code: null, limits: {},
  judge: { scope: "public_examples", suite_version: "v1", passed: 1, total: 1,
    executed: 1, all_passed: true, official_accepted: false, cases: [] },
});

describe("execution integration without changing AI or drafts", () => {
  beforeEach(() => {
    vi.mocked(getExecutionSession).mockResolvedValue({ token: "memory-token", capabilities: {
      enabled: true, engine_verified: false, configuration_valid: true, languages: ["python"],
      problem_ids: [1], judging_scope: "public_examples", official_accepted: false, max_concurrent: 1, note: "M1",
    } });
    vi.mocked(runExecution).mockImplementation(async (payload) => executionResult(payload.request_id));
  });

  it("runs the current editor without clearing AI hints, changing drafts or recording activity", async () => {
    vi.mocked(api.diagnose).mockResolvedValue({ request_id: "candidate", revision: 2 });
    render(<App />);
    const editor = await screen.findByRole("textbox", { name: "test editor" });
    fireEvent.change(editor, { target: { value: "current Python source" } });
    fireEvent.click(screen.getByRole("button", { name: "AI 诊断" }));
    await screen.findByText("first hint");
    const syncCalls = vi.mocked(api.sync).mock.calls.length;
    const saved = JSON.stringify({ ...localStorage });
    fireEvent.click(screen.getByRole("button", { name: "test run" }));
    await screen.findByTestId("test-execution-output");
    expect(runExecution).toHaveBeenCalledWith(expect.objectContaining({ code: "current Python source", language: "python", problem_id: 1 }), "memory-token");
    expect(screen.getByText("first hint")).toBeInTheDocument();
    expect(vi.mocked(api.sync).mock.calls.length).toBe(syncCalls);
    expect(JSON.stringify({ ...localStorage })).toBe(saved);
    expect(api.submission).not.toHaveBeenCalled();
    expect(api.accepted).not.toHaveBeenCalled();
  });

  it.each(["edit", "language", "problem"])("isolates late results after %s changes, even when returning to the original source", async (change) => {
    let finish!: (value: ExecutionResult) => void;
    vi.mocked(runExecution).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    render(<App />);
    const editor = await screen.findByRole("textbox", { name: "test editor" });
    fireEvent.click(screen.getByRole("button", { name: "test run" }));
    await waitFor(() => expect(runExecution).toHaveBeenCalledOnce());
    if (change === "edit") {
      fireEvent.change(editor, { target: { value: "changed source" } });
      fireEvent.change(editor, { target: { value: "first template" } });
    } else if (change === "language") {
      fireEvent.change(screen.getByLabelText("编程语言"), { target: { value: "java" } });
      fireEvent.change(screen.getByLabelText("编程语言"), { target: { value: "python" } });
    } else {
      fireEvent.click(screen.getByRole("button", { name: "下一题" }));
      fireEvent.click(screen.getByRole("button", { name: "上一题" }));
    }
    expect(screen.getByRole("button", { name: "test run" })).toBeDisabled();
    await act(async () => { finish(executionResult(vi.mocked(runExecution).mock.calls[0][0].request_id)); });
    expect(screen.queryByTestId("test-execution-output")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "test run" })).not.toBeDisabled();
  });
});

describe("workbench state across real component boundaries", () => {
  it("preserves four language drafts across switching problem and remounting", async () => {
    const view = render(<App />);
    const editor = await screen.findByRole("textbox", { name: "test editor" });
    const languages = ["python", "java", "c", "cpp"];
    for (const language of languages) {
      fireEvent.change(screen.getByLabelText("编程语言"), { target: { value: language } });
      fireEvent.change(editor, { target: { value: `${language} draft` } });
    }
    fireEvent.click(screen.getByRole("button", { name: "下一题" }));
    expect(editor).toHaveValue("second CPP template");
    fireEvent.click(screen.getByRole("button", { name: "上一题" }));
    for (const language of languages) {
      fireEvent.change(screen.getByLabelText("编程语言"), { target: { value: language } });
      expect(editor).toHaveValue(`${language} draft`);
    }
    view.unmount(); render(<App />);
    await screen.findByRole("textbox", { name: "test editor" });
    for (const language of languages) {
      fireEvent.change(screen.getByLabelText("编程语言"), { target: { value: language } });
      expect(screen.getByRole("textbox", { name: "test editor" })).toHaveValue(`${language} draft`);
    }
  });
  it("restores independent drafts, including an empty draft, across problem changes and refresh", async () => {
    const view = render(<App />);
    const editor = await screen.findByRole("textbox", { name: "test editor" });
    fireEvent.change(editor, { target: { value: "" } });
    expect(localStorage.getItem(draftKey(1))).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "下一题" }));
    expect(editor).toHaveValue("second template");
    fireEvent.change(editor, { target: { value: "my second draft" } });
    fireEvent.click(screen.getByRole("button", { name: "上一题" }));
    expect(editor).toHaveValue("");
    view.unmount();
    render(<App />);
    expect(
      await screen.findByRole("textbox", { name: "test editor" }),
    ).toHaveValue("");
  });
  it("retains drafts in the running tab even when browser persistence is unavailable", async () => {
    render(<App />);
    const editor = await screen.findByRole("textbox", { name: "test editor" });
    const write = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("storage disabled");
      });
    fireEvent.change(editor, { target: { value: "in-memory draft" } });
    fireEvent.click(screen.getByRole("button", { name: "下一题" }));
    fireEvent.click(screen.getByRole("button", { name: "上一题" }));
    expect(editor).toHaveValue("in-memory draft");
    write.mockRestore();
  });
  it("keeps a newer unsaved draft over an older persisted draft after switching away and back", async () => {
    localStorage.setItem(draftKey(1), "persisted draft A");
    render(<App />);
    const editor = await screen.findByRole("textbox", { name: "test editor" });
    const originalSetItem = Storage.prototype.setItem;
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (
      this: Storage,
      key,
      value,
    ) {
      if (key === draftKey(1))
        throw new DOMException("quota exceeded", "QuotaExceededError");
      originalSetItem.call(this, key, value);
    });
    fireEvent.change(editor, { target: { value: "newer unsaved draft B" } });
    expect(localStorage.getItem(draftKey(1))).toBe("persisted draft A");
    fireEvent.click(screen.getByRole("button", { name: "下一题" }));
    fireEvent.click(screen.getByRole("button", { name: "上一题" }));
    expect(editor).toHaveValue("newer unsaved draft B");
    expect(screen.getByRole("alert")).toHaveTextContent("浏览器存储不可用");
  });
  it("does not restore stale persisted code over an unsaved draft when importing another problem", async () => {
    localStorage.setItem(draftKey(1), "persisted draft A");
    render(<App />);
    const editor = await screen.findByRole("textbox", { name: "test editor" });
    const originalSetItem = Storage.prototype.setItem;
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (
      this: Storage,
      key,
      value,
    ) {
      if (key === draftKey(1))
        throw new DOMException("quota exceeded", "QuotaExceededError");
      originalSetItem.call(this, key, value);
    });
    fireEvent.change(editor, { target: { value: "newer unsaved draft B" } });
    fireEvent.click(screen.getByRole("button", { name: "打开工作台设置" }));
    const text = JSON.stringify({
      schema_version: 1,
      drafts: { "20": "imported other draft" },
    });
    const file = new File([text], "drafts.json", { type: "application/json" });
    Object.defineProperty(file, "text", { value: async () => text });
    fireEvent.change(screen.getByLabelText("导入草稿文件"), {
      target: { files: [file] },
    });
    await screen.findByText(/已导入 1 份草稿/);
    expect(editor).toHaveValue("newer unsaved draft B");
    expect(localStorage.getItem(draftKey(20))).toBe("imported other draft");
    expect(localStorage.getItem(draftKey(1))).toBe("persisted draft A");
  });
  it("restores an imported draft for a previously visited but untouched problem", async () => {
    render(<App />);
    const editor = await screen.findByRole("textbox", { name: "test editor" });
    fireEvent.click(screen.getByRole("button", { name: "下一题" }));
    localStorage.setItem(draftKey(1), "imported session draft");
    fireEvent.click(screen.getByRole("button", { name: "上一题" }));
    expect(editor).toHaveValue("imported session draft");
  });
  it("discards a slow diagnosis after an edit and does not accept it into history", async () => {
    let resolve!: (value: { request_id: string; revision: number }) => void;
    vi.mocked(api.diagnose).mockReturnValue(
      new Promise((done) => {
        resolve = done;
      }),
    );
    render(<App />);
    const editor = await screen.findByRole("textbox", { name: "test editor" });
    fireEvent.click(screen.getByRole("button", { name: "AI 诊断" }));
    await waitFor(() => expect(api.diagnose).toHaveBeenCalledOnce());
    fireEvent.change(editor, { target: { value: "newer code" } });
    await act(async () =>
      resolve({ request_id: "stale-request", revision: 2 }),
    );
    expect(api.accept).not.toHaveBeenCalled();
    expect(editor).toHaveValue("newer code");
    expect(screen.queryByText("first hint")).not.toBeInTheDocument();
  });
  it("uses one model request and reveals subsequent hints through the existing hint endpoint", async () => {
    vi.mocked(api.diagnose).mockResolvedValue({
      request_id: "request-one",
      revision: 2,
    });
    vi.mocked(api.hint).mockResolvedValue({
      ...diagnosis,
      hint_level: 2,
      diagnosis: {
        ...diagnosis.diagnosis,
        hints: ["first hint", "second hint"],
      },
    });
    render(<App />);
    await screen.findByRole("textbox", { name: "test editor" });
    fireEvent.click(screen.getByRole("button", { name: "AI 诊断" }));
    expect(await screen.findByText("first hint")).toBeVisible();
    expect(screen.queryByText("second hint")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /查看下一条提示/ }));
    expect(await screen.findByText("second hint")).toBeVisible();
    expect(api.diagnose).toHaveBeenCalledOnce();
    expect(api.hint).toHaveBeenCalledWith(
      expect.any(String),
      "diagnosis-one",
      expect.any(Number),
      1,
    );
  });
  it("sends the selected language for diagnosis, local submission and reported acceptance", async () => {
    vi.mocked(api.diagnose).mockResolvedValue({ request_id: "java-request", revision: 3 });
    vi.mocked(api.submission).mockResolvedValue({ ok: true });
    vi.mocked(api.accepted).mockResolvedValue({ ok: true });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<App />);
    await screen.findByRole("textbox", { name: "test editor" });
    fireEvent.change(screen.getByLabelText("编程语言"), { target: { value: "java" } });
    fireEvent.click(screen.getByRole("button", { name: "AI 诊断" }));
    await screen.findByText("first hint");
    expect(api.diagnose).toHaveBeenCalledWith(expect.objectContaining({ language: "java", code: "first Java template" }), expect.any(AbortSignal));
    fireEvent.click(screen.getByRole("button", { name: "记录提交" }));
    await waitFor(() => expect(api.submission).toHaveBeenCalledWith(expect.objectContaining({ language: "java" })));
    fireEvent.click(screen.getByRole("button", { name: "标记 LeetCode 已通过" }));
    await waitFor(() => expect(api.accepted).toHaveBeenCalledWith(1, "java"));
  });
  it("discards a slow response after changing language even when the source code is identical", async () => {
    localStorage.setItem(draftKey(1, "java"), "first template");
    let resolve!: (value: { request_id: string; revision: number }) => void;
    vi.mocked(api.diagnose).mockReturnValue(new Promise((done) => { resolve = done; }));
    render(<App />);
    await screen.findByRole("textbox", { name: "test editor" });
    fireEvent.click(screen.getByRole("button", { name: "AI 诊断" }));
    await waitFor(() => expect(api.diagnose).toHaveBeenCalledOnce());
    fireEvent.change(screen.getByLabelText("编程语言"), { target: { value: "java" } });
    await act(async () => resolve({ request_id: "old-python", revision: 2 }));
    expect(api.accept).not.toHaveBeenCalled();
    expect(screen.queryByText("first hint")).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "test editor" })).toHaveValue("first template");
  });
  it("keeps an unsaved Java buffer isolated from Python and a schema2 import", async () => {
    localStorage.setItem(draftKey(1, "java"), "old Java");
    render(<App />);
    const editor = await screen.findByRole("textbox", { name: "test editor" });
    fireEvent.change(screen.getByLabelText("编程语言"), { target: { value: "java" } });
    const originalSetItem = Storage.prototype.setItem;
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (this: Storage, key, value) {
      if (key === draftKey(1, "java")) throw new DOMException("quota", "QuotaExceededError");
      originalSetItem.call(this, key, value);
    });
    fireEvent.change(editor, { target: { value: "unsaved Java" } });
    fireEvent.change(screen.getByLabelText("编程语言"), { target: { value: "python" } });
    expect(editor).toHaveValue("first template");
    fireEvent.change(screen.getByLabelText("编程语言"), { target: { value: "java" } });
    expect(editor).toHaveValue("unsaved Java");
    fireEvent.click(screen.getByRole("button", { name: "打开工作台设置" }));
    const text = JSON.stringify({ schema_version: 2, drafts: { "1": { java: "import Java" }, "20": { c: "import C" } } });
    const file = new File([text], "drafts.json", { type: "application/json" });
    Object.defineProperty(file, "text", { value: async () => text });
    fireEvent.change(screen.getByLabelText("导入草稿文件"), { target: { files: [file] } });
    await screen.findByText(/已导入 1 份草稿；1 份/);
    expect(editor).toHaveValue("unsaved Java");
    expect(localStorage.getItem(draftKey(1, "java"))).toBe("old Java");
    expect(localStorage.getItem(draftKey(20, "c"))).toBe("import C");
  });
});
