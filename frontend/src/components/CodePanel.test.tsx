import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Language, Problem } from "../types";

vi.mock("../monaco", () => ({}));
vi.mock("@monaco-editor/react", () => ({
  default: ({ language, path, value, onChange }: { language: string; path: string; value: string; onChange: (value: string) => void }) => (
    <textarea aria-label="Monaco adapter" data-language={language} data-path={path} value={value} onChange={(event) => onChange(event.target.value)} />
  ),
}));
import { CodePanel } from "./CodePanel";

const problem = {
  id: 1,
  python_template: "Python template",
  templates: { python: "Python template", java: "Java template", c: "C template", cpp: "C++ template" },
  examples: [{ input: "nums=[1,2]", output: "[0,1]" }],
} as Problem;
function props(language: Language) {
  return { problem, language, code: "draft", fontSize: 14, fullscreen: false, testHeight: 27, storageError: false,
    onCode: vi.fn(), onLanguage: vi.fn(), onRun: vi.fn(), onFontSize: vi.fn(), onFullscreen: vi.fn(), onTestHeight: vi.fn(), onNotice: vi.fn() };
}
afterEach(cleanup);
describe("four-language Monaco adapter", () => {
  it("passes the active language and a distinct model path without changing the draft", () => {
    const initial = props("python");
    const view = render(<CodePanel {...initial} />);
    fireEvent.change(screen.getByLabelText("编程语言"), { target: { value: "java" } });
    expect(initial.onLanguage).toHaveBeenCalledWith("java");
    for (const language of ["python", "java", "c", "cpp"] as const) {
      view.rerender(<CodePanel {...props(language)} />);
      expect(screen.getByLabelText("编程语言")).toHaveValue(language);
      expect(screen.getByLabelText("Monaco adapter")).toHaveAttribute("data-language", language);
      expect(screen.getByLabelText("Monaco adapter").getAttribute("data-path")).toContain(`problem-1-${language}.`);
      expect(screen.getByLabelText("Monaco adapter")).toHaveValue("draft");
    }
  });
  it("resets only the active language to its corresponding template after confirmation", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const current = props("cpp");
    render(<CodePanel {...current} />);
    fireEvent.click(screen.getByRole("button", { name: "重置代码" }));
    expect(current.onCode).toHaveBeenCalledWith("C++ template");
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("C++"));
  });
  it("explains unsupported execution without reporting test success", () => {
    render(<CodePanel {...props("c")} />);
    fireEvent.click(screen.getByRole("button", { name: "测试结果" }));
    expect(screen.getByText("当前语言或题目尚未开放执行")).toBeVisible();
    expect(screen.getByText(/暂仅开放 Python/)).toBeVisible();
    expect(screen.queryByText("Accepted")).not.toBeInTheDocument();
  });
  it("opens only Python Two Sum and prevents empty or busy execution", () => {
    const initial = props("python");
    const view = render(<CodePanel {...initial} />);
    expect(screen.getByRole("button", { name: "运行公开示例" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "运行公开示例" }));
    expect(initial.onRun).toHaveBeenCalledOnce();
    for (const language of ["java", "c", "cpp"] as const) {
      view.rerender(<CodePanel {...props(language)} />);
      expect(screen.getByRole("button", { name: "运行公开示例" })).toBeDisabled();
    }
    view.rerender(<CodePanel {...initial} problem={{ ...problem, id: 217 }} />);
    expect(screen.getByRole("button", { name: "运行公开示例" })).toBeDisabled();
    view.rerender(<CodePanel {...initial} code=" " />);
    expect(screen.getByRole("button", { name: "运行公开示例" })).toBeDisabled();
    view.rerender(<CodePanel {...initial} execution={{ busy: true, result: null, error: "", stale: false }} />);
    const run = screen.getByRole("button", { name: "运行公开示例" });
    expect(run).toBeDisabled();
    fireEvent.click(run);
    expect(initial.onRun).toHaveBeenCalledOnce();
    expect(screen.getByText("正在运行公开示例…")).toBeVisible();
  });
  it("reveals execution failures automatically in the result tab", () => {
    const initial = props("python");
    const view = render(<CodePanel {...initial} />);
    expect(screen.queryByRole("region", { name: "代码执行结果" })).not.toBeInTheDocument();
    view.rerender(<CodePanel {...initial} execution={{ busy: false, result: null, error: "执行服务尚未启用", stale: false }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("执行服务尚未启用");
    expect(screen.getByText("运行未完成")).toBeVisible();
  });
});
