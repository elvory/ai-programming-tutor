import { useState } from "react";
import {
  ArrowDown,
  ArrowRight,
  BookOpen,
  Check,
  CircleHelp,
  Lightbulb,
  LoaderCircle,
  PanelRightClose,
  ScanLine,
  Sparkles,
} from "lucide-react";
import type { DiagnosisResult, Problem } from "../types";

interface Props {
  problem: Problem;
  result: DiagnosisResult | null;
  loading: boolean;
  hintLoading: boolean;
  error: string;
  onDiagnose: () => void;
  onHint: () => void;
  onCollapse: () => void;
}
export function AssistantPanel({
  problem,
  result,
  loading,
  hintLoading,
  error,
  onDiagnose,
  onHint,
  onCollapse,
}: Props) {
  const [tab, setTab] = useState("hints");
  const diagnosis = result?.diagnosis;
  return (
    <aside className="panel assistant-panel" aria-label="AI 辅导面板">
      <div className="assistant-heading">
        <span className="assistant-logo">
          <Sparkles size={16} />
        </span>
        <div>
          <strong>AI Programming Assistant</strong>
          <span>
            <span className="tiny-dot" />
            DeepSeek · 渐进式辅导
          </span>
        </div>
        <button
          className="icon-button push-right"
          aria-label="折叠 AI 面板"
          title="折叠 AI 面板"
          onClick={onCollapse}
        >
          <PanelRightClose size={15} />
        </button>
      </div>
      <div className="panel-tabs ai-tabs">
        <button
          className={tab === "hints" ? "active" : ""}
          onClick={() => setTab("hints")}
        >
          <Lightbulb size={14} />
          AI 提示
        </button>
        <button
          className={tab === "diagnosis" ? "active" : ""}
          onClick={() => setTab("diagnosis")}
        >
          <ScanLine size={14} />
          代码诊断
        </button>
        <button
          className={tab === "knowledge" ? "active" : ""}
          onClick={() => setTab("knowledge")}
        >
          <BookOpen size={14} />
          知识点
        </button>
      </div>
      <div className="panel-scroll assistant-content" aria-live="polite">
        {error && (
          <div className="inline-error" role="alert">
            <CircleHelp size={16} />
            <div>
              <b>本次诊断未完成</b>
              <p>{error}</p>
              <small>你的代码已保留。没有保存成功诊断。</small>
            </div>
          </div>
        )}
        {loading && (
          <div className="analysis-loading">
            <LoaderCircle className="spin" size={24} />
            <h3>正在阅读你的代码</h3>
            <p>结合题目与边界情况生成三级提示…</p>
            <span>修改代码、切题或切换语言会使本次结果失效</span>
          </div>
        )}
        {!loading && !diagnosis && tab === "hints" && (
          <>
            <div className="assistant-welcome">
              <div className="welcome-orbit">
                <Sparkles size={24} />
              </div>
              <span className="eyebrow">让思路，向前一步</span>
              <h2>
                答案之前，
                <br />
                先找到自己的方向。
              </h2>
              <p>
                卡住了吗？我会陪你拆解问题，
                <br />
                用恰到好处的提示引导你继续。
              </p>
            </div>
            <div className="current-problem-card">
              <span>正在练习</span>
              <strong>
                {problem.id}. {problem.title_zh}
              </strong>
              <small>{problem.tags.join(" · ")}</small>
            </div>
            <div className="hint-steps">
              <div>
                <span>1</span>
                <p>
                  轻度提示<small>发现值得关注的方向</small>
                </p>
              </div>
              <div>
                <span>2</span>
                <p>
                  进一步引导<small>通过例子定位问题</small>
                </p>
              </div>
              <div>
                <span>3</span>
                <p>
                  深入思考<small>明确局部修改思路</small>
                </p>
              </div>
            </div>
            <button
              className="primary-button start-guidance"
              onClick={onDiagnose}
              disabled={!problem}
            >
              <Sparkles size={15} />
              获取 AI 提示
              <ArrowRight size={14} />
            </button>
            <p className="guidance-footnote">
              一次诊断，三级引导。按你的节奏逐步展开。
              <br />
              当前题目与代码将发送至 DeepSeek，可能产生 API 费用。
            </p>
          </>
        )}
        {!loading && diagnosis && (tab === "hints" || tab === "diagnosis") && (
          <>
            <div className="diagnosis-status">
              <span>
                <Check size={12} />
                分析完成
              </span>
              <small>
                来源：
                {diagnosis.source === "deepseek"
                  ? "DeepSeek"
                  : diagnosis.source === "rules" || diagnosis.is_mock
                    ? "本地规则 / Mock"
                    : "未记录"}
              </small>
            </div>
            <div className="diagnosis-summary">
              <span className="eyebrow">这次值得关注</span>
              <h3>{diagnosis.error_type}</h3>
              <div className="knowledge-chip">
                <BookOpen size={12} />
                {diagnosis.knowledge}
              </div>
              <p>{diagnosis.analysis}</p>
            </div>
            {tab === "hints" && (
              <>
                <div className="hints-divider">
                  <span>循序渐进的提示</span>
                  <small>
                    {result.hint_level} / {result.hint_count}
                  </small>
                </div>
                <div className="revealed-hints">
                  {diagnosis.hints
                    .slice(0, result.hint_level)
                    .map((hint, i) => (
                      <article className={`hint-card hint-${i + 1}`} key={i}>
                        <div>
                          <span className="hint-number">0{i + 1}</span>
                          <b>{["轻度提示", "进一步引导", "深入思考"][i]}</b>
                          <Lightbulb size={14} />
                        </div>
                        <p>{hint}</p>
                      </article>
                    ))}
                </div>
                <button
                  className="next-hint-button"
                  disabled={
                    hintLoading || result.hint_level >= result.hint_count
                  }
                  onClick={onHint}
                >
                  {hintLoading ? (
                    <LoaderCircle className="spin" size={15} />
                  ) : result.hint_level >= result.hint_count ? (
                    <Check size={15} />
                  ) : (
                    <ArrowDown size={15} />
                  )}
                  {result.hint_level >= result.hint_count
                    ? "已展开全部三级提示"
                    : "查看下一条提示"}
                  <span>{Math.min(result.hint_level + 1, 3)} / 3</span>
                </button>
              </>
            )}
            {tab === "diagnosis" && (
              <div className="coaching-note">
                <Lightbulb size={16} />
                <p>
                  修改建议会随 Hint 逐级展开。先回到「AI
                  提示」检查已展示的引导，再自行修改代码与验证边界。
                </p>
              </div>
            )}
            {result.warning && (
              <div className="inline-warning">{result.warning}</div>
            )}
          </>
        )}
        {!loading && !diagnosis && tab === "diagnosis" && (
          <div className="empty-state">
            <ScanLine size={28} />
            <h3>先让我们读一遍代码</h3>
            <p>发起诊断后，这里将显示错误类型、分析与相关知识点。</p>
            <button className="secondary-button" onClick={onDiagnose}>
              开始代码诊断
            </button>
          </div>
        )}
        {!loading && tab === "knowledge" && (
          <>
            <div className="knowledge-heading">
              <BookOpen size={24} />
              <h3>从一道题，连接一个知识点。</h3>
            </div>
            <div className="section-label">题目算法标签</div>
            <div className="tag-list knowledge-tags">
              {problem.tags.length ? (
                problem.tags.map((tag) => <span key={tag}>{tag}</span>)
              ) : (
                <span>暂无标签数据</span>
              )}
            </div>
            {diagnosis && (
              <div className="diagnosis-summary">
                <span className="eyebrow">本次诊断相关</span>
                <h3>{diagnosis.knowledge}</h3>
                <p>{diagnosis.analysis}</p>
              </div>
            )}
            <p className="muted small-copy">
              当前知识点来自题库标签与本次诊断。题库尚未收录独立知识讲义。
            </p>
          </>
        )}
      </div>
      <div className="assistant-footer">
        <span className="tiny-dot" />
        <span>引导思考，不代替思考</span>
        <span className="push-right">AI TUTOR</span>
      </div>
    </aside>
  );
}
