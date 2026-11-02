import { ArrowUpRight, ChartNoAxesCombined } from "lucide-react";
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart,
  ResponsiveContainer, Tooltip } from "recharts";
import type { CapabilityProfileData, Problem } from "../types";
import "../capability.css";

const labelLines: Record<string, string[]> = {
  "数组与哈希表": ["数组与", "哈希表"],
  "双指针与滑动窗口": ["双指针与", "滑动窗口"],
  "栈、队列与二分查找": ["栈、队列与", "二分查找"],
  "链表、二叉树与递归": ["链表、二叉树", "与递归"],
  "DFS、BFS 与回溯": ["DFS、BFS", "与回溯"],
  "贪心与动态规划": ["贪心与", "动态规划"],
};

function AxisLabel({ x = 0, y = 0, payload }: { x?: number; y?: number; payload?: { value?: string } }) {
  const label = payload?.value || "";
  return <text x={x} y={y} textAnchor="middle" fill="#9fb8af" fontSize={10}>
    {(labelLines[label] || [label]).map((line, i) => <tspan key={line} x={x} dy={i ? 14 : -3}>{line}</tspan>)}
  </text>;
}

export function CapabilityProfile({ data, problems, onSelect }: {
  data?: CapabilityProfileData; problems: Problem[]; onSelect: (problem: Problem) => void;
}) {
  const next = problems.find(problem => problem.id === data?.recommended_problem_id);
  return <section className="progress-section capability-section" aria-label="算法能力画像">
    <header>
      <div><h2><ChartNoAxesCombined size={17} /> 算法能力画像</h2><p>六个方向，记录你的题库完成度。</p></div>
      <span>V1 · 完成度</span>
    </header>
    {!data ? <p className="capability-note">画像数据暂不可用，请刷新页面或检查后端服务。</p> : <>
      <div className="capability-sample">
        <span>{data.sample_status === "available" ? "按不同题目统计" : "样本不足 · 暂不判断强弱"}</span>
        <b>{data.completed_unique}<em> / {data.total} 题</em></b>
      </div>
      <div className="capability-chart" role="img" aria-label="六边形题库完成度雷达图，范围0至100；详细数据见下方六维列表">
        <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 440, height: 300 }}>
          <RadarChart data={data.dimensions} cx="50%" cy="50%" outerRadius="62%">
            <PolarGrid stroke="#304b44" gridType="polygon" />
            <PolarAngleAxis dataKey="label" tick={<AxisLabel />} />
            <PolarRadiusAxis angle={90} domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={{ fill: "#68877c", fontSize: 9 }} axisLine={false} />
            <Radar name="完成度" dataKey="percentage" stroke="#56c79b" fill="#32a879" fillOpacity={0.27}
              dot={{ r: 3, fill: "#7ce4b5", strokeWidth: 0 }} isAnimationActive={false} />
            <Tooltip content={({ active, payload }) => {
              const row = active && payload?.[0]?.payload as typeof data.dimensions[number] | undefined;
              return row ? <div className="capability-tooltip"><strong>{row.label}</strong>
                <p>{row.completed} / {row.total} 题已确认通过 · {row.percentage}%</p>
                <small>{row.sample_status === "available" ? "按不同题目 ID 去重" : "样本不足，完成度不代表实际能力"}</small>
              </div> : null;
            }} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <ul className="capability-dimensions" aria-label="六个算法维度完成度">
        {data.dimensions.map(row => <li key={row.id} tabIndex={0}
          title={`${row.label}：${row.completed} / ${row.total} 题，${row.percentage}%。${row.sample_status !== "available" ? "样本不足；" : ""}按不同题目统计，非实际能力评分。`}>
          <span>{row.label}</span><small>{row.completed} / {row.total}</small><b>{row.percentage}%</b>
        </li>)}
      </ul>
      <div className="capability-analysis">
        {data.sample_status === "available" && <dl>
          <div><dt>完成度较高</dt><dd>{data.strongest.join("、") || "暂无可比较数据"}</dd></div>
          <div><dt>待加强方向</dt><dd>{data.needs_attention.join("、") || "已完成当前题库，可继续复盘"}</dd></div>
        </dl>}
        <p>{data.recommendation}</p>
        <small>按用户自报 LeetCode 通过统计；同题多语言只计一次。少于 3 道通过题标记样本不足，诊断与 Hint 不参与评分。</small>
        {data.unclassified_problem_ids.length > 0 && <p>另有 {data.unclassified_problem_ids.length} 道题未能归类，未计入六维分母。</p>}
        {next && <button className="subtle-link" onClick={() => onSelect(next)}>继续练习 · {next.title_zh} <ArrowUpRight size={13} /></button>}
      </div>
    </>}
  </section>;
}
