import { useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import {
  AlignLeft,
  Check,
  CheckCheck,
  ChevronDown,
  Code2,
  Copy,
  FileCode2,
  FlaskConical,
  Maximize2,
  Minimize2,
  RotateCcw,
  Terminal,
} from "lucide-react";
import "../monaco";
import { SplitHandle } from "./SplitHandle";
import type { Problem } from "../types";

interface Props {
  problem: Problem;
  code: string;
  fontSize: number;
  fullscreen: boolean;
  testHeight: number;
  storageError: boolean;
  onCode: (value: string) => void;
  onFontSize: (value: number) => void;
  onFullscreen: () => void;
  onTestHeight: (delta: number) => void;
  onNotice: (message: string) => void;
}
export function CodePanel({
  problem,
  code,
  fontSize,
  fullscreen,
  testHeight,
  storageError,
  onCode,
  onFontSize,
  onFullscreen,
  onTestHeight,
  onNotice,
}: Props) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const [readOnly, setReadOnly] = useState(false);
  const [testTab, setTestTab] = useState("cases");
  const [exampleIndex, setExampleIndex] = useState(0);
  const [cursor, setCursor] = useState({ lineNumber: 1, column: 1 });
  const [copied, setCopied] = useState(false);
  const example =
    problem.examples[Math.min(exampleIndex, problem.examples.length - 1)];
  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      onNotice("浏览器未允许复制，请在编辑器中全选后复制。");
    }
  }
  return (
    <section
      className={`panel code-panel ${fullscreen ? "editor-fullscreen" : ""}`}
      aria-label="代码编辑器面板"
    >
      <div className="panel-tabs code-heading">
        <span className="code-title">
          <Code2 size={15} />
          代码
        </span>
        <span className="file-path">
          <FileCode2 size={12} />
          solution.py
        </span>
        <div className="push-right toolbar-icons">
          <button
            className="icon-button"
            title="复制代码"
            aria-label="复制代码"
            onClick={copy}
          >
            {copied ? <CheckCheck size={14} /> : <Copy size={14} />}
          </button>
          <button
            className="icon-button"
            title="重置为本题模板"
            aria-label="重置代码"
            onClick={() => {
              if (
                confirm(
                  "将当前题目的草稿重置为模板？这会覆盖本题当前代码，请先备份。",
                )
              )
                onCode(problem.python_template);
            }}
          >
            <RotateCcw size={14} />
          </button>
          <button
            className="icon-button"
            title={fullscreen ? "退出编辑器全屏" : "编辑器全屏"}
            aria-label={fullscreen ? "退出编辑器全屏" : "编辑器全屏"}
            onClick={onFullscreen}
          >
            {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
        </div>
      </div>
      <div
        className="editor-test-stack"
        style={{
          gridTemplateRows: `minmax(150px, 1fr) 6px minmax(95px, ${testHeight}%)`,
        }}
      >
        <div className="editor-space">
          <div className="editor-toolbar">
            <label className="language-select">
              <span className="python-mark">Py</span>
              <select aria-label="编程语言" defaultValue="python">
                <option value="python">Python 3</option>
              </select>
              <ChevronDown size={11} />
            </label>
            <span className="toolbar-divider" />
            <select
              className="mode-select"
              aria-label="编辑模式"
              value={readOnly ? "readonly" : "edit"}
              onChange={(event) =>
                setReadOnly(event.target.value === "readonly")
              }
            >
              <option value="edit">编辑模式</option>
              <option value="readonly">只读预览</option>
            </select>
            <span className="push-right" />
            <button
              className="icon-button"
              title="整理缩进"
              aria-label="整理缩进"
              onClick={() =>
                void editorRef.current
                  ?.getAction("editor.action.reindentlines")
                  ?.run()
              }
            >
              <AlignLeft size={14} />
            </button>
            <label className="font-control" title="编辑器字号">
              <span>Aa</span>
              <select
                aria-label="编辑器字号"
                value={fontSize}
                onChange={(event) => onFontSize(Number(event.target.value))}
              >
                {[12, 13, 14, 15, 16, 18, 20].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="monaco-container" data-testid="monaco-container">
            <Editor
              key={problem.id}
              path={`problem-${problem.id}.py`}
              language="python"
              value={code}
              theme="tutor-dark"
              loading={<div className="editor-loading">正在准备编辑器…</div>}
              onChange={(value) => {
                if (value !== undefined) onCode(value);
              }}
              onMount={(instance) => {
                editorRef.current = instance;
                instance.onDidChangeCursorPosition((event) =>
                  setCursor(event.position),
                );
              }}
              options={{
                automaticLayout: true,
                fontSize,
                readOnly,
                fontFamily:
                  "'Cascadia Code', 'JetBrains Mono', Consolas, monospace",
                fontLigatures: false,
                lineHeight: Math.round(fontSize * 1.65),
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                tabSize: 4,
                insertSpaces: true,
                padding: { top: 18, bottom: 16 },
                lineNumbersMinChars: 3,
                folding: true,
                glyphMargin: false,
                renderLineHighlight: "line",
                smoothScrolling: true,
                bracketPairColorization: { enabled: true },
                autoIndent: "full",
                wordBasedSuggestions: "currentDocument",
                quickSuggestions: true,
                suggestOnTriggerCharacters: true,
                stickyScroll: { enabled: false },
                wordWrap: "off",
                scrollbar: {
                  verticalScrollbarSize: 7,
                  horizontalScrollbarSize: 7,
                },
                overviewRulerLanes: 0,
              }}
            />
          </div>
          <div className="editor-status">
            <span>
              <Check size={11} />
              {storageError ? "仅保存在当前会话" : "草稿已自动保存"}
            </span>
            <span>
              Ln {cursor.lineNumber}, Col {cursor.column}
            </span>
            <span>UTF-8</span>
            <span>空格: 4</span>
          </div>
        </div>
        <SplitHandle
          direction="vertical"
          label="调整测试面板高度"
          value={testHeight}
          onChange={(delta) => onTestHeight(-delta)}
        />
        <section className="test-panel" aria-label="测试面板">
          <div className="panel-tabs">
            <button
              className={testTab === "cases" ? "active" : ""}
              onClick={() => setTestTab("cases")}
            >
              <FlaskConical size={14} />
              测试用例
            </button>
            <button
              className={testTab === "results" ? "active" : ""}
              onClick={() => setTestTab("results")}
            >
              <Terminal size={14} />
              测试结果
            </button>
            <span className="not-run-label push-right">
              <span className="tiny-dot" />
              尚未执行
            </span>
          </div>
          <div className="test-content">
            {testTab === "cases" ? (
              <>
                <div className="case-tabs">
                  {problem.examples.map((_, i) => (
                    <button
                      key={i}
                      className={
                        Math.min(exampleIndex, problem.examples.length - 1) ===
                        i
                          ? "active"
                          : ""
                      }
                      onClick={() => setExampleIndex(i)}
                    >
                      Case {i + 1}
                    </button>
                  ))}
                  <span>题库示例</span>
                </div>
                {example ? (
                  <div className="test-values">
                    <div>
                      <label>示例输入</label>
                      <pre>{example.input}</pre>
                    </div>
                    <div>
                      <label>预期输出</label>
                      <pre>{example.output}</pre>
                    </div>
                  </div>
                ) : (
                  <p className="muted">本题暂无示例数据。</p>
                )}
              </>
            ) : (
              <div className="no-execution">
                <Terminal size={20} />
                <div>
                  <b>尚未执行代码</b>
                  <p>
                    当前未接入安全的 Python
                    执行环境，暂不提供实际输出、运行时间或判题结果。
                  </p>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>
    </section>
  );
}
