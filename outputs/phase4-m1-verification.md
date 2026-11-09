# AI Programming Tutor 第四阶段 M1 验收报告

日期：2026-11-09。项目：`D:/Projects/Python/ai-programming-tutor`。开发基准：`main` / `9911e0524ee3dc9e9d9f79d91b4c5552bf2bcc33`。

## 结论与范围

已实现并真实验证 Python Docker 执行、Two Sum 函数调用、容器外公开示例比较、FastAPI 执行 API、资源限制和容器回收。M1 只包含一个公开示例，不提供正式本地 Accepted，不代表 LeetCode 官方通过或生产级恶意代码隔离。

M2 Java/C/C++ 执行与 M3 前端运行 UI/正式本地判题只做设计，见 [M1 说明](../docs/execution-m1.md)。没有更改前端源码、四语言模板、DeepSeek、三级 Hint、草稿和学习统计规则。

## 架构审查与实现

- 确认旧架构是 React/Monaco → FastAPI → Python services，保留 Streamlit。
- 确认现有 32 题、8 阶段和 128 模板；现有示例是展示字符串，没有正式测试集。
- 现有 AI revision 同时在编辑和重诊断时递增，因此执行 API 不调用旧 snapshot/sync。
- 公开题目服务整体复制题目对象，因此新示例夹具和比较器放入独立执行模块，不向原 catalog 添加私有字段。
- FastAPI 仅增量接入执行模块，原诊断、Hint、提交、通过和画像接口语义不变。
- M1 采用安装好的 Docker CLI 和标准库，无需 Docker SDK 或新增包。所有宿主调用为固定 argv，源码通过 stdin 进入容器。

## 修改文件

现有文件：

- `D:/Projects/Python/ai-programming-tutor/backend/app.py`：注入独立执行服务并安装新路由。
- `D:/Projects/Python/ai-programming-tutor/README.md`：M1 入口及功能边界。

新增模块：

- `D:/Projects/Python/ai-programming-tutor/backend/execution/__init__.py`
- `D:/Projects/Python/ai-programming-tutor/backend/execution/config.py`
- `D:/Projects/Python/ai-programming-tutor/backend/execution/schemas.py`
- `D:/Projects/Python/ai-programming-tutor/backend/execution/exceptions.py`
- `D:/Projects/Python/ai-programming-tutor/backend/execution/routes.py`
- `D:/Projects/Python/ai-programming-tutor/backend/execution/service.py`
- `D:/Projects/Python/ai-programming-tutor/backend/execution/docker_runner.py`
- `D:/Projects/Python/ai-programming-tutor/backend/execution/watchdog.py`
- `D:/Projects/Python/ai-programming-tutor/backend/execution/adapters/__init__.py`
- `D:/Projects/Python/ai-programming-tutor/backend/execution/adapters/python_adapter.py`

新增测试：

- `D:/Projects/Python/ai-programming-tutor/tests/test_execution_adapter.py`
- `D:/Projects/Python/ai-programming-tutor/tests/test_execution_api.py`
- `D:/Projects/Python/ai-programming-tutor/tests/test_execution_service.py`
- `D:/Projects/Python/ai-programming-tutor/tests/test_execution_watchdog.py`
- `D:/Projects/Python/ai-programming-tutor/tests/test_docker_runner.py`
- `D:/Projects/Python/ai-programming-tutor/tests/test_docker_integration.py`

文档：`D:/Projects/Python/ai-programming-tutor/docs/execution-m1.md` 及本报告。

新增 Python/npm 依赖：**0**。requirements/package/lockfile 未修改。

## 自动化结果

| 验证 | 结果 | 范围 |
|---|---|---|
| 全部 Python unittest | 197 项，182 通过、15 按规则跳过 | 原 136 项 + 新增 46 项无 Docker 测试；真实 Docker 默认不运行 |
| 单独真实 Docker 集成 | 15/15 通过，约 22.6 秒 | 显式启用，真实 Engine 和本地镜像 |
| 前端 Vitest/RTL | 37/37 通过，8 文件 | 旧 UI、草稿、AI 和画像回归 |
| TypeScript typecheck | 通过 | tsc -b |
| 前端生产构建 | 通过 | Vite；保留既有 Monaco 大包提示 |
| Python 语法检查 | 48 文件通过 | AST 解析，不生成 pyc |
| 差异检查 | 通过 | tracked/cached diff --check；18 个新增文本文件逐个 no-index --check |
| 常见密钥/私钥模式扫描 | 0 可疑文件 | 只扫描本轮文本，不读取 .env |

Python 测试包含旧 Streamlit ScriptRunContext 提示和 FastAPI TestClient 的 httpx 弃用提示，没有因此新增或升级依赖。没有调用真实 DeepSeek。

交付前再次确认正式数据哈希、原有未跟踪报告哈希一致，M1 容器残留 0、执行 watchdog 残留 0。

## 真实 Docker 验收

开始检查时 Linux Engine 不可连接。本轮启动已安装的 Docker Desktop 后，Engine 为 Linux，32 个逻辑 CPU、约 8.12 GB 可见内存，builtin seccomp 启用。

本轮下载一次官方 `python:3.12-slim`，未构建自定义镜像；运行路径禁止隐式下载。

本轮镜像标识：

```text
python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
```

| 场景 | 真实验证结果 |
|---|---|
| Two Sum 正确返回、反向索引、中文 stdout | SUCCESS，公开示例通过，official_accepted=false |
| 错误解 | 执行 SUCCESS，但 judge.all_passed=false |
| Python 语法错误 | COMPILE_ERROR |
| 运行异常 | RUNTIME_ERROR，有受限错误信息 |
| 无限循环 | 外部 3 秒墙钟超时，终止容器 |
| stdout/stderr 洪泛 | OUTPUT_LIMIT_EXCEEDED，分别不超过 65,536 UTF-8 字节 |
| 512 MiB 内存申请 | 128 MiB cgroup 上限触发 OOM，MEMORY_LIMIT_EXCEEDED |
| 非 root / capabilities / 提权 / seccomp | UID 65534、CapEff=0、NoNewPrivs=1、Seccomp=2 |
| 外网连接 | 无法连接外部地址 |
| 根文件系统写入 | EROFS，写入失败 |
| CPU / 内存 / PID | cgroup 实际值为 0.5 核、128 MiB、64 PID |
| 进程洪泛 | 触及 EAGAIN，未越过 PID 配额 |
| tmpfs | 可写临时文件，下一次运行不存在 |
| 后台 sleep 子进程 | 主程序结束后随容器退出清理 |
| 多次运行 | 临时文件和容器独立 |
| 并发 | 同 service 及不同 service 共享锁时均返回 429，不中断原任务 |
| 缺失镜像 | SYSTEM_ERROR / IMAGE_UNAVAILABLE，无下载、无创建 |
| FastAPI → Docker | TestClient 经过真实 API/服务/容器/外部比较，成功 |
| 独立 watchdog | 到期回收精确的模拟遗留容器，退出码 0 |
| 清理 | 每项结束检查无新增 M1 容器；正常、错误、超时、输出/OOM 均确认清理 |

Engine 不可用、系统通信故障、清理失败和创建响应丢失使用 Mock 故障注入，没有为测试停止用户 Docker。强制终止 API 进程、宿主崩溃、长期 Engine 失联等未做完整真实故障演练。

## 安全边界

容器配置包含 network none、只读 rootfs、UID/GID 65534、cap-drop ALL、no-new-privileges、默认 seccomp、CPU/内存/swap/PID、有限 tmpfs 和文件预算，无宿主 bind、无 Docker Socket、无宿主环境继承。Engine 日志关闭；stdout/stderr 和管理命令输出均流式有界读取。

退出 137 不直接视为 MLE，使用 Docker OOM 证据。外部超时/输出/OOM/系统结果不能被学生协议覆盖。容器只提供不可信候选值，最终比较在容器外完成。

创建前记录随机名称并启动外部守护。清理失败或创建结果不确定时保留恢复记录/守护/锁，关闭执行，避免将暂时不存在误判为永久不存在。新 runner 在放行前先恢复登记资源，无全局 prune。

M1 控制器与 API 仍在同一可信本机进程中，拥有 Engine 管理权限。Host/Origin/loopback/token 是本地边界，不是公网多用户认证。Docker 共享内核；公网前必须独立 Worker 身份/节点和安全评审。

## 数据与 Git 保护

没有读取或修改 `.env`，没有输出真实密钥；自动化模型请求均 Mock，执行模块不加载 dotenv。没有操作浏览器用户 profile 或草稿存储。

正式数据本轮前后 SHA-256：

| 文件 | SHA-256 |
|---|---|
| records.json | `f52953ef1bdeb28624bd1b2c3903f9e6b6f7a49b5e51df182f3c7549543482de` |
| activities.json | `f6daba3203c5637718e3fb233067d9dac521406c706cd76c8c76086441a74e3f` |
| problem_catalog.json | `cb40a383db2de61487aae67901a1412111cc611d72f8f7560730c977a6f80958` |
| problem_templates.json | `01536dba3426b8e63bee08eb98fb4c8e13b0f6998ee50d681b6a89eb98813508` |

原有未跟踪阶段报告保留；未 add、commit、push、reset 或 clean。工作区保留本轮可审查改动。

## 下一步人工检查与计划

按 M1 文档启用后端，用自己的 Two Sum 代码调用 session/run，确认正误解、中文输出与错误提示。前端没有新增运行按钮，这是 M3 的范围。

M2 先做四语言同题，再做节点/矩阵适配。M3 先落实异步任务、幂等、取消、所有权和独立执行快照，再接 UI 与完整正式本地测试集。不要自动将执行计入提交、绿墙或画像。

推荐 commit 信息（未执行）：

```text
feat(execution): add isolated Python Docker runner and Two Sum example API
```
