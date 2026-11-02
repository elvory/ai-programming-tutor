import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { HistoryPage } from "./HistoryPage";

vi.mock("../api", () => ({ api: { history: vi.fn() } }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
describe("language-aware history", () => {
  it("shows new language labels and keeps a missing legacy language unclassified", async () => {
    vi.mocked(api.history).mockResolvedValue({ records: [
      { "原始索引": "0", "题目名称": "Old problem", "状态": "完整" },
      { "原始索引": "1", "题目名称": "New problem", "语言": "Java", "状态": "完整" },
    ], activities: [{ "原始索引": "0", "题目名称": "C problem", "语言": "C", "状态": "完整" }] });
    render(<HistoryPage refreshKey={0} />);
    const oldProblem = await screen.findByText("Old problem");
    const oldRow = oldProblem.closest("tr")!;
    expect(within(oldRow).queryByText("Python 3")).not.toBeInTheDocument();
    expect(within(oldRow).getAllByText("未记录").length).toBeGreaterThan(0);
    expect(screen.getByText("Java")).toBeVisible();
    expect(screen.getByRole("columnheader", { name: "语言" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /本地学习活动/ }));
    expect(screen.getByText("C")).toBeVisible();
  });
});
