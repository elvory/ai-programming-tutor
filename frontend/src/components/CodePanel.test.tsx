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
    onCode: vi.fn(), onLanguage: vi.fn(), onFontSize: vi.fn(), onFullscreen: vi.fn(), onTestHeight: vi.fn(), onNotice: vi.fn() };
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
  it("describes all four languages as unexecuted instead of reporting test success", () => {
    render(<CodePanel {...props("c")} />);
    fireEvent.click(screen.getByRole("button", { name: "测试结果" }));
    expect(screen.getByText("尚未执行代码")).toBeVisible();
    expect(screen.getByText(/当前四种语言均未接入安全执行环境/)).toBeVisible();
    expect(screen.queryByText("Accepted")).not.toBeInTheDocument();
  });
});
