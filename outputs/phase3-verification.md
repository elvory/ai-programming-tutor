# AI Programming Tutor 第三阶段验收报告

日期：2026-11-02。实际项目：`D:\Projects\Python\ai-programming-tutor`。

本报告区分实际业务服务联调、模拟模型响应和未验证项目。所有自动化模型请求均为 Mock HTTP；没有请求真实 DeepSeek，没有读取或修改真实 `.env` 内容，没有执行学生代码。截图来自临时活动与诊断数据，不是用户的正式学习记录。

## 1. 审计与架构

开始修改前确认 `main` / HEAD `3cec88d`，工作区干净，已有分支比 `origin/main` 领先一个提交。检查 React 结构、FastAPI 路由、Python services、Responses 调用链、Monaco、浏览器草稿键、三个正式数据文件结构和测试。

最终保留 React + TypeScript + Vite → FastAPI → Python services，Monaco 本地打包编辑器；原 Streamlit/Ace 的 Python 页面继续保留。图表新增 Recharts，没有整体重建或改变原 32 题描述、题号和八阶段路线。

## 2. 四种语言与 Monaco

| 语言 | ID / Monaco 模式 | 后缀 | 模板覆盖 | 编辑/高亮/基础补全 |
| --- | --- | --- | --- | --- |
| Python 3（默认） | python | .py | 32/32 | 已通过 |
| Java | java | .java | 32/32 | 已通过 |
| C | c | .c | 32/32 | 已通过 |
| C++ | cpp | .cpp | 32/32 | 已通过 |

Java 引入本地 java contribution，C/C++ 使用 Monaco 本地 C 系列 tokenizer，分别注册基础 snippets；Python 保留原补全。四种语言使用题号与语言独立的 Monaco model URI，保留行号、自动缩进、括号匹配、多行编辑、主题、字号、复制、全屏和独立滚动。组件测试验证 language/path 参数，真实浏览器验证独立 model URI 与实际关键字高亮。

没有语言服务器或完整 IDE 语义补全；“整理缩进”不是完整语言格式化器。没有编译/执行/自动判题功能，测试面板继续明确显示尚未执行代码。

## 3. 32 题模板

原 Python 模板逐字保留。新增独立 `data/problem_templates.json` 提供 96 份 Java/C/C++ 骨架，共 128 份四语言模板。服务只读合并、按文件版本缓存，并要求题号和 slug 匹配，防止自定义题库套用错误签名。自定义题目缺少目标模板时返回 422，不破坏原工作区。

链表/树节点定义以判题器约定注释提供，避免正式提交重复声明；C 的数组长度、二维输入列数、二维输出 returnColumnSizes、内存所有权均有明确约定。字符网格和整数网格分别处理，没有复制同一模板充当所有题目。模板包含 TODO 或占位返回，不是算法答案。

精确的 32 题三种新增语言签名表见 [模板接口说明](../docs/template-interfaces.md)。

- **已通过**：32 题四语言覆盖、原题库兼容、复杂接口独立字面量断言、9 个模板测试、96 个新增签名静态复核。
- **已通过**：32 份 Python ast.parse；32 份 Java 模板实际 javac 编译，仅临时目录和判题器节点桩，没有运行生成的类。
- **部分通过**：C/C++ 已完成签名、结构、头文件与内存约定静态检查。
- **未测试**：C/C++ 实际编译（当前 PATH 未找到编译器）、最新在线 LeetCode 接口和官方判题。

## 4. 草稿保护

Python 保留 `ai-tutor:draft:v1:<题号>`，无需破坏性迁移；其他语言为 `ai-tutor:draft:v2:<题号>:<语言>`。内存键也包含题号和语言。保存失败时，脏内存内容优先于旧磁盘内容；有意清空的草稿也保留。schema 2 导出四语言草稿，导入兼容 schema 1 Python 草稿并保护同题同语言冲突。浏览器存储不可读时，提供明确标注的当前会话“部分备份”。

**已通过**：四语言轮流编辑、切换题目、返回、刷新、旧 Python 草稿、空 C 草稿、存储失败、导入冲突、导出最新内存内容。实际关闭浏览器进程并用同一专用 profile 重开后，四语言草稿均恢复。没有接触用户常用浏览器 profile，没有清空用户旧草稿。

## 5. DeepSeek 多语言与三级 Hint

只增加 language / language_label / language_review 和 Prompt 语言说明。保留已存在的 `/responses`、模型配置、reasoning、max_output_tokens、text.format JSON Schema、UTF-8 编码和严格恰好三级非空 Hint 校验。密钥仍在服务端由 dotenv 加载。

Java 检查类/泛型/类型，C 检查指针/内存/越界，C++ 检查容器/引用/迭代器，Python 保留缩进与容器检查。非 Python 不会进入 Python AST 规则。未知语言在加载凭据、联网前拒绝。

**已通过（Mock）**：四语言完整传参、一次模型请求、默认只返回 Hint 1、逐级展示 2/3、重试不跳级、旧记录 hints_used 更新。401/402/429、超时、空响应、非法 JSON、缺字段、不完整响应和 Hint 数量错误继续拒绝保存成功记录；不修复缺失 Hint、不自动回退 Mock。

题目、语言、代码、修订号、请求 ID 均用于过时结果隔离。编辑、切题、切换语言、改回相同代码、快速重复请求和迟到的 Monaco 回调都有保护，浏览器确认候选结果后才保存历史。

**未测试**：真实 DeepSeek 四语言回答的教学质量、真实账号/余额/网络。此次真实 API 请求次数为 0。手动点击诊断仍会请求模型，可能产生费用。

## 6. 提交、历史与通过状态

新诊断记录、提交事件和用户通过确认带 language。旧记录缺语言显示“未记录”，不猜为 Python。相同旧活动 ID 重试不改写历史语言；已知不同语言不能复用活动 ID。

总体完成状态继续按不同题号统计；新增 completed_by_language 只统计明确带语言的通过事件。旧的无语言通过仍计入总体完成，但不分配给任何语言。Python 通过不会显示成 Java 通过。历史以语言标签展示，异常旧记录仍保留。

**已通过**：多语言提交、历史、幂等、每语言状态、旧数据兼容、诊断不计提交、提交不计通过，以及服务真实读写临时 JSON 的前后端联调。

## 7. 六维画像与题单

| 主要维度 | 原阶段 | 题号 | 分母 |
| --- | --- | --- | ---: |
| 数组与哈希表 | 1 | 1、217、242、49 | 4 |
| 双指针与滑动窗口 | 2 | 125、3、11、42 | 4 |
| 栈、队列与二分查找 | 3 | 20、704、739、150 | 4 |
| 链表、二叉树与递归 | 4、5 | 206、21、141、19、104、226、102、98 | 8 |
| DFS、BFS 与回溯 | 6 | 200、78、46、994 | 4 |
| 贪心与动态规划 | 7、8 | 53、55、45、56、70、198、322、1143 | 8 |

完成度 = 用户确认通过的不同题号 / 此维度题库不同题号 × 100，保留一位小数。以原阶段作唯一主要分类，不按多标签重复归类。同题四语言完成只计一道；诊断、Hint 和本地提交不参与评分；无效/未来/重复事件沿用活动服务校验。无法归类的题号单独列出，不编造维度。

少于三道不同题目通过时显示样本不足，暂不判断强弱；各维度也提供样本状态。三道仅为 V1 展示阈值，不是置信度。0% 不解释为真实能力为零。最强/待加强仅比较完成度，建议指向真实题库中尚未完成的题目。

桌面左侧绿墙、下方推荐题单，右侧翡翠色 0–100 六边形雷达图；约 55:45，窄屏上下排列。悬停提供分子/分母，列表兼顾键盘阅读。绿墙保留 365 天与横向滚动。按用户补充要求在左下放入题单，默认推荐阶段，可切换八阶段并点击进入练习，保留当前语言；下方完整路线继续保留。

## 8. 前后端接口与测试结果

`/api/bootstrap` 增加 templates、completed_by_language、capability；新增只读题目详情 `/api/problems/{id}` 与 `/api/capabilities`。快照/提交/通过确认增加 language，缺省 Python，原 Python 请求格式继续有效。现有搜索、学习路线、历史、两阶段诊断和 Hint 接口保留。TypeScript 类型与 FastAPI 参数约束一致。

| 验证项 | 状态 | 结果与范围 |
| --- | --- | --- |
| 原 Python 回归 + 新增测试 | 已通过 | 136 项；原 106 + 多语言后端 16 + 模板 9 + 能力画像 5 |
| 前端单元/React 测试 | 已通过 | 37 项，8 个测试文件 |
| TypeScript | 已通过 | typecheck 与最终 build 的 tsc |
| 生产构建 | 已通过 | Vite 构建成功，Monaco 既有大包提示保留 |
| Python 语法检查 | 已通过 | 32 个项目 Python 文件 ast.parse，不生成 pyc |
| tracked/new 文本 diff --check | 已通过 | Windows CRLF 正常处理；不改 Git 配置、不暂存 |
| ESLint | 未测试 | 项目未配置 ESLint |
| 新增浏览器主流程 | 已通过 | 70 项，生产构建 + 真实 FastAPI/services + Mock 模型 HTTP |
| 关闭重开浏览器 | 已通过 | 4 项，专用持久 profile，四份草稿恢复 |
| 原浏览器主流程 | 已通过 | 13 项 |
| 原浏览器边界与响应式 | 已通过 | 17 项，包含模拟超时、慢响应、布局/字号/全屏/手机页签 |
| 原迁移与备份 | 已通过 | 3 项 |
| 浏览器合计 | 已通过 | 107 项 |
| 真实 DeepSeek | 未测试 | 0 次真实请求 |
| 任意学生代码执行/官方判题 | 未测试 | 本阶段不实现此功能 |

主流程浏览器 page/console error 为 0，异常网络失败为 0。过时请求主动中止属于预期行为；边界场景专门模拟 HTTP 502 超时，用于验证错误展示与不写成功记录，不视为正常 API 成功。

测试结果明细：`outputs/phase3-browser-results.json`、`phase3-reopen-results.json`、`phase3-core-results.json`、`phase3-boundaries-results.json`、`phase3-migration-results.json`。浏览器脚本检查专用测试响应头，拒绝写入普通服务；测试服务使用临时目录、假密钥、禁用 dotenv 和 Mock urlopen。

## 9. 页面截图

下列均为模拟网络响应与临时学习事件，数据计算由真实服务完成。

- [桌面：绿墙、推荐题单与六维画像](phase3-capability-detail.png)
- [桌面仪表盘](phase3-capability-desktop.png)
- [空数据与样本提醒](phase3-capability-empty.png)
- [390px 窄屏完整布局](phase3-capability-mobile.png)；交互同时在 390×844 验证，长图使用 390×2100 展示上下排列。
- [Java 工作台与独立草稿](phase3-java-workbench.png)

## 10. 正式数据 SHA-256

修改前先保存基线，全部测试后再次比对。原题库未修改，新增模板在独立文件。

| 文件 | 修改前 | 修改后 | 结果 |
| --- | --- | --- | --- |
| `data/records.json` | `f52953ef1bdeb28624bd1b2c3903f9e6b6f7a49b5e51df182f3c7549543482de` | `f52953ef1bdeb28624bd1b2c3903f9e6b6f7a49b5e51df182f3c7549543482de` | 一致 |
| `data/activities.json` | `f6daba3203c5637718e3fb233067d9dac521406c706cd76c8c76086441a74e3f` | `f6daba3203c5637718e3fb233067d9dac521406c706cd76c8c76086441a74e3f` | 一致 |
| `data/problem_catalog.json` | `cb40a383db2de61487aae67901a1412111cc611d72f8f7560730c977a6f80958` | `cb40a383db2de61487aae67901a1412111cc611d72f8f7560730c977a6f80958` | 一致 |

`.env` 忽略状态已确认；没有读取/展示真实密钥内容，没有修改 `.env`。没有清空、迁移或重写正式学习记录。

## 11. 修改与新增文件

共 56 个文件（包含本报告、测试和截图），未包含忽略的构建产物、依赖和临时工作文件：

- `README.md`
- `backend/app.py`
- `data/problem_templates.json`
- `docs/phase3.md`
- `docs/template-interfaces.md`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/src/App.test.tsx`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/capability.css`
- `frontend/src/components/AssistantPanel.tsx`
- `frontend/src/components/CapabilityProfile.test.tsx`
- `frontend/src/components/CapabilityProfile.tsx`
- `frontend/src/components/CodePanel.test.tsx`
- `frontend/src/components/CodePanel.tsx`
- `frontend/src/components/HistoryPage.test.tsx`
- `frontend/src/components/HistoryPage.tsx`
- `frontend/src/components/ProblemChecklist.test.tsx`
- `frontend/src/components/ProblemChecklist.tsx`
- `frontend/src/components/ProblemPanel.tsx`
- `frontend/src/components/ProgressPage.tsx`
- `frontend/src/components/SettingsDialog.tsx`
- `frontend/src/components/checklist.css`
- `frontend/src/languages.ts`
- `frontend/src/monaco.ts`
- `frontend/src/storage.test.ts`
- `frontend/src/storage.ts`
- `frontend/src/styles.css`
- `frontend/src/types.ts`
- `outputs/phase3-boundaries-results.json`
- `outputs/phase3-browser-results.json`
- `outputs/phase3-capability-desktop.png`
- `outputs/phase3-capability-detail.png`
- `outputs/phase3-capability-empty.png`
- `outputs/phase3-capability-mobile.png`
- `outputs/phase3-core-results.json`
- `outputs/phase3-java-workbench.png`
- `outputs/phase3-migration-results.json`
- `outputs/phase3-reopen-results.json`
- `outputs/phase3-verification.md`
- `prompts/diagnose_prompt.txt`
- `services/activity_service.py`
- `services/capability_service.py`
- `services/history_service.py`
- `services/language_service.py`
- `services/llm_service.py`
- `services/practice_service.py`
- `services/problem_service.py`
- `tests/browser/multilingual.js`
- `tests/browser/reopen_multilingual.js`
- `tests/browser_server.py`
- `tests/test_activity_service.py`
- `tests/test_capability_service.py`
- `tests/test_language_templates.py`
- `tests/test_multilanguage_backend.py`

## 12. 开发验收时的 Git 状态快照

第三阶段开发验收结束时尚未执行 git add、commit、push、reset、clean 或强制推送，HEAD 为 `3cec88d`，本地领先远程一个提交。以下为当时未暂存工作区的快照；用户后续授权的提交与同步以仓库历史为准。

```text
## main...origin/main [ahead 1]
 M README.md
 M backend/app.py
 M frontend/package-lock.json
 M frontend/package.json
 M frontend/src/App.test.tsx
 M frontend/src/App.tsx
 M frontend/src/api.ts
 M frontend/src/components/AssistantPanel.tsx
 M frontend/src/components/CodePanel.tsx
 M frontend/src/components/HistoryPage.tsx
 M frontend/src/components/ProblemPanel.tsx
 M frontend/src/components/ProgressPage.tsx
 M frontend/src/components/SettingsDialog.tsx
 M frontend/src/monaco.ts
 M frontend/src/storage.test.ts
 M frontend/src/storage.ts
 M frontend/src/styles.css
 M frontend/src/types.ts
 M prompts/diagnose_prompt.txt
 M services/activity_service.py
 M services/history_service.py
 M services/llm_service.py
 M services/practice_service.py
 M services/problem_service.py
 M tests/browser_server.py
 M tests/test_activity_service.py
?? data/problem_templates.json
?? docs/phase3.md
?? docs/template-interfaces.md
?? frontend/src/capability.css
?? frontend/src/components/CapabilityProfile.test.tsx
?? frontend/src/components/CapabilityProfile.tsx
?? frontend/src/components/CodePanel.test.tsx
?? frontend/src/components/HistoryPage.test.tsx
?? frontend/src/components/ProblemChecklist.test.tsx
?? frontend/src/components/ProblemChecklist.tsx
?? frontend/src/components/checklist.css
?? frontend/src/languages.ts
?? outputs/phase3-boundaries-results.json
?? outputs/phase3-browser-results.json
?? outputs/phase3-capability-desktop.png
?? outputs/phase3-capability-detail.png
?? outputs/phase3-capability-empty.png
?? outputs/phase3-capability-mobile.png
?? outputs/phase3-core-results.json
?? outputs/phase3-java-workbench.png
?? outputs/phase3-migration-results.json
?? outputs/phase3-reopen-results.json
?? services/capability_service.py
?? services/language_service.py
?? tests/browser/multilingual.js
?? tests/browser/reopen_multilingual.js
?? tests/test_capability_service.py
?? tests/test_language_templates.py
?? tests/test_multilanguage_backend.py
?? outputs/phase3-verification.md
```

## 13. 运行与人工验收

前端已构建。如原后端正在运行，请在其终端 Ctrl+C 后重启：

```powershell
Set-Location 'D:\Projects\Python\ai-programming-tutor'
& 'D:\anaconda\envs\ai-study\python.exe' -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000/>。新的题单在“学习路线”页面绿墙下方。

人工重点检查：自己常用浏览器的旧 Python 草稿、四语言切换/刷新/重开、题单跳转后当前语言和草稿、历史旧记录语言标记、通过状态与绿墙/画像语义。若需要真实模型验收，可主动发起简短四语言诊断，检查 Hint 是否贴合语言且不给完整答案；这会产生真实 API 请求并可能收费，本次没有代为执行。模板正式提交前对照当前 LeetCode 接口，C/C++ 实际编译仍待补充。

## 14. 已知限制

- 没有安全执行沙箱、编译、真实运行时间、自动判题或官方 Accepted 同步。
- 补全为本地基础能力，没有 Python/Java/C/C++ 语言服务器。
- 草稿依赖当前浏览器存储，不跨设备同步；存储失败后关闭标签页会丢失未备份的内存内容，页面提供明确提示和部分备份出口。
- JSON 持久化仍为单进程方案；服务器短期工作区在内存，最多 512 个，重启可能需重新诊断。
- Monaco chunk 约 654 KB gzip；主应用含图表约 196 KB gzip，首次加载有成本。
- 画像仅反映这 32 道题的自报完成度，不能推断面试能力、准确率或真实算法水平。

开发与自动化验证已结束，停止并等待人工验收。
