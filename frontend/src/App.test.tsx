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
import { draftKey } from "./storage";
import type { Bootstrap, DiagnosisResult, Problem } from "./types";

vi.mock("./components/CodePanel", () => ({
  CodePanel: ({
    code,
    onCode,
  }: {
    code: string;
    onCode: (value: string) => void;
  }) => (
    <textarea
      aria-label="test editor"
      value={code}
      onChange={(event) => onCode(event.target.value)}
    />
  ),
}));
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

describe("workbench state across real component boundaries", () => {
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
    await screen.findByText(/已导入 1 道题的草稿/);
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
});
