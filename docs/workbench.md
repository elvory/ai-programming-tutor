# V3 编程工作台

> 阶段说明：本文记录早期 React 工作台迁移。四语言、画像、Docker API 和网页运行已在后续阶段完成；文中的旧功能范围不作为当前交付声明。当前范围与启动方法见 [README](../README.md)，最终验证见 [Day 2 验收](../outputs/day2-final-acceptance-report.md)。

本次迁移升级界面，保留现有题库、Python 业务规则、DeepSeek Responses 请求、结构化输出与三级 Hint 严格校验。正式学习数据不做迁移或重置。

## 架构与迁移范围

| 模块 | 原界面 | 新工作台 |
| --- | --- | --- |
| UI | Streamlit | React + TypeScript + Vite |
| 编辑器 | streamlit-code-editor / Ace | 本地打包的 Monaco 与 Python 高亮 |
| 布局 | Streamlit 列与容器 | 可拖动三栏、可调测试区、移动标签切换 |
| 业务 | `services/*.py` | 复用同一组 Python 服务，FastAPI 提供薄接口 |
| 草稿 | Streamlit 会话内 | 浏览器按题 localStorage 持久化，支持显式导入/导出 |
| 诊断 | 已验收的 DeepSeek Responses API | 沿用同一个 `analyze_code` 和严格校验，不改变模型协议 |
| 记录与绿墙 | 本地 JSON / Python 活动服务 | 共享已有路径与 Python 统计，不重建数据 |

原 `app.py`、`pages/`、Ace 包装器及其测试保留。旧练习页仅增加草稿导出入口，不自动将会话内容迁移到另一界面。保留旧浏览器标签页完成导出，避免 Streamlit 会话结束后内存草稿无法恢复。

## 运行

环境要求：Python 3.10+，Node.js 22.12+。项目使用 `D:\anaconda\envs\ai-study\python.exe` 验证。

```powershell
Set-Location 'D:\Projects\Python\ai-programming-tutor'
& 'D:\anaconda\envs\ai-study\python.exe' -m pip install -r requirements.txt
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
.\scripts\start_workbench.ps1
```

打开 `http://127.0.0.1:8000`。FastAPI 同源提供构建产物和 `/api`，不依赖外部 CDN。监听地址默认是本机。启动脚本不会修改 `.env`、安装依赖、构建前端或清空数据；缺少构建产物时会提示先构建。

开发时使用两个终端：

```powershell
# 终端一：项目根目录
& 'D:\anaconda\envs\ai-study\python.exe' -m uvicorn backend.app:app --host 127.0.0.1 --port 8000

# 终端二：项目根目录
npm.cmd --prefix frontend run dev
```

开发网址 `http://127.0.0.1:5173`，Vite 将 `/api` 代理至 `127.0.0.1:8000`。`.env` 仍只在既有诊断服务端按原逻辑加载，不进入前端构建或浏览器响应。浏览器发送的练习代码不应包含秘密信息。

## 交互边界

- 桌面提供题目／代码与测试／AI 三栏，分隔条支持拖动和键盘调整；左右面板可折叠，支持恢复布局与编辑器全屏。面板比例、字体和草稿是当前浏览器的偏好。
- 题库搜索、难度与标签筛选调用 Python 题库服务。题解没有独立内容时显示空状态和官方链接，不编造解法。
- Monaco 提供语法高亮、行号、缩进、括号匹配和基于编辑器语言能力的补全。它没有 Python 语言服务器，因此补全不等同于完整的 Python 类型分析；不伪装格式化能力。
- 测试区展示真实题库示例、解释与预期输出；实际输出和执行时间不会凭空出现。没有执行器，不运行任意 Python 代码。
- AI 请求一次返回三级 Hint，但只有第一级先显示；展开下一条走原 Python Hint 状态机并更新原记录的 `hints_used`。末级变为完成状态。
- 修改代码、切题或再次诊断使旧结果失效。界面通过快照检查，接口通过工作区版本和请求标识检查；模型返回后先暂存，浏览器确认仍有效才接受并保存诊断，避免网络取消后旧请求仍写入历史。
- AI 诊断、记录本地提交、用户自报 LeetCode 通过仍是独立操作。本地提交才影响绿墙，通过须用户明确确认，均不伪装判题。
- 新草稿即时写入本浏览器 localStorage，包括空字符串；异步响应不能替换草稿。浏览器清除站点数据会删除浏览器草稿，请适时导出备份。浏览器拒绝存储时会显示提示。
- 导入兼容 `{schema_version: 1, drafts: {"题号": "代码"}, exported_at: "ISO时间"}`，已有本地稿优先，不静默覆盖。重置到模板需要确认。

## 接口

所有错误使用安全中文 `detail`，不回传上游请求头、密钥或原始异常。工作区由浏览器标签页 UUID 标识；`revision` 单调递增，过期操作返回 409。工作区诊断状态在单进程内存中，重启服务器后需要重新诊断；浏览器草稿不受服务器重启影响。

| 接口 | 用途 |
| --- | --- |
| `GET /api/health` | 本地服务可用性 |
| `GET /api/bootstrap` | 真实题库、8 阶段路线、Python 统计和 365 天热力图 |
| `GET /api/problems` | 搜索、难度、重复 `tags` 参数组合筛选 |
| `GET /api/history` | 兼容旧记录的诊断与活动展示行，可按 `problem_id` 筛选 |
| `POST /api/workspace/sync` | 同步当前题号、代码和版本，使旧请求失效 |
| `POST /api/diagnoses` | 调原诊断服务，产生待接受结果，不立即写记录 |
| `POST /api/diagnoses/accept` | 确认快照仍有效，保存一次记录，返回 Hint 1 |
| `POST /api/hints` | 展开下一条并持久化 Hint 使用情况 |
| `POST /api/submissions` | 记录一次主动本地提交，复用活动幂等接口 |
| `POST /api/accepted` | 明确确认后保存用户自报通过 |

## 测试与安全验收

```powershell
& 'D:\anaconda\envs\ai-study\python.exe' -B -m unittest discover -s tests -v
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
git diff --check
```

Python 测试使用临时记录、假密钥和模拟网络；前端测试模拟接口。`tests/browser_server.py` 是专用浏览器验收夹具：创建临时记录并替换 HTTP 传输，不读取真实 `.env`，不请求真实 DeepSeek。它不是生产模式，不要用于日常学习。

```powershell
# 在前端已构建的情况下，用临时数据打开与生产相同的界面
& 'D:\anaconda\envs\ai-study\python.exe' -B tests/browser_server.py --port 8000
```

浏览器验收应覆盖 1440px 三栏、1024px 中屏、390px 移动端、Monaco 编辑、刷新/切题/切页草稿恢复、分栏拖动/折叠/全屏、三级 Hint、失败保留代码、慢响应过时隔离、提交和通过分离、控制台与请求失败。

已有可重复的真实浏览器断言脚本，先构建前端并在终端一运行上述专用夹具，在项目根目录的终端二执行：

```powershell
npx.cmd --yes --package @playwright/cli playwright-cli --session tutor-qa open http://127.0.0.1:8000
npx.cmd --yes --package @playwright/cli playwright-cli --session tutor-qa run-code --filename tests/browser/core.js
npx.cmd --yes --package @playwright/cli playwright-cli --session tutor-qa run-code --filename tests/browser/boundaries.js
npx.cmd --yes --package @playwright/cli playwright-cli --session tutor-qa run-code --filename tests/browser/migration.js
```

三个脚本按顺序执行，在独立浏览器会话中覆盖 33 个检查点；脚本会编辑合成草稿并操作临时数据，只能对专用夹具使用。结束后关闭夹具，常规运行请使用 `scripts/start_workbench.ps1`。迁移测试会下载合成草稿备份到忽略的 `work/playwright/`。

本次开发不得真实调用 DeepSeek，也不得修改正式学习记录。正式 `data/` 文件修改前后比较 SHA-256；密钥文件不读取或修改。当前实现仍是单机单 Python 进程工具，不为多进程部署添加数据库，也不新增安全代码执行环境。
