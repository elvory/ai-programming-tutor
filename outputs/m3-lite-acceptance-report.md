# AI Programming Tutor：72 小时冲刺 Day 1 验收报告

日期：2026-11-09。项目：`D:/Projects/Python/ai-programming-tutor`。

源码基准：`main / 9911e0524ee3dc9e9d9f79d91b4c5552bf2bcc33`。开始时 M1 后端、文档和测试均为已有未提交改动，本轮保留；没有 commit、push、reset 或 clean。

**结论：网页 → 现有 M1 FastAPI 接口 → 真实 Docker → 页面结果的 Python Two Sum 最小闭环已完成。** 当前仅运行一个公开示例，不代表完整本地测试集或 LeetCode 官方通过。

## 1. 修改文件

本轮修改已有文件：

- `D:/Projects/Python/ai-programming-tutor/frontend/src/App.tsx`：接入独立执行 hook；在既有源码上下文变化入口使旧执行结果失效，不改变原草稿写入与恢复逻辑。
- `D:/Projects/Python/ai-programming-tutor/frontend/src/components/CodePanel.tsx`：运行按钮、范围限制、忙碌状态、结果标签及新结果面板。
- `D:/Projects/Python/ai-programming-tutor/frontend/src/App.test.tsx`：执行与 AI/草稿/统计独立、编辑/切题/切语言后的迟到结果回归。
- `D:/Projects/Python/ai-programming-tutor/frontend/src/components/CodePanel.test.tsx`：更新原“所有语言均未开放”的历史断言，验证当前支持范围与禁用行为。

本轮新增文件：

- `D:/Projects/Python/ai-programming-tutor/frontend/src/executionTypes.ts`
- `D:/Projects/Python/ai-programming-tutor/frontend/src/executionApi.ts`
- `D:/Projects/Python/ai-programming-tutor/frontend/src/useExecution.ts`
- `D:/Projects/Python/ai-programming-tutor/frontend/src/components/ExecutionResultPanel.tsx`
- `D:/Projects/Python/ai-programming-tutor/frontend/src/execution.css`
- `D:/Projects/Python/ai-programming-tutor/frontend/src/executionApi.test.ts`
- `D:/Projects/Python/ai-programming-tutor/frontend/src/useExecution.test.tsx`
- `D:/Projects/Python/ai-programming-tutor/frontend/src/components/ExecutionResultPanel.test.tsx`
- `D:/Projects/Python/ai-programming-tutor/tests/browser/execution.js`

验收产物：本报告、[浏览器结果明细](m3-lite-browser-results.json)、[桌面截图](m3-lite-desktop.png)、[移动端截图](m3-lite-mobile.png)。

新增 Python/npm 依赖：**0**。没有修改后端、Docker Runner、M1 配置、题库、模板、DeepSeek 协议、Hint、统计服务或存储模块。

## 2. 实现功能

### 运行入口与结果

- Monaco 工具栏新增“运行公开示例”。
- 仅 Python + problem_id=1 开放；空代码、忙碌状态和未开放组合禁用按钮。
- Java、C、C++ 和其他题目显示明确说明，不生成运行结果。
- 调用现有 `GET /api/execution/session` 和 `POST /api/execution/run`。
- Token 仅保存在 hook 内存 ref，不写 localStorage、sessionStorage、URL 或日志。
- POST 显式发送原接口的四个字段：problem_id、language、code、request_id。
- 获取会话、运行中、HTTP/网络失败、结构异常和七种 M1 执行状态均有反馈。
- 显示 stdout、stderr、沙箱实测耗时、示例通过数量、预期结果和实际结果。
- 输出由 React 作为纯文本显示，不解释 HTML。
- 自动切换到测试结果标签；保留现有三栏、可调整结果区和移动端布局。

运行成功与答案正确分别显示。错误解可以是 SUCCESS，但公开示例为 0/1；不会显示 Accepted，也不会自动记录学习活动。

### 防重复与过时结果

执行有独立源码意图计数和运行代次，不复用 AI revision。App 的两个既有入口覆盖切题、切语言、编辑、重置、整理缩进及导入当前草稿。

- 点击后先同步锁定 ref，再更新按钮状态，防止 React 更新前快速连点。
- 编辑后立即清空旧结果；A→B→A 仍视为新意图。
- 获取 Token 期间源码失效，不再发送旧代码 POST。
- 已发出的同步 POST 不因编辑而 abort，也不提前释放忙碌状态；原请求结束后才可再运行。
- 结果必须匹配本次 request_id、题号、语言、意图和代次。
- Token 失效时清除内存缓存，用户下次点击重新获取；不自动重放运行请求。
- 接口响应验证来源、字段、计数与用例状态一致性，拒绝畸形“成功”结果。

## 3. 自动化测试结果

| 检查 | 本轮结果 |
|---|---|
| Python 全部测试 | 197 项：182 通过，15 项真实 Docker 集成按默认规则跳过 |
| 前端 Vitest / React Testing Library | 71/71 通过，11 个文件 |
| TypeScript 类型检查 | 通过 |
| 前端生产构建 | 通过 |
| 真实浏览器 + Docker | 完整验收脚本通过，10 次真实执行请求 |

前端包括原有 37 项回归及新增执行测试，覆盖 Token/请求结构、错误响应、快速连点、A→B→A、三种上下文变化、旧 AI/草稿隔离、输出纯文本及各状态面板。

Python 测试中的 Streamlit ScriptRunContext 提示和 TestClient 的 httpx 弃用提示，以及生产构建的既有 Monaco 大包提示均保留，没有因此安装依赖或扩大重构。

本轮没有重新跑 M1 全部 15 项独立 Docker 安全测试；Runner 未改变，新增前端通过下面的真实浏览器流程验证现有运行路径。

## 4. 真实 Docker 验收结果

使用已安装的 Playwright CLI 和本机浏览器，访问生产构建后的页面。后端使用原有 `tests/browser_server.py`：记录和活动写入临时目录，禁用真实 dotenv 与模型 HTTP；执行接口连接真实 Docker。没有访问用户常用浏览器 profile。

环境：Linux Docker Engine 可连接，builtin seccomp 启用，复用已有 Python 镜像。本轮没有修改安全参数或拉取镜像。

| 网页场景 | 结果 |
|---|---|
| 正确 Two Sum | 公开示例 1/1，中文 stdout、stderr 和实测耗时显示正确 |
| 错误 Two Sum | 运行成功，公开示例 0/1，不冒充通过 |
| 语法错误 | COMPILE_ERROR 和实际语法信息可见 |
| 运行异常 | RUNTIME_ERROR 和实际异常信息可见 |
| 无限循环 | TIME_LIMIT_EXCEEDED；该次沙箱测得约 3046 ms |
| 编辑 A→B→A | 原容器完成并清理，旧输出丢弃，必须重新运行 |
| Python→Java→Python | 未开放语言禁用；回到 Python 后旧输出仍丢弃 |
| #1→其他题→#1 | 其他题禁用；旧题结果不会覆盖当前代码 |
| 运行中重复点击 | 每个场景只有一次执行 POST |
| 已展开三级 Hint 后运行 | 三条 Hint 保留，不新增诊断历史 |
| 学习统计 | 提交、绿墙、六维画像前后相同 |
| 四语言草稿 | 切换及刷新后均恢复，存储实现未改变 |
| Token | localStorage/sessionStorage 中均未出现 |
| 1600×1100 桌面 | 三栏和结果区正常 |
| 390×844 移动端 | 运行按钮可见，页面无横向溢出 |
| 页面异常与容器清理 | 未捕获 page error 为 0；最终 M1 容器残留为 0 |

AI 回归使用模拟网络响应，不能据此声称验证了真实 DeepSeek 回答质量。代码运行和结果比较为真实 Docker 路径。

验收脚本曾发现 Monaco 模型切换后立即读取可见文本存在时序问题，已改为等待目标 model URI/文本；没有改动业务草稿逻辑。

复现：前端先构建，在端口 8000 启动隔离夹具并启用执行，再用独立 Playwright 会话运行 `tests/browser/execution.js`。脚本首先校验夹具响应头，拒绝向普通学习服务写入验收数据。

## 5. 数据完整性检查

本轮检查前后比较了 22 个保护文件，包括正式数据、整个 M1 Python 执行模块、后端入口、AI/练习/统计服务、浏览器存储模块、语言模块和原有未跟踪报告；**22 个文件哈希全部一致**。

正式数据 SHA-256：

| 文件 | SHA-256 |
|---|---|
| records.json | `f52953ef1bdeb28624bd1b2c3903f9e6b6f7a49b5e51df182f3c7549543482de` |
| activities.json | `f6daba3203c5637718e3fb233067d9dac521406c706cd76c8c76086441a74e3f` |
| problem_catalog.json | `cb40a383db2de61487aae67901a1412111cc611d72f8f7560730c977a6f80958` |
| problem_templates.json | `01536dba3426b8e63bee08eb98fb4c8e13b0f6998ee50d681b6a89eb98813508` |

不读取或修改 `.env`。Token 不进入验收 JSON、截图或 Git。没有真实 DeepSeek 请求，没有更改正式学习数据或常用浏览器草稿。

Git 中已有的 M1 改动与阶段报告保留，HEAD 不变。本轮不暂存、不提交、不推送。tracked/cached diff --check 通过，11 个新增文本文件的 no-index --check 无问题，常见密钥/私钥模式扫描为 0 可疑项。验收夹具与专用浏览器已关闭，CLI 中间快照移入忽略的 work 目录；交付截图和结果 JSON 保留在 outputs。

## 6. 已知限制

- 只开放 Python Two Sum 的一个公开示例，没有正式判题提交或全部测试按钮。
- 现有 M1 同步接口没有取消和进度阶段；源码变更只隔离旧结果，需等原请求结束。
- 页面刷新、关闭或网络中断不会自动停止容器，仍由 M1 的超时与回收保护；网络中断后重试可能收到后端 429。
- 执行仍需按 M1 说明启用，关闭时页面显示明确错误，不自动修改服务配置。
- 后端重启导致 Token 失效时，第一次运行可能收到 403；下一次点击会重新获取会话，不自动重放。
- 大型输出和多列测试数据需在现有结果区域滚动查看，可用分隔条调整高度。
- 不提供异步队列、账号、多语言执行或云同步，也不改变 M1 的本机部署边界。

## 7. 剩余工作与运行方式

Day 1 当前目标已完成。后续冲刺可独立评审正式测试集、更多题目及语言；本轮不实施。

常规使用时启动 Docker Desktop，在项目根目录运行：

```powershell
Set-Location 'D:\Projects\Python\ai-programming-tutor'
$env:AI_TUTOR_EXECUTION_ENABLED = '1'
& 'D:\anaconda\envs\ai-study\python.exe' -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

打开 `http://127.0.0.1:8000/`，选择 #1 两数之和和 Python 3，编辑代码后点击“运行公开示例”。本轮已完成生产构建；需要重建时使用 `npm.cmd --prefix frontend run build`。

人工建议检查自己的 Python 草稿、中文输出、正误解和运行后既有 Hint 是否保持。其他语言和题目应看到未开放说明。
