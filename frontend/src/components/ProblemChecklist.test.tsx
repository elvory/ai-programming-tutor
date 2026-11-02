import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProblemChecklist } from "./ProblemChecklist";
import type { Bootstrap, Problem } from "../types";

afterEach(cleanup);
const first = { id: 1, title_zh: "两数之和", difficulty: "Easy" } as Problem;
const second = { id: 217, title_zh: "存在重复元素", difficulty: "Easy" } as Problem;
const third = { id: 3, title_zh: "无重复字符的最长子串", difficulty: "Medium" } as Problem;
const data = {
  problems: [first, second, third],
  route: [
    { id: 1, title: "数组与哈希表", problems: [first, second] },
    { id: 2, title: "双指针与滑动窗口", problems: [third] },
  ],
  summary: { recommended_stage: 1, completed_ids: [1] },
} as Bootstrap;

describe("recommended stage checklist", () => {
  it("defaults to the recommended real stage and shows unique completion status", () => {
    render(<ProblemChecklist data={data} onSelect={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "推荐题单" })).toBeVisible();
    expect(screen.getByLabelText("题单阶段")).toHaveValue("1");
    expect(screen.getByText("1 / 2 已完成")).toBeVisible();
    const passed = screen.getByRole("button", { name: /两数之和/ });
    expect(within(passed).getByText("已完成")).toBeVisible();
    expect(screen.queryByRole("button", { name: /无重复字符/ })).not.toBeInTheDocument();
  });
  it("switches stages and opens the exact catalog problem through the existing callback", () => {
    const onSelect = vi.fn();
    render(<ProblemChecklist data={data} onSelect={onSelect} />);
    fireEvent.change(screen.getByLabelText("题单阶段"), { target: { value: "2" } });
    expect(screen.getByText("0 / 1 已完成")).toBeVisible();
    expect(screen.queryByRole("button", { name: /两数之和/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /无重复字符/ }));
    expect(onSelect).toHaveBeenCalledWith(third);
    expect(onSelect).toHaveBeenCalledOnce();
  });
  it("handles an empty learning route without inventing checklist problems", () => {
    render(<ProblemChecklist data={{ ...data, route: [] }} onSelect={vi.fn()} />);
    expect(screen.getByText("当前阶段暂无题目。")).toBeVisible();
    expect(screen.getByLabelText("题单阶段")).toBeDisabled();
  });
});
