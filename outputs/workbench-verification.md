# AI Programming Tutor 工作台重构验收

验收日期：2026-11-02（北京时间）。截图来自本地实际运行的生产构建，由 FastAPI 同源提供；AI 内容是专用验收夹具的模拟网络响应，不是本次真实调用 DeepSeek。

## 交付结果

- React / TypeScript / Vite + 本地 Monaco 三栏 IDE 工作台，替换练习界面体验；旧 Streamlit / Ace 页面保留。
- FastAPI 薄适配层复用现有 Python 题库、路线、诊断、Hint、历史、活动和绿墙服务，不复制业务规则。
- 题目、编辑器与 AI 独立滚动，左右可拖动/折叠，底部测试区高度可调，编辑器全屏、字号和面板尺寸可记忆。
- 1440/1600px 三栏、1024px 中屏、390px 移动标签布局均实际检查。768–1023px AI 可作为抽屉展开。
- 草稿按题持久化，保留空代码；刷新、切题、导航恢复。浏览器写入失败时逐题保留最新内存稿，旧存储稿不能覆盖它；备份优先导出最新未落盘稿。
- 旧 Streamlit 会话显式导出 JSON，新工作台导入不覆盖已有稿。重置模板须确认。
- 一次模型诊断仍生成三级 Hint，默认显示一级、逐次展开；Hint 更新原记录，携带预期等级防止网络重试跳级。
- 诊断候选与接受分离，版本、题号、代码和请求标识共同隔离过时结果，防止未接受的结果写历史。
- 测试面板仅显示真实题库示例、预期输出和未执行状态；没有执行任意 Python 代码，没有伪造 Accepted、运行时间或实际输出。

## 自动化与浏览器验证

| 检查 | 结果 |
| --- | --- |
| 全部 Python 测试 | 106/106 通过，包含原有 86 项、18 项新 API 测试及 2 项草稿导出测试 |
| 前端测试 | 20/20 通过，含草稿、存储失败、导入、导出、慢响应、Hint 组件与请求层 |
| TypeScript | 通过 |
| Vite 生产构建 | 通过；Monaco 为本地独立 chunk 与 worker，无 CDN |
| Python 语法 | 27 个文件通过 |
| Playwright 生产构建 | 33/33 检查点通过 |
| 最终正常流程页面错误 / 控制台错误 / 请求失败 | 0 / 0 / 0 |
| 本次真实 DeepSeek 请求 | 0 |
| 正式数据 SHA-256 | 修改前后完全相同 |
| 已验收诊断服务与 Prompt | 文件 SHA-256 不变 |
| Git diff 与新文本文件空白检查 | 通过 |

浏览器三组断言位于 `tests/browser/core.js`、`boundaries.js`、`migration.js`，使用 `tests/browser_server.py` 的临时数据和 fake HTTP 传输。脚本先校验专用夹具响应标记，普通服务没有标记时会在写入前拒绝运行，避免误操作正式记录。超时测试的预期 502 与主动取消请求不计入“最终正常流程”结果。

## 截图

| 文件 | 场景 |
| --- | --- |
| [workbench-desktop.png](workbench-desktop.png) | 1600×1000 三栏与欢迎态 |
| [workbench-ai-mock.png](workbench-ai-mock.png) | 1600×1000 单条 Hint，模拟网络响应 |
| [workbench-1440.png](workbench-1440.png) | 1440×900 三栏 |
| [workbench-1024.png](workbench-1024.png) | 1024×768 中屏 |
| [workbench-mobile.png](workbench-mobile.png) | 390×844 Monaco 与测试区 |
| [workbench-mobile-ai-mock.png](workbench-mobile-ai-mock.png) | 390×844 AI 面板，模拟网络响应 |
| [workbench-progress.png](workbench-progress.png) | 学习统计、365 格绿墙及路线（临时活动） |

## 修改与新增文件

本次合并修改 `.gitignore`、`README.md`、`requirements.txt` 和 `pages/practice.py`；旧练习页仅追加显式草稿导出入口，已有界面改动仍保留。

用户原有的 `tests/test_app_flow.py`、`utils/ui.py`、`tests/test_editor.py` 和 `utils/editor.py` 保持逐字节一致。原始 7 份未提交文件副本与正式数据指纹保存在忽略目录 `work/workbench-baseline-20261102-5cdacba8/`。未读取或修改真实 `.env`。

本次新增的业务/界面与文档文件如下（不含构建缓存）：

- `backend/__init__.py`
- `backend/app.py`
- `docs/workbench.md`
- `frontend/index.html`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/public/favicon.svg`
- `frontend/src/App.test.tsx`
- `frontend/src/App.tsx`
- `frontend/src/api.test.ts`
- `frontend/src/api.ts`
- `frontend/src/components/AssistantPanel.test.tsx`
- `frontend/src/components/AssistantPanel.tsx`
- `frontend/src/components/CodePanel.tsx`
- `frontend/src/components/HistoryPage.tsx`
- `frontend/src/components/LibraryDrawer.tsx`
- `frontend/src/components/ProblemPanel.tsx`
- `frontend/src/components/ProgressPage.tsx`
- `frontend/src/components/SettingsDialog.tsx`
- `frontend/src/components/SplitHandle.tsx`
- `frontend/src/main.tsx`
- `frontend/src/monaco.ts`
- `frontend/src/storage.test.ts`
- `frontend/src/storage.ts`
- `frontend/src/styles.css`
- `frontend/src/test-setup.ts`
- `frontend/src/types.ts`
- `frontend/tsconfig.json`
- `frontend/vite.config.ts`
- `outputs/workbench-1024.png`
- `outputs/workbench-1440.png`
- `outputs/workbench-ai-mock.png`
- `outputs/workbench-desktop.png`
- `outputs/workbench-mobile-ai-mock.png`
- `outputs/workbench-mobile.png`
- `outputs/workbench-progress.png`
- `scripts/start_workbench.ps1`
- `tests/browser/boundaries.js`
- `tests/browser/core.js`
- `tests/browser/legacy-drafts.json`
- `tests/browser/migration.js`
- `tests/browser_server.py`
- `tests/test_draft_export.py`
- `tests/test_workbench_api.py`
- `utils/draft_export.py`

## 正式数据 SHA-256

| 文件 | 修改前 | 修改后 |
| --- | --- | --- |
| `data/activities.json` | `f6daba3203c5637718e3fb233067d9dac521406c706cd76c8c76086441a74e3f` | `f6daba3203c5637718e3fb233067d9dac521406c706cd76c8c76086441a74e3f` |
| `data/problem_catalog.json` | `cb40a383db2de61487aae67901a1412111cc611d72f8f7560730c977a6f80958` | `cb40a383db2de61487aae67901a1412111cc611d72f8f7560730c977a6f80958` |
| `data/records.json` | `568c6a80b5400978056a61255637aff121dddc3321f0a541fcd837530be9a9bc` | `568c6a80b5400978056a61255637aff121dddc3321f0a541fcd837530be9a9bc` |

## 运行与边界

依赖已在本地指定环境安装，前端已构建。在项目根目录执行：

```powershell
& 'D:\anaconda\envs\ai-study\python.exe' -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000`。也可使用 `scripts/start_workbench.ps1`；全新环境安装与开发模式详见 `docs/workbench.md` 和 `README.md`。

Monaco 当前提供 Python 高亮、行号、缩进、括号、词补全和基础 snippets，以及复制、确认重置、字号、全屏和“整理缩进”。没有 Python 语言服务器、完整 PEP8 格式化或安全代码执行器。Monaco 编辑器 chunk 约 654KB gzip，首次加载成本高于普通表单页。

现有 DeepSeek Responses 请求协议、Schema 和严格三级 Hint 校验保持原样，兼容性通过模拟接口和实际页面链路验证；本次按要求未重新做真实 API 验收。正常使用时由用户主动发起的诊断仍会调用现有服务并可能产生费用。教学质量仍应由用户在真实练习中评估。

旧 Streamlit 草稿只在原会话内，无法从另一个应用自动读取；请保持旧标签页，先导出再导入。浏览器草稿不等于跨设备同步。Python 工作区与 JSON 并发仍按单进程设计，服务器重启会清空短期诊断会话，草稿及持久历史不受影响。

## Git 最终状态

未暂存、提交、推送、reset 或清理旧数据。以下状态包含用户原有修改：

```text
 M .gitignore
 M README.md
 M pages/practice.py
 M requirements.txt
 M tests/test_app_flow.py
 M utils/ui.py
?? backend/
?? docs/
?? frontend/
?? outputs/
?? scripts/
?? tests/browser/
?? tests/browser_server.py
?? tests/test_draft_export.py
?? tests/test_editor.py
?? tests/test_workbench_api.py
?? utils/draft_export.py
?? utils/editor.py
```
