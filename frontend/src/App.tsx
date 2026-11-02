import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import {
  BookOpen,
  Braces,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Code2,
  Command,
  ExternalLink,
  GitCommitHorizontal,
  History,
  LayoutDashboard,
  ListFilter,
  LoaderCircle,
  PanelLeftOpen,
  PanelRightOpen,
  RotateCcw,
  Route,
  Settings2,
  Sparkles,
  X,
} from "lucide-react";
import { api, ApiError } from "./api";
import { isLanguage, LANGUAGES, problemTemplate } from "./languages";
import { AssistantPanel } from "./components/AssistantPanel";
import { CodePanel } from "./components/CodePanel";
import { HistoryPage } from "./components/HistoryPage";
import { LibraryDrawer } from "./components/LibraryDrawer";
import { ProblemPanel } from "./components/ProblemPanel";
import { ProgressPage } from "./components/ProgressPage";
import { SettingsDialog } from "./components/SettingsDialog";
import { SplitHandle } from "./components/SplitHandle";
import {
  readPreference,
  bufferKey,
  rememberRevision,
  restoreCode,
  sameSnapshot,
  saveCode,
  storePreference,
  tabIdentity,
} from "./storage";
import type {
  Bootstrap,
  DiagnosisResult,
  Language,
  MobilePanel,
  Page,
  Problem,
  Snapshot,
} from "./types";

const DEFAULT_LAYOUT = { left: 27, right: 26, test: 27 };
function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

export default function App() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [bootError, setBootError] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const [code, setCode] = useState("");
  const [language, setLanguage] = useState<Language>(() => {
    const preferred = readPreference<unknown>("lastLanguage", "python");
    return isLanguage(preferred) ? preferred : "python";
  });
  const [page, setPage] = useState<Page>("workbench");
  const [result, setResult] = useState<DiagnosisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [hintLoading, setHintLoading] = useState(false);
  const [diagnosisError, setDiagnosisError] = useState("");
  const [activityBusy, setActivityBusy] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(
    () =>
      window.matchMedia?.("(min-width:768px) and (max-width:1023px)").matches ??
      false,
  );
  const [fullscreen, setFullscreen] = useState(false);
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>("code");
  const [layout, setLayout] = useState(() => {
    const stored = readPreference("layout", DEFAULT_LAYOUT);
    return {
      left: clamp(Number(stored?.left) || 27, 18, 38),
      right: clamp(Number(stored?.right) || 26, 20, 38),
      test: clamp(Number(stored?.test) || 27, 15, 55),
    };
  });
  const [fontSize, setFontSize] = useState(() =>
    clamp(Number(readPreference("fontSize", 14)) || 14, 12, 20),
  );
  const [notice, setNotice] = useState("");
  const [storageError, setStorageError] = useState(false);
  const identity = useRef(tabIdentity());
  const snapshot = useRef<Snapshot | null>(null);
  const memoryDrafts = useRef<Record<string, string>>({});
  const dirtyDrafts = useRef(new Set<string>());
  const controller = useRef<AbortController | null>(null);
  const noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function showNotice(message: string) {
    if (noticeTimer.current) clearTimeout(noticeTimer.current);
    setNotice(message);
    noticeTimer.current = setTimeout(() => setNotice(""), 6500);
  }
  function nextSnapshot(selected: Problem, source: string, selectedLanguage: Language = language): Snapshot {
    identity.current.revision++;
    rememberRevision(identity.current.revision);
    const next = { ...identity.current, problem_id: selected.id, code: source, language: selectedLanguage };
    snapshot.current = next;
    return next;
  }
  function invalidateDiagnosis() {
    controller.current?.abort();
    controller.current = null;
    setResult(null);
    setDiagnosisError("");
    setLoading(false);
    setHintLoading(false);
  }
  function sync(next: Snapshot) {
    void api.sync(next).catch((reason) => {
      if (
        sameSnapshot(next, snapshot.current) &&
        !(reason instanceof ApiError && reason.status === 409)
      )
        showNotice(reason.message);
    });
  }
  function selectProblem(selected: Problem, selectedLanguage: Language = language) {
    const key = bufferKey(selected.id, selectedLanguage);
    let source = memoryDrafts.current[key] ?? problemTemplate(selected, selectedLanguage);
    if (dirtyDrafts.current.has(key)) {
      setStorageError(true);
    } else {
      try {
        source = restoreCode(selected.id, source, localStorage, selectedLanguage);
        setStorageError(dirtyDrafts.current.size > 0);
      } catch {
        setStorageError(true);
        showNotice(
          "浏览器存储不可用。草稿仅保留在当前页面，请及时导出或复制。",
        );
      }
    }
    memoryDrafts.current[key] = source;
    invalidateDiagnosis();
    const next = nextSnapshot(selected, source, selectedLanguage);
    setProblem(selected);
    setCode(source);
    setLanguage(selectedLanguage);
    setPage("workbench");
    storePreference("lastProblem", selected.id);
    storePreference("lastLanguage", selectedLanguage);
    sync(next);
  }
  function updateCode(source: string, expectedProblem = problem?.id, expectedLanguage = language) {
    if (!problem || snapshot.current?.problem_id !== expectedProblem
      || snapshot.current?.language !== expectedLanguage || source === snapshot.current?.code) return;
    const key = bufferKey(problem.id, language);
    memoryDrafts.current[key] = source;
    try {
      saveCode(problem.id, source, localStorage, language);
      dirtyDrafts.current.delete(key);
      setStorageError(dirtyDrafts.current.size > 0);
    } catch {
      dirtyDrafts.current.add(key);
      setStorageError(true);
    }
    invalidateDiagnosis();
    const next = nextSnapshot(problem, source);
    setCode(source);
    sync(next);
  }
  async function refreshData() {
    try {
      const fresh = await api.bootstrap();
      setData(fresh);
    } catch (reason) {
      showNotice(
        reason instanceof Error ? reason.message : "学习进度暂时无法刷新。",
      );
    }
    setRefreshKey((value) => value + 1);
  }
  useEffect(() => {
    let active = true;
    api
      .bootstrap()
      .then((fresh) => {
        if (!active) return;
        setData(fresh);
        const preferredId = readPreference("lastProblem", 1);
        const selected =
          fresh.problems.find((item) => item.id === preferredId) ||
          fresh.problems[0];
        if (selected && !snapshot.current) selectProblem(selected);
      })
      .catch((reason) => {
        if (active) setBootError(reason.message);
      });
    return () => {
      active = false;
      controller.current?.abort();
    };
    // Bootstrap is deliberately one-shot; later refreshes must never reinitialize a draft.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    storePreference("layout", layout);
  }, [layout]);
  useEffect(() => {
    storePreference("fontSize", fontSize);
  }, [fontSize]);
  useEffect(() => {
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setLibraryOpen(false);
        setSettingsOpen(false);
        setFullscreen(false);
      }
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, []);

  async function diagnose() {
    if (!problem || !snapshot.current) return;
    if (!snapshot.current.code.trim()) {
      setDiagnosisError("请先写下代码，再获取 AI 提示。");
      setMobilePanel("assistant");
      setRightCollapsed(false);
      return;
    }
    invalidateDiagnosis();
    const captured = nextSnapshot(problem, snapshot.current.code);
    const pending = new AbortController();
    controller.current = pending;
    setLoading(true);
    setRightCollapsed(false);
    setMobilePanel("assistant");
    try {
      const candidate = await api.diagnose(captured, pending.signal);
      if (!sameSnapshot(captured, snapshot.current)) return;
      const accepted = await api.accept(
        captured.workspace_id,
        candidate.request_id,
        captured.revision,
        pending.signal,
      );
      if (!sameSnapshot(captured, snapshot.current)) return;
      setResult(accepted);
      setRefreshKey((value) => value + 1);
    } catch (reason) {
      if (
        !sameSnapshot(captured, snapshot.current) ||
        (reason instanceof DOMException && reason.name === "AbortError")
      )
        return;
      setDiagnosisError(
        reason instanceof Error ? reason.message : "诊断失败，请稍后重试。",
      );
    } finally {
      if (sameSnapshot(captured, snapshot.current)) setLoading(false);
    }
  }
  async function nextHint() {
    if (!result || !snapshot.current || hintLoading) return;
    const captured = { ...snapshot.current };
    setHintLoading(true);
    try {
      const revealed = await api.hint(
        captured.workspace_id,
        result.diagnosis_id,
        captured.revision,
        result.hint_level,
      );
      if (sameSnapshot(captured, snapshot.current)) {
        setResult(revealed);
        setRefreshKey((value) => value + 1);
      }
    } catch (reason) {
      if (sameSnapshot(captured, snapshot.current))
        showNotice(reason instanceof Error ? reason.message : "提示读取失败。");
    } finally {
      if (sameSnapshot(captured, snapshot.current)) setHintLoading(false);
    }
  }
  async function recordSubmission() {
    if (!snapshot.current || !snapshot.current.code.trim()) {
      showNotice("请先编写代码，再记录本地提交。");
      return;
    }
    const captured = { ...snapshot.current };
    setActivityBusy(true);
    try {
      await api.submission(captured);
      showNotice(
        "已记录一次本地提交，学习活动已更新。此操作不代表 LeetCode 通过。",
      );
      await refreshData();
    } catch (reason) {
      showNotice(
        reason instanceof Error ? reason.message : "提交记录保存失败。",
      );
    } finally {
      setActivityBusy(false);
    }
  }
  async function markAccepted() {
    if (
      !problem ||
      !confirm(
        `你确认已使用 ${LANGUAGES[language].label} 在 LeetCode 官方提交这道题并通过吗？此状态为用户自报，不额外增加本地提交次数。`,
      )
    )
      return;
    try {
      await api.accepted(problem.id, language);
      showNotice("已记录用户自报的 LeetCode 通过状态。");
      await refreshData();
    } catch (reason) {
      showNotice(
        reason instanceof Error ? reason.message : "通过状态保存失败。",
      );
    }
  }
  function resetLayout() {
    setLayout(DEFAULT_LAYOUT);
    setLeftCollapsed(false);
    setRightCollapsed(false);
    setFullscreen(false);
    setFontSize(14);
    showNotice("已恢复默认工作台布局。");
  }

  const selectedIndex =
    data?.problems.findIndex((item) => item.id === problem?.id) ?? -1;
  const completed = data?.summary.completed_ids || [];
  const workbenchStyle = {
    "--left-size": `${layout.left}%`,
    "--right-size": `${layout.right}%`,
  } as CSSProperties;
  const activeCode = page === "workbench";

  return (
    <div className="app-shell">
      <header className="app-header">
        <button
          className="brand"
          onClick={() => setPage("workbench")}
          aria-label="AI Programming Tutor 工作台"
        >
          <span className="brand-mark">
            <Braces size={21} />
          </span>
          <span>
            AI <strong>Programming Tutor</strong>
          </span>
          <span className="brand-version">WORKSPACE</span>
        </button>
        <nav className="main-nav" aria-label="主导航">
          <button
            className={page === "workbench" ? "active" : ""}
            onClick={() => setPage("workbench")}
          >
            <Code2 size={14} />
            工作台
          </button>
          <button
            className={page === "route" ? "active" : ""}
            onClick={() => setPage("route")}
          >
            <Route size={14} />
            学习路线
          </button>
          <button
            className={page === "history" ? "active" : ""}
            onClick={() => setPage("history")}
          >
            <History size={14} />
            学习记录
          </button>
        </nav>
        <div className="header-right">
          <span className="local-indicator">
            <span className="tiny-dot" />
            本地工作台
          </span>
          <button
            className="icon-button"
            aria-label="打开工作台设置"
            title="工作台设置"
            onClick={() => setSettingsOpen(true)}
          >
            <Settings2 size={17} />
          </button>
          <a
            className="icon-button external-header"
            title="LeetCode 官方网站"
            href="https://leetcode.cn/problemset/"
            target="_blank"
            rel="noreferrer"
          >
            <ExternalLink size={16} />
          </a>
          <span className="avatar" title="本地学习者">
            Y
          </span>
        </div>
      </header>
      {bootError ? (
        <main className="fatal-state">
          <LayoutDashboard size={34} />
          <h1>工作台暂时无法加载</h1>
          <p>{bootError}</p>
          <button
            className="secondary-button"
            onClick={() => location.reload()}
          >
            重新加载
          </button>
        </main>
      ) : !data || !problem ? (
        <main className="fatal-state">
          <LoaderCircle className="spin" size={28} />
          <p>正在准备你的编程工作台…</p>
        </main>
      ) : (
        <>
          <div className="workspace-toolbar">
            <div className="problem-navigation">
              <button
                className="library-trigger"
                onClick={() => setLibraryOpen(true)}
              >
                <ListFilter size={16} />
                <span>题库</span>
                <ChevronDown size={11} />
              </button>
              <span className="toolbar-divider" />
              <button
                className="icon-button"
                title="上一题"
                aria-label="上一题"
                disabled={selectedIndex <= 0}
                onClick={() => selectProblem(data.problems[selectedIndex - 1])}
              >
                <ChevronLeft size={17} />
              </button>
              <button
                className="icon-button"
                title="下一题"
                aria-label="下一题"
                disabled={
                  selectedIndex < 0 || selectedIndex >= data.problems.length - 1
                }
                onClick={() => selectProblem(data.problems[selectedIndex + 1])}
              >
                <ChevronRight size={17} />
              </button>
              <span className="toolbar-problem-title">
                {problem.id}. {problem.title_zh}
              </span>
              <span
                className={`difficulty ${problem.difficulty.toLowerCase()} toolbar-difficulty`}
              >
                {problem.difficulty}
              </span>
            </div>
            <div className="toolbar-actions">
              {activeCode && (
                <>
                  <button
                    className="icon-button layout-reset"
                    title="恢复默认布局"
                    aria-label="恢复默认布局"
                    onClick={resetLayout}
                  >
                    <RotateCcw size={14} />
                  </button>
                  <button
                    className="secondary-button submission-button"
                    disabled={activityBusy}
                    onClick={() => void recordSubmission()}
                  >
                    {activityBusy ? (
                      <LoaderCircle className="spin" size={14} />
                    ) : (
                      <GitCommitHorizontal size={14} />
                    )}
                    <span>记录提交</span>
                  </button>
                  <button
                    className="primary-button diagnose-button"
                    disabled={loading}
                    onClick={() => void diagnose()}
                  >
                    {loading ? (
                      <LoaderCircle className="spin" size={14} />
                    ) : (
                      <Sparkles size={14} />
                    )}
                    <span>
                      {loading ? "分析中…" : result ? "重新诊断" : "AI 诊断"}
                    </span>
                  </button>
                </>
              )}
            </div>
          </div>
          {storageError && (
            <div className="storage-warning" role="alert">
              浏览器存储不可用。当前代码仍在页面中，请复制备份，刷新前勿关闭页面。
            </div>
          )}
          {activeCode ? (
            <div className="workspace-container">
              <div className="activity-rail">
                <button
                  className="active"
                  aria-label="打开题库"
                  title="题库"
                  onClick={() => setLibraryOpen(true)}
                >
                  <BookOpen size={18} />
                </button>
                <button
                  aria-label="查看学习路线"
                  title="学习路线"
                  onClick={() => setPage("route")}
                >
                  <Route size={18} />
                </button>
                <button
                  aria-label="查看学习记录"
                  title="学习记录"
                  onClick={() => setPage("history")}
                >
                  <History size={18} />
                </button>
                <span className="push-down" />
                <button
                  aria-label="设置与草稿备份"
                  title="设置与草稿备份"
                  onClick={() => setSettingsOpen(true)}
                >
                  <Settings2 size={18} />
                </button>
              </div>
              <div
                className={`workspace-grid ${leftCollapsed ? "left-collapsed" : ""} ${rightCollapsed ? "right-collapsed" : ""} ${fullscreen ? "fullscreen-mode" : ""} mobile-${mobilePanel}`}
                style={workbenchStyle}
              >
                {leftCollapsed ? (
                  <button
                    className="collapsed-panel left-restore"
                    aria-label="展开题目面板"
                    onClick={() => setLeftCollapsed(false)}
                  >
                    <PanelLeftOpen size={16} />
                    <span>题目描述</span>
                  </button>
                ) : (
                  <ProblemPanel
                    problem={problem}
                    language={language}
                    accepted={data.summary.completed_by_language?.[language]?.includes(problem.id) ?? false}
                    overallAccepted={completed.includes(problem.id)}
                    refreshKey={refreshKey}
                    onCollapse={() => setLeftCollapsed(true)}
                    onAccept={() => void markAccepted()}
                  />
                )}
                <SplitHandle
                  label="调整题目面板宽度"
                  value={layout.left}
                  onChange={(delta) =>
                    setLayout((previous) => ({
                      ...previous,
                      left: clamp(previous.left + delta, 18, 38),
                    }))
                  }
                />
                <CodePanel
                  problem={problem}
                  language={language}
                  onLanguage={(value) => {
                    if (value !== language) selectProblem(problem, value);
                  }}
                  code={code}
                  fontSize={fontSize}
                  fullscreen={fullscreen}
                  testHeight={layout.test}
                  storageError={storageError}
                  onCode={(source) => updateCode(source, problem.id, language)}
                  onFontSize={setFontSize}
                  onFullscreen={() => setFullscreen((value) => !value)}
                  onTestHeight={(delta) =>
                    setLayout((previous) => ({
                      ...previous,
                      test: clamp(previous.test + delta, 15, 55),
                    }))
                  }
                  onNotice={showNotice}
                />
                <SplitHandle
                  label="调整 AI 面板宽度"
                  value={layout.right}
                  onChange={(delta) =>
                    setLayout((previous) => ({
                      ...previous,
                      right: clamp(previous.right - delta, 20, 38),
                    }))
                  }
                />
                {rightCollapsed ? (
                  <button
                    className="collapsed-panel right-restore"
                    aria-label="展开 AI 面板"
                    onClick={() => setRightCollapsed(false)}
                  >
                    <PanelRightOpen size={16} />
                    <span>AI 辅导</span>
                  </button>
                ) : (
                  <AssistantPanel
                    problem={problem}
                    result={result}
                    loading={loading}
                    hintLoading={hintLoading}
                    error={diagnosisError}
                    onDiagnose={() => void diagnose()}
                    onHint={() => void nextHint()}
                    onCollapse={() => setRightCollapsed(true)}
                  />
                )}
              </div>
              <nav className="mobile-panel-nav" aria-label="工作台面板">
                <button
                  className={mobilePanel === "problem" ? "active" : ""}
                  onClick={() => {
                    setMobilePanel("problem");
                    setLeftCollapsed(false);
                  }}
                >
                  <BookOpen size={16} />
                  题目
                </button>
                <button
                  className={mobilePanel === "code" ? "active" : ""}
                  onClick={() => setMobilePanel("code")}
                >
                  <Code2 size={16} />
                  代码
                </button>
                <button
                  className={mobilePanel === "assistant" ? "active" : ""}
                  onClick={() => {
                    setMobilePanel("assistant");
                    setRightCollapsed(false);
                  }}
                >
                  <Sparkles size={16} />
                  AI 辅导
                </button>
              </nav>
            </div>
          ) : (
            <main className="page-container">
              {page === "route" ? (
                <ProgressPage data={data} onSelect={selectProblem} />
              ) : (
                <HistoryPage refreshKey={refreshKey} />
              )}
            </main>
          )}
          <footer className="app-statusbar">
            <span>
              <span className="tiny-dot" />
              {activeCode ? "专注当下这一题" : "每一次思考，都在积累"}
            </span>
            <span className="statusbar-right">
              <span className="status-shortcut">
                <Command size={10} />
                本地草稿 · 自动保存
              </span>
              <span>{LANGUAGES[language].label}</span>
              <span>AI 辅导仅作静态分析</span>
            </span>
          </footer>
          {libraryOpen && (
            <LibraryDrawer
              problems={data.problems}
              currentId={problem.id}
              completed={completed}
              onSelect={selectProblem}
              onClose={() => setLibraryOpen(false)}
            />
          )}
          {settingsOpen && (
            <SettingsDialog
              problemIds={data.problems.map((item) => item.id)}
              getUnsavedDrafts={() =>
                Object.fromEntries(
                  [...dirtyDrafts.current].map((id) => [
                    id,
                    memoryDrafts.current[id],
                  ]),
                )
              }
              getMemoryDrafts={() => ({ ...memoryDrafts.current })}
              onClose={() => setSettingsOpen(false)}
              onResetLayout={resetLayout}
              onImported={() => {
                if (!problem) return;
                if (dirtyDrafts.current.has(bufferKey(problem.id, language))) return;
                try {
                  const restored = restoreCode(
                    problem.id,
                    problemTemplate(problem, language),
                    localStorage,
                    language,
                  );
                  if (restored !== snapshot.current?.code) updateCode(restored);
                } catch {
                  setStorageError(true);
                }
              }}
            />
          )}
        </>
      )}
      {notice && (
        <div className="toast" role="status">
          <Check size={16} />
          <span>{notice}</span>
          <button
            className="icon-button"
            aria-label="关闭通知"
            onClick={() => setNotice("")}
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
