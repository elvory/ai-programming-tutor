import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CapabilityProfile } from "./CapabilityProfile";
import type { CapabilityProfileData, Problem } from "../types";

afterEach(cleanup);
const labels = ["数组与哈希表", "双指针与滑动窗口", "栈、队列与二分查找", "链表、二叉树与递归", "DFS、BFS 与回溯", "贪心与动态规划"];
const empty: CapabilityProfileData = {
  dimensions: labels.map((label, i) => ({ id: String(i), label, stages: [i + 1],
    problem_ids: [i + 1], total: 1, completed_ids: [], completed: 0, percentage: 0,
    sample_status: "empty", recommended_problem_id: i + 1 })),
  completed_unique: 0, total: 6, sample_status: "empty", strongest: [], needs_attention: [],
  recommendation: "暂无已确认通过的样本；0% 不代表真实能力为零。",
  recommended_problem_id: 1, unclassified_problem_ids: [],
};

describe("completion profile", () => {
  it("shows all six labels and explains empty coverage without judging ability", () => {
    render(<CapabilityProfile data={empty} problems={[]} onSelect={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "算法能力画像" })).toBeInTheDocument();
    expect(screen.getByText(/暂无已确认通过的样本/)).toBeInTheDocument();
    expect(screen.getByText("样本不足 · 暂不判断强弱")).toBeInTheDocument();
    for (const label of labels) expect(screen.getByRole("list").textContent).toContain(label);
    expect(screen.queryByText("准确率")).not.toBeInTheDocument();
  });
  it("displays backend coverage and selects the recommended real catalog problem", () => {
    const onSelect = vi.fn();
    const problem = { id: 1, title_zh: "两数之和" } as Problem;
    const data: CapabilityProfileData = { ...empty, completed_unique: 3, sample_status: "available",
      strongest: [labels[0]], needs_attention: [labels[1]],
      dimensions: [{ ...empty.dimensions[0], completed: 1, percentage: 100 }, ...empty.dimensions.slice(1)] };
    render(<CapabilityProfile data={data} problems={[problem]} onSelect={onSelect} />);
    expect(screen.getByRole("list").textContent).toContain("1 / 1");
    expect(screen.getByText("100%")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /继续练习.*两数之和/ }));
    expect(onSelect).toHaveBeenCalledWith(problem);
  });
  it("does not manufacture a profile when the server omitted it", () => {
    render(<CapabilityProfile problems={[]} onSelect={vi.fn()} />);
    expect(screen.getByText(/画像数据暂不可用/)).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });
});
