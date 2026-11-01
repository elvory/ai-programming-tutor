import { useRef, useState } from "react";
import { Download, FolderInput, RotateCcw, ShieldCheck, X } from "lucide-react";
import { exportDrafts, importDrafts } from "../storage";

interface Props {
  problemIds: number[];
  onClose: () => void;
  onImported: () => void;
  onResetLayout: () => void;
  getUnsavedDrafts: () => Record<string, string>;
}
export function SettingsDialog({
  problemIds,
  onClose,
  onImported,
  onResetLayout,
  getUnsavedDrafts,
}: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  function download() {
    try {
      const url = URL.createObjectURL(
        new Blob([exportDrafts(problemIds, localStorage, getUnsavedDrafts())], {
          type: "application/json;charset=utf-8",
        }),
      );
      const link = document.createElement("a");
      link.href = url;
      const localDate = new Date().toLocaleDateString("sv-SE", {
        timeZone: "Asia/Shanghai",
      });
      link.download = `ai-tutor-drafts-${localDate}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setMessage("草稿备份已导出。");
      setFailed(false);
    } catch {
      setMessage("无法读取浏览器草稿，请检查浏览器存储权限。");
      setFailed(true);
    }
  }
  return (
    <div
      className="dialog-backdrop centered"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="settings-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="工作台设置"
      >
        <header>
          <div>
            <strong>工作台设置</strong>
            <p>把专注留给代码，把草稿妥善保留。</p>
          </div>
          <button
            className="icon-button"
            aria-label="关闭设置"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        <div className="settings-body">
          <div className="settings-section-title">草稿备份与迁移</div>
          <p>
            每道题的草稿保存在当前浏览器，刷新与切页后可以恢复。清除浏览器数据前，请先导出备份。
          </p>
          <div className="settings-actions">
            <button className="secondary-button" onClick={download}>
              <Download size={15} />
              导出全部草稿
            </button>
            <button
              className="secondary-button"
              onClick={() => input.current?.click()}
            >
              <FolderInput size={15} />
              导入草稿 JSON
            </button>
          </div>
          <input
            ref={input}
            type="file"
            accept="application/json,.json"
            hidden
            aria-label="导入草稿文件"
            onChange={async (event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              try {
                const result = importDrafts(
                  await file.text(),
                  problemIds,
                  localStorage,
                );
                setMessage(
                  `已导入 ${result.imported} 道题的草稿；${result.conflicts} 份同题已有草稿保留不变${result.ignored ? `，${result.ignored} 份不在当前题库中已忽略` : ""}。`,
                );
                setFailed(false);
                onImported();
              } catch (error) {
                setMessage(
                  error instanceof Error ? error.message : "草稿导入失败。",
                );
                setFailed(true);
              }
              event.target.value = "";
            }}
          />
          <div className="migration-note">
            <ShieldCheck size={18} />
            <p>
              从旧版 Streamlit
              迁移：先在旧练习页展开「导出当前会话草稿到新版工作台」并导出，再在此导入。同题已有草稿不会被覆盖。
            </p>
          </div>
          {message && (
            <div
              className={failed ? "inline-error" : "inline-success"}
              role="status"
            >
              {message}
            </div>
          )}
          <div className="settings-section-title">工作台布局</div>
          <p>面板宽度、测试区高度和编辑器字号会在此浏览器中记忆。</p>
          <button className="secondary-button" onClick={onResetLayout}>
            <RotateCcw size={15} />
            恢复默认布局
          </button>
        </div>
      </section>
    </div>
  );
}
