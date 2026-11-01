import { useEffect, useState } from "react";
import { Check, ChevronRight, ListFilter, Search, X } from "lucide-react";
import { api } from "../api";
import type { Problem } from "../types";

interface Props {
  problems: Problem[];
  currentId: number;
  completed: number[];
  onSelect: (problem: Problem) => void;
  onClose: () => void;
}
export function LibraryDrawer({
  problems,
  currentId,
  completed,
  onSelect,
  onClose,
}: Props) {
  const [query, setQuery] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [results, setResults] = useState(problems);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      setError("");
      api
        .problems(query, difficulty, tags, controller.signal)
        .then((data) => setResults(data.problems))
        .catch((reason) => {
          if (reason.name !== "AbortError") setError(reason.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 160);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, difficulty, tags]);
  const allTags = [...new Set(problems.flatMap((problem) => problem.tags))];
  return (
    <div
      className="dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="library-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="题库选择"
      >
        <header>
          <div>
            <ListFilter size={18} />
            <strong>精选题库</strong>
            <span>{problems.length} 道题 · 8 个阶段</span>
          </div>
          <button
            className="icon-button"
            aria-label="关闭题库"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        <div className="library-filters">
          <label className="search-field">
            <Search size={16} />
            <input
              autoFocus
              placeholder="搜索题号、中文或英文题名"
              aria-label="搜索题目"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className="filter-row">
            <select
              aria-label="筛选难度"
              value={difficulty}
              onChange={(event) => setDifficulty(event.target.value)}
            >
              <option value="">全部难度</option>
              <option value="Easy">简单</option>
              <option value="Medium">中等</option>
              <option value="Hard">困难</option>
            </select>
            <span>组合筛选 · 所选标签全部匹配</span>
          </div>
          <div className="tag-filters">
            {allTags.map((tag) => (
              <button
                key={tag}
                className={tags.includes(tag) ? "active" : ""}
                onClick={() =>
                  setTags((previous) =>
                    previous.includes(tag)
                      ? previous.filter((item) => item !== tag)
                      : [...previous, tag],
                  )
                }
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
        <div className="library-results">
          {error && <div className="inline-error">{error}</div>}
          <div className="list-caption">
            {loading ? "正在搜索…" : `${results.length} 道匹配题目`}
          </div>
          {!error && results.length === 0 && (
            <div className="empty-state">
              <Search size={28} />
              <h3>没有匹配题目</h3>
              <p>尝试调整关键词、难度或标签。</p>
            </div>
          )}
          {results.map((problem) => (
            <button
              key={problem.id}
              className={`problem-row ${currentId === problem.id ? "selected" : ""}`}
              onClick={() => {
                onSelect(problem);
                onClose();
              }}
            >
              <span className="problem-row-status">
                {completed.includes(problem.id) ? (
                  <Check size={14} />
                ) : (
                  <span />
                )}
              </span>
              <span>
                <strong>
                  {problem.id}. {problem.title_zh}
                </strong>
                <small>
                  {problem.title_en} · {problem.tags.join(" / ")}
                </small>
              </span>
              <span
                className={`difficulty ${problem.difficulty.toLowerCase()}`}
              >
                {problem.difficulty}
              </span>
              <ChevronRight size={14} />
            </button>
          ))}
        </div>
        <footer>选择题目会自动保留当前草稿。</footer>
      </section>
    </div>
  );
}
