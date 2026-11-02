import { useEffect, useState } from "react";
import {
  Clock3,
  GitCommitHorizontal,
  LoaderCircle,
  ScanLine,
} from "lucide-react";
import { api } from "../api";
import type { DisplayRow, History } from "../types";

export function HistoryPage({ refreshKey }: { refreshKey: number }) {
  const [history, setHistory] = useState<History | null>(null);
  const [tab, setTab] = useState<"records" | "activities">("records");
  const [error, setError] = useState("");
  useEffect(() => {
    let current = true;
    api
      .history()
      .then((data) => {
        if (current) setHistory(data);
      })
      .catch((reason) => {
        if (current) setError(reason.message);
      });
    return () => {
      current = false;
    };
  }, [refreshKey]);
  const rows = history?.[tab] || [];
  const columns =
    tab === "records"
      ? [
          "题目名称",
          "LeetCode 题号",
          "语言",
          "错误类型",
          "知识点",
          "Hint 使用情况",
          "诊断来源",
          "提交日期",
          "状态",
        ]
      : [
          "题目名称",
          "活动类型",
          "语言",
          "Hint 使用情况",
          "诊断来源",
          "提交日期",
          "本地完成状态",
          "状态",
        ];
  function value(row: DisplayRow, column: string) {
    return column === "题目名称" && row[column] === "未记录"
      ? row["题目"] || row[column]
      : row[column] || "未记录";
  }
  return (
    <div className="secondary-page history-page">
      <div className="page-intro">
        <span className="eyebrow">REFLECT & GROW</span>
        <h1>回看走过的每一步。</h1>
        <p>保留思考的轨迹，在复盘中发现下一次进步的方向。</p>
      </div>
      <div className="history-switch">
        <button
          className={tab === "records" ? "active" : ""}
          onClick={() => setTab("records")}
        >
          <ScanLine size={16} />
          AI 诊断记录<span>{history?.records.length ?? "—"}</span>
        </button>
        <button
          className={tab === "activities" ? "active" : ""}
          onClick={() => setTab("activities")}
        >
          <GitCommitHorizontal size={16} />
          本地学习活动<span>{history?.activities.length ?? "—"}</span>
        </button>
      </div>
      {error && <div className="inline-error">{error}</div>}
      {!history && !error && (
        <div className="empty-state">
          <LoaderCircle className="spin" size={26} />
          <p>正在读取本地学习记录…</p>
        </div>
      )}
      {history && rows.length === 0 && (
        <div className="empty-state">
          <Clock3 size={32} />
          <h3>这里会记录你的成长</h3>
          <p>
            {tab === "records"
              ? "完成一次 AI 诊断后，就能在这里回顾相关知识点和 Hint 使用。"
              : "点击「记录提交」或主动确认 LeetCode 通过后，活动会显示在这里。"}
          </p>
        </div>
      )}
      {rows.length > 0 && (
        <div className="history-table-wrap">
          <table>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row["原始索引"]}-${index}`}>
                  {columns.map((column) => (
                    <td
                      key={column}
                      className={
                        column === "状态" && row[column] !== "完整"
                          ? "anomaly-text"
                          : ""
                      }
                      title={
                        column === "状态" ? row["异常说明"] : value(row, column)
                      }
                    >
                      {column === "语言" ? <span className="language-badge">{value(row, column)}</span> : value(row, column)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="history-note">
        诊断、提交与用户自报通过独立记录。旧记录与异常条目保持原样，缺失信息显示为「未记录」。
      </p>
    </div>
  );
}
