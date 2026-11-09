import { AlertCircle, CheckCircle2, LoaderCircle, Terminal } from "lucide-react";
import type { ExecutionStatus, ExecutionViewState } from "../executionTypes";
import "../execution.css";

const STATUS_LABELS: Record<ExecutionStatus, string> = {
  SUCCESS: "运行成功",
  COMPILE_ERROR: "语法错误",
  RUNTIME_ERROR: "运行错误",
  TIME_LIMIT_EXCEEDED: "运行超时",
  OUTPUT_LIMIT_EXCEEDED: "输出超限",
  MEMORY_LIMIT_EXCEEDED: "内存超限",
  SYSTEM_ERROR: "执行服务错误",
};

function valueText(value: unknown) {
  if (value === undefined) return "未返回";
  return JSON.stringify(value) ?? "未返回";
}

interface Props {
  execution: ExecutionViewState;
  supported: boolean;
}

export function ExecutionResultPanel({ execution, supported }: Props) {
  const { busy, result, error, stale } = execution;
  if (!supported) {
    return <div className="no-execution" role="region" aria-label="代码执行结果">
      <Terminal size={20} />
      <div><b>当前语言或题目尚未开放执行</b>
        <p>暂仅开放 Python · 两数之和（#1）的公开示例运行。</p>
        {busy && <p>上次运行仍在结束中，旧结果不会显示在当前题目。</p>}
      </div>
    </div>;
  }
  if (busy) {
    return <div className="execution-pending" role="region" aria-label="代码执行结果">
      <LoaderCircle size={18} className="execution-spinner" />
      <div role="status"><b>{stale ? "等待上次运行结束" : "正在运行公开示例…"}</b>
        <p>{stale ? "当前代码已更新，旧结果已隔离。上次运行结束后可运行当前代码。" : "正在执行当前代码，请稍候。"}</p>
      </div>
    </div>;
  }
  if (error) {
    return <div className="execution-error" role="region" aria-label="代码执行结果">
      <AlertCircle size={18} /><div role="alert"><b>运行未能完成</b><p>{error}</p></div>
    </div>;
  }
  if (stale) {
    return <div className="no-execution" role="region" aria-label="代码执行结果">
      <Terminal size={20} /><div><b>执行结果已失效</b>
        <p>代码、题目或语言已更新，请重新运行当前代码。</p>
      </div>
    </div>;
  }
  if (!result) {
    return <div className="no-execution" role="region" aria-label="代码执行结果">
      <Terminal size={20} /><div><b>尚未执行代码</b>
        <p>点击“运行公开示例”，查看当前 Python 代码的实际结果；修改代码后可重新运行。</p>
      </div>
    </div>;
  }
  const successful = result.status === "SUCCESS";
  return <div className="execution-result" role="region" aria-label="代码执行结果">
    <div className={`execution-summary ${successful && result.judge.all_passed ? "is-passed" : "is-failed"}`} role="status">
      {successful && result.judge.all_passed ? <CheckCircle2 size={17} /> : <AlertCircle size={17} />}
      <div><b>{STATUS_LABELS[result.status]}</b>
        <p>公开示例 {result.judge.passed} / {result.judge.total} 通过</p>
      </div>
      <span className="execution-time"><span>沙箱耗时</span>
        <b>{result.execution_time_ms === null ? "未获取" : `${result.execution_time_ms.toFixed(2)} ms`}</b>
      </span>
    </div>
    {result.error_message && <p className="execution-message">{result.error_message}</p>}
    <p className="execution-scope">仅运行公开示例，不代表 LeetCode 官方通过；运行不会增加学习提交。</p>
    <div className="execution-streams">
      <div><label>stdout</label><pre>{result.stdout || "（无输出）"}</pre></div>
      <div><label>stderr</label><pre>{result.stderr || "（无输出）"}</pre></div>
    </div>
    <div className="execution-cases">
      {result.judge.cases.map((testCase, index) => (
        <article className="execution-case" key={testCase.case_id}>
          <div className="execution-case-heading"><b>Case {index + 1}</b>
            <span className={testCase.passed ? "case-passed" : "case-failed"}>
              {testCase.status === "not_run" ? "未运行" : testCase.passed ? "通过" : "未通过"}
            </span>
          </div>
          <div className="execution-case-values">
            <div><label>输入</label><pre>{valueText(testCase.input)}</pre></div>
            <div><label>预期结果</label><pre>{valueText(testCase.expected)}</pre></div>
            <div><label>实际结果</label><pre>{testCase.status === "not_run" ? "未返回" : valueText(testCase.actual)}</pre></div>
          </div>
        </article>
      ))}
    </div>
  </div>;
}
