import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { ExecutionResult, ExecutionStatus, ExecutionViewState } from "../executionTypes";
import { ExecutionResultPanel } from "./ExecutionResultPanel";

const result: ExecutionResult = {
  status: "SUCCESS", stdout: "hello\n", stderr: "", exit_code: 0,
  execution_time_ms: 25.75, language: "python", problem_id: 1, request_id: "run-1",
  error_message: null, error_code: null, cleanup_confirmed: true, limits: {},
  judge: { scope: "public_examples", suite_version: "example-v1", passed: 1, total: 1,
    executed: 1, all_passed: true, official_accepted: false,
    cases: [{ case_id: "example-1", input: { nums: [4, 1, 6], target: 7 }, expected: [1, 2],
      actual: [2, 1], passed: true, status: "passed", error_type: null }] },
};
const idle: ExecutionViewState = { busy: false, result: null, error: "", stale: false };
afterEach(cleanup);

describe("execution result panel", () => {
  it("shows execution and public-example correctness, output and measured time separately", () => {
    render(<ExecutionResultPanel execution={{ ...idle, result }} supported />);
    expect(screen.getByText("运行成功")).toBeVisible();
    expect(screen.getByText("公开示例 1 / 1 通过")).toBeVisible();
    expect(screen.getByText("25.75 ms")).toBeVisible();
    expect(screen.getByText("hello")).toBeVisible();
    expect(screen.getByText("[1,2]")).toBeVisible();
    expect(screen.getByText("[2,1]")).toBeVisible();
    expect(screen.getByText(/不代表 LeetCode 官方通过/)).toBeVisible();
    expect(screen.queryByText("Accepted")).not.toBeInTheDocument();
  });
  it("keeps a wrong answer distinct from an execution failure", () => {
    const wrong: ExecutionResult = { ...result, judge: { ...result.judge, passed: 0, all_passed: false,
      cases: [{ ...result.judge.cases[0], actual: [0, 0], passed: false, status: "failed", error_type: "reused_index" }] } };
    render(<ExecutionResultPanel execution={{ ...idle, result: wrong }} supported />);
    expect(screen.getByText("运行成功")).toBeVisible();
    expect(screen.getByText("公开示例 0 / 1 通过")).toBeVisible();
    expect(screen.getByText("未通过")).toBeVisible();
    expect(screen.queryByText("运行错误")).not.toBeInTheDocument();
  });
  it.each([
    ["COMPILE_ERROR", "语法错误"], ["RUNTIME_ERROR", "运行错误"], ["TIME_LIMIT_EXCEEDED", "运行超时"],
    ["OUTPUT_LIMIT_EXCEEDED", "输出超限"], ["MEMORY_LIMIT_EXCEEDED", "内存超限"], ["SYSTEM_ERROR", "执行服务错误"],
  ] as [ExecutionStatus, string][])("shows %s without inventing timing or example success", (status, label) => {
    render(<ExecutionResultPanel execution={{ ...idle, result: { ...result, status, execution_time_ms: null,
      error_message: "明确的失败信息", stdout: "", stderr: "failure detail",
      judge: { ...result.judge, passed: 0, all_passed: false, executed: 0,
        cases: [{ ...result.judge.cases[0], actual: null, passed: false, status: "not_run" }] } } }} supported />);
    expect(screen.getByText(label)).toBeVisible();
    expect(screen.getByText("未获取")).toBeVisible();
    expect(screen.getByText("明确的失败信息")).toBeVisible();
    expect(screen.getByText("failure detail")).toBeVisible();
    expect(screen.getByText("未运行")).toBeVisible();
    expect(screen.queryByText("0.00 ms")).not.toBeInTheDocument();
  });
  it("hides stale results and explains an outstanding old request", () => {
    const view = render(<ExecutionResultPanel execution={{ ...idle, result, stale: true }} supported />);
    expect(screen.getByText("执行结果已失效")).toBeVisible();
    expect(screen.queryByText("hello")).not.toBeInTheDocument();
    view.rerender(<ExecutionResultPanel execution={{ ...idle, result, stale: true, busy: true }} supported />);
    expect(screen.getByText("等待上次运行结束")).toBeVisible();
    expect(screen.queryByText("25.75 ms")).not.toBeInTheDocument();
  });
  it("never shows candidate results for unsupported language or problems", () => {
    render(<ExecutionResultPanel execution={{ ...idle, result }} supported={false} />);
    expect(screen.getByText("当前语言或题目尚未开放执行")).toBeVisible();
    expect(screen.queryByText("hello")).not.toBeInTheDocument();
    expect(screen.queryByText("25.75 ms")).not.toBeInTheDocument();
  });
  it("shows request failure and renders container output as text", () => {
    const view = render(<ExecutionResultPanel execution={{ ...idle, error: "网络请求失败" }} supported />);
    expect(screen.getByRole("alert")).toHaveTextContent("网络请求失败");
    const payload = "<img src=x onerror=alert(1)>";
    view.rerender(<ExecutionResultPanel execution={{ ...idle, result: { ...result, stdout: payload } }} supported />);
    expect(screen.getByText(payload)).toBeVisible();
    expect(view.container.querySelector("img")).toBeNull();
  });
});
