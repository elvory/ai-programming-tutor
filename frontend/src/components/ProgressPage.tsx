import {
  ArrowRight,
  Check,
  Flame,
  GitCommitHorizontal,
  Route,
  Trophy,
} from "lucide-react";
import type { Bootstrap, Problem } from "../types";

export function ProgressPage({
  data,
  onSelect,
}: {
  data: Bootstrap;
  onSelect: (problem: Problem) => void;
}) {
  const { summary, heatmap, route } = data;
  const padding = heatmap.length
    ? new Date(`${heatmap[0].date}T00:00:00`).getDay()
    : 0;
  return (
    <div className="secondary-page">
      <div className="page-intro">
        <span className="eyebrow">YOUR ALGORITHM JOURNEY</span>
        <h1>把每一次练习，变成进步。</h1>
        <p>不急着到达终点。沿着自己的节奏，一题一题向前。</p>
      </div>
      <div className="metric-grid">
        <article>
          <GitCommitHorizontal size={19} />
          <span>累计本地提交</span>
          <strong>{summary.total_submissions}</strong>
          <small>来自你主动记录的学习活动</small>
        </article>
        <article>
          <Trophy size={19} />
          <span>已完成题目</span>
          <strong>
            {summary.completed_problems}
            <em> / {data.problems.length}</em>
          </strong>
          <small>LeetCode 已通过 · 用户自报</small>
        </article>
        <article>
          <Flame size={19} />
          <span>连续学习</span>
          <strong>
            {summary.streak_days}
            <em> 天</em>
          </strong>
          <small>按北京时间统计提交日</small>
        </article>
        <article>
          <Route size={19} />
          <span>推荐学习阶段</span>
          <strong>
            <em>第 </em>
            {summary.recommended_stage}
            <em> 阶段</em>
          </strong>
          <small>
            {route.find((stage) => stage.id === summary.recommended_stage)
              ?.title || "开始学习"}
          </small>
        </article>
      </div>
      <section className="progress-section">
        <header>
          <div>
            <h2>学习活动</h2>
            <p>每一格，都是你认真思考过的痕迹。</p>
          </div>
          <span>过去 365 天</span>
        </header>
        <div className="heatmap-scroll">
          <div className="heatmap-labels">
            <span>周一</span>
            <span>周三</span>
            <span>周五</span>
          </div>
          <div className="heatmap-grid" aria-label="过去365天本地提交绿墙">
            {Array.from({ length: padding }, (_, i) => (
              <span className="heatmap-blank" key={`blank-${i}`} />
            ))}
            {heatmap.map((day) => (
              <span
                key={day.date}
                className={`heatmap-day level-${day.level}`}
                title={`${day.date}：${day.count} 次本地提交`}
                aria-label={`${day.date}：${day.count} 次本地提交`}
              />
            ))}
          </div>
        </div>
        <div className="heatmap-footer">
          <span>仅「记录提交」点亮绿墙，AI 诊断不会计入。</span>
          <div>
            <span>少</span>
            {[0, 1, 2, 3, 4].map((level) => (
              <i className={`heatmap-day level-${level}`} key={level} />
            ))}
            <span>多</span>
          </div>
        </div>
      </section>
      <section className="route-section">
        <div className="section-heading">
          <h2>推荐刷题路线</h2>
          <span>8 个阶段，从基础走向进阶</span>
        </div>
        <div className="route-grid">
          {route.map((stage) => {
            const done = stage.problems.filter((problem) =>
              summary.completed_ids.includes(problem.id),
            ).length;
            return (
              <article
                className={`route-stage ${stage.id === summary.recommended_stage ? "recommended" : ""}`}
                key={stage.id}
              >
                <header>
                  <span>{String(stage.id).padStart(2, "0")}</span>
                  <div>
                    <h3>{stage.title}</h3>
                    <small>
                      {done} / {stage.problems.length} 已完成
                    </small>
                  </div>
                  {stage.id === summary.recommended_stage && <b>推荐</b>}
                </header>
                <div className="stage-progress">
                  <i
                    style={{
                      width: `${stage.problems.length ? (done / stage.problems.length) * 100 : 0}%`,
                    }}
                  />
                </div>
                {stage.problems.map((problem) => (
                  <button key={problem.id} onClick={() => onSelect(problem)}>
                    {summary.completed_ids.includes(problem.id) ? (
                      <Check size={13} />
                    ) : (
                      <span className="route-unsolved" />
                    )}
                    <span>
                      {problem.id}. {problem.title_zh}
                    </span>
                    <small
                      className={`difficulty ${problem.difficulty.toLowerCase()}`}
                    >
                      {problem.difficulty}
                    </small>
                    <ArrowRight size={12} />
                  </button>
                ))}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
