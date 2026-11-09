# AI Programming Tutor：Day 2 最终验收报告

日期：2026-11-09。实际项目：`D:/Projects/Python/ai-programming-tutor`。

分支和 HEAD：`main / 9911e0524ee3dc9e9d9f79d91b4c5552bf2bcc33`。本轮以开工时的真实工作区为基线，保留已有 M1、Day 1 未提交改动及所有原阶段报告。

**结论：当前本地项目已达到本轮课程教学原型的交付范围。本轮功能回归和构建验证通过；交付收尾时 Docker Linux 引擎不可连接，演示前需启动并复查。本轮只修改文档、忽略规则、启动错误指引和一条过时浏览器断言，没有新增产品功能。**

完整数据见 [day2-test-results.json](day2-test-results.json)，答辩文字见 [defense-materials.md](defense-materials.md)。本报告严格区分 Mock、真实模型与真实 Docker。

## 1. 最终功能验收表

| 功能 | 结果与证据 | 范围 |
|---|---|---|
| 首页和仪表盘 | 通过：工作台、学习概览指标和导航可用 | React 实际浏览器；Streamlit 兼容流程由 AppTest 回归 |
| 八阶段路线 | 通过：8 个阶段保留，可进入实际题目 | 真实 Python 服务 + 浏览器 |
| 32 道题 | 通过：题库/schema/搜索/路由回归，32×4 模板检查 | 不代表 32 题均可执行或判题 |
| 四语言编辑器 | 通过：Monaco 模型、语言高亮、切换及模板 | Python、Java、C、C++ |
| 逐题逐语言草稿 | 通过：独立编辑、切题、刷新、空草稿、导入冲突和备份 | 专用浏览器，不接触个人 profile |
| DeepSeek 结构化诊断 | 通过：Mock 故障回归；另一次真实浏览器请求成功 | 实网本轮仅验证 Python 样例 |
| 三级 Hint | 通过：1→2→3，最终禁用；历史记录更新 | Mock 和真实 AI 均分别验证 |
| 诊断历史 | 通过：来源、语言和 Hint 使用展示 | 写入临时数据，不修改正式历史 |
| 本地提交 | 通过：主动点击才新增，诊断/运行不新增 | 实际服务读写临时 JSON |
| 365 天绿墙 | 通过：365 格、提交日和计数规则 | 与完成状态分离 |
| 六维完成度雷达 | 通过：分类、分母、去重、悬停及样本说明 | 自报完成度，不是实际能力评测 |
| 推荐题单 | 通过：绿墙下展示、切阶段、点击进题、语言保留 | 对应真实题库 |
| Python Two Sum 网页运行 | 通过：正误解、语法/运行错误、超时和旧结果隔离 | 真实 Docker，一个公开示例 |
| 桌面/移动布局 | 通过：三栏、拖动/折叠/全屏、1024px/390px | 无页面横向溢出 |

Java/C/C++ Docker 执行、全 32 题正式本地判题、账号和云同步均未实现，也未在本轮开发。

## 2. 自动化测试结果

| 检查 | 最终结果 | 通过/失败/跳过的说明 |
|---|---|---|
| Python unittest | 197 项：182 通过，0 失败，15 跳过 | 15 项真实 Docker 默认 opt-in，未算作通过 |
| 前端 Vitest/RTL | 71/71 通过，11 文件 | 无删除、跳过或弱化原测试 |
| TypeScript | 通过 | `npm run typecheck` |
| Vite 生产构建 | 通过 | `tsc -b && vite build` |
| Python 语法 | 48 文件通过 | AST 检查，不生成 pyc，不执行学生代码 |
| PowerShell 语法 | 通过，0 错误 | 启动脚本 AST 检查 |
| Python 依赖 | 通过 | `pip check` 无损坏依赖 |
| 前端依赖 | 通过 | `npm ls --depth=0` 无缺失/非法依赖 |
| Git 文本差异 | 通过 | tracked/cached 及新增文本分别检查 |

本轮安装/升级依赖：**0**。requirements、package.json 和 package-lock.json 未修改。

实测环境：Python 3.10.20、Node.js 24.14.1、npm 11.11.0、FastAPI 0.162.0、Pydantic 2.13.4、Uvicorn 0.51.0、React 19.3.1、Vite 7.3.7、Vitest 3.2.7、TypeScript 5.9.3。它们是本机验证版本，不代表全部可能兼容版本。

保留的提示：Monaco 大包、Streamlit AppTest 的 ScriptRunContext 提示、TestClient/httpx 弃用提示。它们没有造成最终测试或构建失败，本轮没有以升级依赖扩大范围。

### 浏览器回归

| 流程 | 结果 | 模型来源 |
|---|---|---|
| 旧主流程 core | 15 检查点通过 | Mock HTTP |
| 边界与布局 | 17 检查点通过 | Mock 超时/慢响应 |
| 旧草稿迁移/导出 | 3 检查点通过 | 无真实模型 |
| 四语言、画像、题单 | 70 检查点通过 | Mock HTTP |
| 网页执行与状态隔离 | 71 检查点通过，10 次执行请求 | AI Mock；代码真实 Docker |

合计 176 个浏览器检查点是各脚本的断言数，不能解释成 176 个独立产品功能。另有下面单独的真实 AI 浏览器验收。

为保护阶段材料，四语言和执行脚本的 Day 2 运行副本只调整端口/截图路径；没有覆盖原阶段截图或修改这些脚本的判定标准。

## 3. 真实 API 验收情况

**本轮代理在真实浏览器中手动点击一次“AI 诊断”，经过原 `llm_service` 和真实 DeepSeek HTTP，成功完成。不是 Mock，也不是用历史结果代替本轮验证。**

- 模型：`deepseek-flash`，来源 `deepseek`，返回 `is_mock=false`。
- 页面诊断、候选接受、两次 Hint 展开接口均为 HTTP 200。
- 使用合成的 Two Sum 相邻比较/越界代码，不发送个人代码或秘密。
- 严格校验后的错误类型、知识点、分析与恰好三级 Hint 可用。
- 初始只显示 Hint 1，逐次显示 2、3，最后按钮禁用。
- 人工审阅：指出 `nums[i+1]` 越界及只检查相邻元素的问题；三个 Hint 从题意、反例到索引对关系逐步推进，没有完整可提交程序。
- 临时历史中只有 1 条诊断，Hint 使用为 1、2、3；活动条目、提交数和完成题数均为 0。
- 通过临时验收进程设置最多一次上游调用，不自动重试、不查询账户或输出密钥。

配置由原服务在服务端按既有逻辑加载；本轮没有人工读取/展示 `.env` 文件内容，也没有改写 `.env`。真实请求可能产生费用，未查询或推断实际账单。

证据：[真实 AI 三 Hint 截图](day2-live-ai.png)及验收 JSON 的 `live_ai`。这只是一次样例验收，不代表所有语言或所有输入的模型质量都已实网验证。该次分析较长，表达精炼度列为未来教学质量改进项，不在本轮改 Prompt 或协议。

官方 Responses 格式核对见 [DeepSeek 官方说明](https://api-docs.deepseek.com/guides/responses_api/)。本报告对兼容性的结论以当前代码与实际单次响应为限。

## 4. 真实 Docker 验收情况

真实验收执行时 Linux Engine 可连接，builtin seccomp 启用，复用已有镜像；本轮没有拉取镜像或修改安全配置。

```text
python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
```

独立 Docker 测试最终 **15/15 通过、0 失败、0 跳过**：正误解、语法/运行错误、无限循环、双流输出限制、内存 OOM、非 root/只读/网络/CPU/PID、进程洪泛、重复隔离、后台进程、跨服务实例并发、缺镜像、API 闭环及独立 watchdog。

浏览器再次完成 10 次真实执行：正确示例、错误返回、语法错误、运行异常、超时，以及编辑 A→B→A、切语言、切题的旧结果隔离。该次无限循环沙箱耗时约 3047 ms；它包含启动/驱动/通信开销，不是纯算法耗时。

真实验收结束时，M1 容器和执行守护进程残留均为 0；未停止或清理用户其他 Docker 资源。交付收尾再次查询时，Docker Linux 引擎管道不可连接，因此该时点不能重新确认容器清单。测试进程和测试端口已单独复核，无残留。

### 首轮失败记录

在 Python/前端回归与构建同时运行时，Docker 测试初始化的 `docker ps` 超过现有 5 秒时限：**0 项执行、1 个 setUpClass 错误**。负载结束后同一查询约 0.109 秒返回，随后串行原样重跑 15 项全部通过。没有提高时限、放宽隔离或跳过用例。首次失败保留在验收 JSON 中。

## 5. README 修改情况

保留原说明与 M1/Day 1 内容，修正“前端未接入执行”等过时描述，补齐：

1. 项目定位、当前功能及明确范围。
2. 技术栈、系统架构 Mermaid 图和目录结构。
3. 本机 Python/Node 环境、首次安装与日常启动的区别。
4. 真实项目/Python 路径、后端脚本和直接启动、Vite 开发/生产构建。
5. Docker Desktop/WSL2/Linux context、预置镜像及安全预算。
6. DeepSeek 服务端配置、当前项目模型白名单和真实请求费用边界。
7. 网页演示步骤、操作与学习统计的区别。
8. 自动化、真实 Docker、真实 AI 的分离说明及已知限制。

`docs/workbench.md` 和 `docs/execution-m1.md` 仅增加“历史阶段说明”与当前入口链接，保留原文，避免把历史设计当成当前状态。

启动脚本只修正缺构建时的错误指引为 `npm.cmd --prefix frontend ci` / `run build`，没有改变启动逻辑。使用真实 Python 路径与该脚本在 18000 端口完成烟测：健康检查和生产静态首页均 HTTP 200；此端口仅测普通启动，执行仍使用白名单 8000/5173。

## 6. Git 和安全检查

- 开工先记录 branch、HEAD、status、diff --stat 和完整未跟踪清单。
- 当前仍为 `main / 9911e0524ee3dc9e9d9f79d91b4c5552bf2bcc33`，原有 M1/Day 1 改动和阶段报告保留。
- 不执行 add、commit、push、reset、clean；没有同步远程，不能据此声称 GitHub 已更新。
- 跟踪状态检查：实际 `.env`、正式 records/activities、草稿导出均未被 Git 跟踪；`.env.example` 是保留的配置模板。
- `.gitignore` 保留 `.env`、`.env.*`、`!.env.example`、个人学习数据和 work，补充任意层 node_modules/dist、常见缓存、嵌套 Playwright 临时文件、日志及两种草稿导出文件名。
- 只对必要文本和模板安全特征检查；不扫描真实 `.env` 内容，不输出匹配值。未发现常见密钥/私钥模式，配置模板确认是占位值。
- 没有清理用户缓存、删除阶段材料或读取常用浏览器 profile。验收仅使用独立会话与临时记录。

静态扫描有模式覆盖范围，不能替代专用秘密检测或外部账户安全审计。本轮没有以读取真实密钥进行反向匹配。

## 7. 数据完整性检查

本轮基线是 **Day 2 开工实测值**，没有回滚为 Day 1 的旧哈希；用户在阶段间新增的记录完整保留。

| 文件 | Day 2 前后 SHA-256 |
|---|---|
| records.json | `ce973d6d0d4378f814a3869c7191d62c8bcd6deefbc2371e6199347c9ea2732c` |
| activities.json | `969d71dd870d84e6c4fa190e2863ff28a2e661ea73421a0ab3bc13b3ce2bf0c6` |
| problem_catalog.json | `cb40a383db2de61487aae67901a1412111cc611d72f8f7560730c977a6f80958` |
| problem_templates.json | `01536dba3426b8e63bee08eb98fb4c8e13b0f6998ee50d681b6a89eb98813508` |

同时核对开工基线中的业务源码、M1、Day 1、依赖、历史报告和截图；除本轮声明的少数交付文件外保持一致。没有修改题库、模板、统计、草稿、AI 或 Docker Runner。

## 8. 本轮修改文件清单

已有文件的最小修改：

- `D:/Projects/Python/ai-programming-tutor/README.md`：最终范围、架构、环境、启动与演示文档。
- `D:/Projects/Python/ai-programming-tutor/.gitignore`：缺失的本地缓存、构建和草稿产物规则。
- `D:/Projects/Python/ai-programming-tutor/docs/workbench.md`：历史阶段提示。
- `D:/Projects/Python/ai-programming-tutor/docs/execution-m1.md`：历史阶段提示。
- `D:/Projects/Python/ai-programming-tutor/scripts/start_workbench.ps1`：缺构建时的指引文案。
- `D:/Projects/Python/ai-programming-tutor/tests/browser/core.js`：修正 #198 未开放执行的旧断言，并增加按钮禁用及无伪造结果检查。

新交付：本报告、`outputs/defense-materials.md`、`outputs/day2-test-results.json` 和 `outputs/day2-*.png` 截图。临时验收脚本位于忽略的 work 内，不属于产品功能或待提交源码。

旧 core 脚本修复前已实际观察到失败；修复后该流程由 13 增至 15 检查点，原其余检查保留。没有为测试全绿删除、跳过或弱化已有断言。

## 9. 已知问题与未验证项

1. 只运行 Python Two Sum 的一个公开示例；不存在全题正式本地判题或官方 Accepted 同步。
2. JSON 与执行会话按本机单进程使用；同步接口无取消/排队进度和跨设备状态。
3. 模型回答非确定性，本轮只人工审阅一个 Python 样例；分析表达偏长，未来可再评估教学质量。
4. Docker/WSL 在主机资源紧张时可能出现管理查询超时，建议演示和验收串行运行。
5. Monaco 首次加载较大；测试框架已有弃用提示，后续按独立维护任务处理。
6. 未进行生产公网、多租户、容器逃逸、宿主崩溃和长期 Engine 失联的完整故障审计，不能宣传为生产级恶意代码平台。
7. C/C++ 编译与 Java 执行不在当前功能内，不把编辑器/模板测试解释为四语言执行验收。

8. 交付收尾复查时，Docker Linux 引擎管道不可连接。该次环境检查不能计为通过，也不否定此前已完成的真实测试；演示前需启动 Docker Desktop、确认 Linux Engine 和镜像可用。本轮未为收尾检查启动或重新配置引擎。

## 10. 最终交付建议

- 本地课程演示可用，按 README 的实际环境和端口启动，演示前确认 Docker 与 AI 账号可用。
- 答辩按 defense-materials 中的架构、功能、真实证据与限制组织，不夸大完成度或测试覆盖。
- 提交源码时由负责人审核未跟踪文件；保留 README、后端/前端源码、模板、Prompt、测试和必要文档，不包含密钥、个人记录、草稿、依赖目录和临时文件。
- 本轮遵守不提交/推送要求；后续是否授权 Git 操作由负责人决定，本轮不继续开发。

验证命令、原始检查摘要与截图均在项目中可查看；Mock 诊断截图明确属于模拟学习数据，真实 AI 截图单独标识。
