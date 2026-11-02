# 第三阶段：多语言与算法能力画像

在原 React + TypeScript + Vite / Monaco / FastAPI / Python services 架构上扩展。旧 Streamlit 页面保留 Python 功能。新工作台支持 Python 3、Java、C、C++ 的编辑与 DeepSeek 静态诊断，不编译、不运行学生代码，也不自动判题。

## 运行

在 VS Code 打开项目，终端执行：

```powershell
Set-Location 'D:\Projects\Python\ai-programming-tutor'
& 'D:\anaconda\envs\ai-study\python.exe' -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000/>。这次已经构建前端；以后改前端代码，需要在 `frontend` 目录执行 `npm.cmd run build`，并重启后端。也可按 `docs/workbench.md` 使用 Vite 开发模式。

## 语言、草稿与记录

语言选择器改变 Monaco 模式、文件扩展名和模板。Python / Java / C / C++ 分别使用 `python` / `java` / `c` / `cpp` 模式；C 与 C++ 共享 Monaco 自带的 C 系列 tokenizer 定义，各自有补全条目。编辑器保留行号、缩进、括号匹配、多行编辑、深色主题、字号、复制和全屏。补全是词汇与基础 snippets，没有语言服务器或完整 IDE 类型分析。

原题库 `data/problem_catalog.json` 保持不变。独立的 `data/problem_templates.json` 为现有题目提供 Java、C、C++ 签名与骨架，Python 模板仍直接来自原题库。详细接口与 C 输出长度/内存约定见 `docs/template-interfaces.md`。模板不是答案；占位返回值或 TODO 异常不表示算法已实现。

Python 保留原 localStorage 键 `ai-tutor:draft:v1:<题号>`，其他语言使用 `ai-tutor:draft:v2:<题号>:<语言>`。按题目和语言分别保存，包括有意清空的草稿。浏览器存储失败时，当前标签页内存保留最新内容，并显示备份提示。关闭页面前应导出草稿；清理浏览器数据或换浏览器不会自动同步。

导出使用 schema 2 保存四语言草稿；导入兼容 schema 1 的旧 Python 草稿，冲突时保留当前草稿。语言偏好也保存在浏览器。

新诊断、提交和通过确认记录带 `language`。旧记录缺少语言时展示“未记录”，不据此归类为 Python。题目总体通过状态继续按题号统计；`summary.completed_by_language` 只统计明确记录了语言的通过事件。

## AI 协议与过时请求

保留现有 DeepSeek Responses API、模型配置、JSON Schema 和严格三级 Hint 校验。仅在上下文中增加 `language`、`language_label`、`language_review`，并扩展 `prompts/diagnose_prompt.txt` 的语言要求。密钥仍只在服务端由 `.env` 加载。

`POST /api/workspace/sync`、`POST /api/diagnoses`、`POST /api/submissions` 的快照支持 `language`，缺省为 `python`，不支持的语言返回 422。`POST /api/accepted` 同样支持语言。原先的请求格式继续有效。

诊断维持候选结果与浏览器确认两阶段流程。切题、切换语言、编辑代码和再次请求都会使旧请求失效；服务端按修订号和题目/语言/代码检查，浏览器也检查当前快照。下一条 Hint 使用预期等级重试保护。模型缺字段、非法 JSON、少 Hint、网络错误均报错，不补 Hint，也不回退 Mock。

## 六个维度与统计规则

| 主要维度 | 原路线阶段 | 现有题数 |
| --- | --- | ---: |
| 数组与哈希表 | 1 | 4 |
| 双指针与滑动窗口 | 2 | 4 |
| 栈、队列与二分查找 | 3 | 4 |
| 链表、二叉树与递归 | 4、5 | 8 |
| DFS、BFS 与回溯 | 6 | 4 |
| 贪心与动态规划 | 7、8 | 8 |

使用原题库阶段作为唯一主要分类依据。标签供教学解释，不因多个标签重复分类。无法识别阶段的题号单独列出并排除六维分母。

完成度 = 此维度中用户已确认通过的不同题号数 / 此维度题库不同题号总数 × 100，保留一位小数。重复事件、同题不同语言通过都不增加题数。沿用活动服务的校验与北京时间日期规则，忽略无效、重复和未来事件。诊断、Hint、本地提交不计为通过。

雷达图使用 Recharts，固定 0–100 六边形网格，支持悬停数据与键盘可读六维列表。桌面端绿墙在左、画像在右，约 55:45；绿墙下方放置推荐题单，默认显示推荐阶段，支持切换八个阶段、查看完成状态并直接进入练习，完整路线仍保留在下方。窄屏上下排列。整体不足三道不同题目通过时显示“样本不足”，暂不判断强弱。每个维度也有样本状态。三道是 V1 的透明展示阈值，不是统计置信度。0% 不表示真实能力为零。建议根据完成度较低且尚未完成的维度，指向真实题库中的下一道题。

`GET /api/bootstrap` 增加 `capability`、多语言模板、语言完成集合；`GET /api/capabilities` 独立返回画像，`GET /api/problems/{id}` 返回含模板的详情。现有搜索、路线、历史、提交和 Hint 接口保留。

## 测试与隔离

```powershell
& 'D:\anaconda\envs\ai-study\python.exe' -B -m unittest discover -s tests -v
Set-Location frontend
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
```

没有配置 ESLint，因此不报告 ESLint 通过。后端和浏览器自动化使用假密钥、模拟 HTTP 传输及临时记录目录，不调用真实 DeepSeek。

浏览器验收只允许使用专用测试服务：

```powershell
& 'D:\anaconda\envs\ai-study\python.exe' -B tests/browser_server.py --port 8011
```

在项目根目录用专用浏览器 profile 运行 `tests/browser/multilingual.js`。该脚本检查测试服务响应头后才写入，拒绝对普通服务写入。脚本中的通过确认和提交仅用于测试服务的临时数据。截图上的画像同样来自这些模拟学习事件。

结果、截图、正式数据前后 SHA-256、文件清单和限制记录在 `outputs/phase3-verification.md`。

## 人工验收

1. 用自己的浏览器检查旧 Python 草稿；为同题四语言各写不同代码，切题、刷新、关闭浏览器再打开。
2. 检查数组、字符串、链表、树、二维数组题的模板是否符合目标 LeetCode 编辑器的接口。
3. 若主动验证真实模型，分别发起简短四语言诊断，检查术语和三级提示的教学质量。这些操作会请求 DeepSeek，可能产生费用；本次自动化未进行此项验证。
4. 检查本地提交的语言标签、通过确认的语言范围，以及绿墙与画像各自的统计语义。

当前仍采用单进程 JSON 持久化；多个服务进程共同写文件需要另行设计。服务端工作区是有上限的内存状态，重启可能需要重新诊断，浏览器草稿与持久记录不受此影响。
