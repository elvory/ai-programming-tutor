import { useState } from "react";
import { ArrowUpRight, Check, ListChecks } from "lucide-react";
import type { Bootstrap, Problem } from "../types";
import "./checklist.css";

export function ProblemChecklist({ data, onSelect }: {
  data: Bootstrap;
  onSelect: (problem: Problem) => void;
}) {
  const [selectedStageId, setSelectedStageId] = useState<number | null>(null);
  const stage = data.route.find((item) => item.id === (selectedStageId ?? data.summary.recommended_stage))
    ?? data.route[0];
  const completed = new Set(data.summary.completed_ids);
  const done = stage?.problems.filter((problem) => completed.has(problem.id)).length ?? 0;
  const total = stage?.problems.length ?? 0;

  return (
    <section className="problem-checklist" aria-label="推荐阶段题单">
      <header className="checklist-heading">
        <div>
          <span className="checklist-eyebrow"><ListChecks size={13} /> YOUR NEXT STEPS</span>
          <h2>推荐题单</h2>
          <p>从当前阶段出发，把下一题写进学习计划。</p>
        </div>
        <a href="#full-learning-route" className="checklist-all">完整路线 <ArrowUpRight size={12} /></a>
      </header>
      <div className="checklist-stage">
        <label>
          <span>学习阶段</span>
          <select aria-label="题单阶段" value={stage?.id ?? ""} disabled={!data.route.length}
            onChange={(event) => setSelectedStageId(Number(event.target.value))}>
            {data.route.map((item) => (
              <option key={item.id} value={item.id}>第 {item.id} 阶段 · {item.title}</option>
            ))}
          </select>
        </label>
        <span className="checklist-count">{done} / {total} 已完成</span>
      </div>
      <div className="checklist-progress" role="progressbar" aria-label="当前题单完成度"
        aria-valuemin={0} aria-valuemax={total || 1} aria-valuenow={done}>
        <span style={{ width: `${total ? done / total * 100 : 0}%` }} />
      </div>
      <div className="checklist-problems">
        {stage?.problems.map((problem) => {
          const passed = completed.has(problem.id);
          return (
            <button className={`checklist-row ${passed ? "checklist-done" : ""}`} key={problem.id}
              onClick={() => onSelect(problem)}>
              <span className="checklist-check" aria-hidden="true">{passed ? <Check size={12} /> : null}</span>
              <span className="checklist-title"><small>#{problem.id}</small>{problem.title_zh}</span>
              {passed && <span className="checklist-passed">已完成</span>}
              <span className={`difficulty ${problem.difficulty.toLowerCase()}`}>{problem.difficulty}</span>
              <ArrowUpRight size={13} className="checklist-open" />
            </button>
          );
        })}
        {!total && <p className="checklist-empty">当前阶段暂无题目。</p>}
      </div>
      <p className="checklist-note">完成状态按不同题目统计，来自你确认的 LeetCode 通过记录。</p>
    </section>
  );
}
