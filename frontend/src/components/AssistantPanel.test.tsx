import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AssistantPanel } from "./AssistantPanel";
import type { DiagnosisResult, Problem } from "../types";

const problem = { id: 1, title_zh: "测试题目", tags: ["数组"] } as Problem;
const result: DiagnosisResult = {
  diagnosis: {
    error_type: "边界错误",
    knowledge: "索引",
    analysis: "检查边界。",
    hints: ["第一条", "第二条", "第三条"],
    source: "deepseek",
    is_mock: false,
  },
  diagnosis_id: "diagnosis",
  record_id: "record",
  hint_level: 1,
  hint_count: 3,
  warning: null,
};
afterEach(cleanup);
describe("progressive coaching", () => {
  it("keeps unrevealed hints out of the screen and calls the next-step action", () => {
    const onHint = vi.fn();
    render(
      <AssistantPanel
        problem={problem}
        result={result}
        loading={false}
        hintLoading={false}
        error=""
        onHint={onHint}
        onCollapse={vi.fn()}
        onDiagnose={vi.fn()}
      />,
    );
    expect(screen.getByText("第一条")).toBeVisible();
    expect(screen.queryByText("第二条")).not.toBeInTheDocument();
    expect(screen.queryByText("第三条")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /查看下一条提示/ }));
    expect(onHint).toHaveBeenCalledOnce();
  });
  it("keeps all viewed hints visible and completes at level three", () => {
    render(
      <AssistantPanel
        problem={problem}
        result={{ ...result, hint_level: 3 }}
        loading={false}
        hintLoading={false}
        error=""
        onHint={vi.fn()}
        onCollapse={vi.fn()}
        onDiagnose={vi.fn()}
      />,
    );
    ["第一条", "第二条", "第三条"].forEach((hint) =>
      expect(screen.getByText(hint)).toBeVisible(),
    );
    expect(
      screen.getByRole("button", { name: /已展开全部三级提示/ }),
    ).toBeDisabled();
  });
  it("shows explicit failure rather than a diagnosis", () => {
    render(
      <AssistantPanel
        problem={problem}
        result={null}
        loading={false}
        hintLoading={false}
        error="DeepSeek 认证失败"
        onHint={vi.fn()}
        onCollapse={vi.fn()}
        onDiagnose={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("DeepSeek 认证失败");
    expect(screen.queryByText("分析完成")).not.toBeInTheDocument();
  });
});
