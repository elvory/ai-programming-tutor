import { useEffect, useState } from "react";
import {
  BookOpen,
  Check,
  ExternalLink,
  FileText,
  History,
  PanelLeftClose,
} from "lucide-react";
import { api } from "../api";
import type { DisplayRow, Problem } from "../types";

interface Props {
  problem: Problem;
  accepted: boolean;
  refreshKey: number;
  onCollapse: () => void;
  onAccept: () => void;
}
export function ProblemPanel({
  problem,
  accepted,
  refreshKey,
  onCollapse,
  onAccept,
}: Props) {
  const [tab, setTab] = useState("description");
  const [activities, setActivities] = useState<DisplayRow[]>([]);
  const [historyError, setHistoryError] = useState("");
  useEffect(() => {
    setHistoryError("");
    setActivities([]);
    let current = true;
    api
      .history(problem.id)
      .then((data) => {
        if (current) setActivities(data.activities);
      })
      .catch((error) => {
        if (current) setHistoryError(error.message);
      });
    return () => {
      current = false;
    };
  }, [problem.id, refreshKey]);
  return (
    <section className="panel problem-panel" aria-label="题目面板">
      <div className="panel-tabs">
        <button
          className={tab === "description" ? "active" : ""}
          onClick={() => setTab("description")}
        >
          <FileText size={14} />
          题目描述
        </button>
        <button
          className={tab === "solutions" ? "active" : ""}
          onClick={() => setTab("solutions")}
        >
          <BookOpen size={14} />
          题解
        </button>
        <button
          className={tab === "submissions" ? "active" : ""}
          onClick={() => setTab("submissions")}
        >
          <History size={14} />
          提交记录
        </button>
        <button
          className="icon-button push-right"
          onClick={onCollapse}
          title="折叠题目面板"
          aria-label="折叠题目面板"
        >
          <PanelLeftClose size={15} />
        </button>
      </div>
      <div className="panel-scroll statement">
        {tab === "description" && (
          <>
            <div className="problem-kicker">LEETCODE · 精选题库</div>
            <h1>
              {problem.id}. {problem.title_zh}
            </h1>
            <p className="english-title">{problem.title_en}</p>
            <div className="problem-meta">
              <span
                className={`difficulty ${problem.difficulty.toLowerCase()}`}
              >
                {
                  { Easy: "简单", Medium: "中等", Hard: "困难" }[
                    problem.difficulty
                  ]
                }
              </span>
              <span className="meta-divider" />
              {accepted ? (
                <span className="accepted-label">
                  <Check size={12} />
                  已通过 · 用户自报
                </span>
              ) : (
                <span className="muted">未完成</span>
              )}
              <a
                className="icon-link push-right"
                href={problem.official_url}
                target="_blank"
                rel="noreferrer"
                aria-label="查看 LeetCode 官方题目"
              >
                <ExternalLink size={14} />
              </a>
            </div>
            <div className="tag-list">
              {problem.tags.map((tag) => (
                <span key={tag}>{tag}</span>
              ))}
            </div>
            <div className="statement-copy">
              <p>{problem.summary}</p>
            </div>
            <div className="section-label">示例</div>
            {problem.examples.map((example, i) => (
              <div className="example" key={i}>
                <h3>示例 {i + 1}</h3>
                <div className="example-code">
                  <p>
                    <span>输入：</span>
                    <code>{example.input}</code>
                  </p>
                  <p>
                    <span>输出：</span>
                    <code>{example.output}</code>
                  </p>
                </div>
                {example.explanation && (
                  <p className="example-explanation">
                    <b>解释：</b>
                    {example.explanation}
                  </p>
                )}
              </div>
            ))}
            <div className="section-label constraints-label">提示与约束</div>
            <ul className="constraints">
              {problem.constraints.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <div className="statement-note">
              <BookOpen size={14} />
              <p>
                本地原创练习摘要。完整题意与判题要求以{" "}
                <a href={problem.official_url} target="_blank" rel="noreferrer">
                  LeetCode 官方页面 <ExternalLink size={10} />
                </a>{" "}
                为准。
              </p>
            </div>
            <button
              className={`accept-control ${accepted ? "is-accepted" : ""}`}
              onClick={onAccept}
              disabled={accepted}
            >
              <Check size={14} />
              {accepted ? "已确认在 LeetCode 通过" : "标记 LeetCode 已通过"}
            </button>
          </>
        )}
        {tab === "solutions" && (
          <div className="empty-state">
            <BookOpen size={30} />
            <h3>把思考留给自己</h3>
            <p>当前题库未收录完整题解。可以先写下思路，再使用右侧渐进提示。</p>
            <a
              className="subtle-link"
              href={problem.official_url}
              target="_blank"
              rel="noreferrer"
            >
              前往官方题目页面 <ExternalLink size={13} />
            </a>
          </div>
        )}
        {tab === "submissions" && (
          <>
            <div className="section-label">本题学习活动</div>
            {historyError && <div className="inline-error">{historyError}</div>}
            {!historyError && activities.length === 0 && (
              <div className="empty-state">
                <History size={28} />
                <h3>从第一次练习开始</h3>
                <p>
                  点击顶部「记录提交」保存本地学习活动。AI
                  诊断不会计入提交次数。
                </p>
              </div>
            )}
            {activities.map((item, i) => (
              <article className="activity-item" key={i}>
                <div>
                  <span className="activity-dot" />
                  <b>{item["活动类型"]}</b>
                </div>
                <p>{item["提交日期"]}</p>
                <small>
                  {item["错误类型"]} · {item["Hint 使用情况"]}
                </small>
              </article>
            ))}
          </>
        )}
      </div>
      <div className="panel-bottom">
        <span>
          <span className="tiny-dot" />
          独立阅读区域
        </span>
        <span>第 {problem.stage} 阶段</span>
      </div>
    </section>
  );
}
