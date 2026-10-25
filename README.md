# AI Programming Tutor V2.0

基于 Python + Streamlit 的算法练习与渐进式编程辅导工具。通过选题、编写代码、问题分析和逐级 Hint，引导学习者自主解决问题。

## 运行

在 PowerShell 中执行：

```powershell
Set-Location 'D:\Projects\Python\ai-programming-tutor'
& 'D:\anaconda\envs\ai-study\python.exe' -m pip install -r requirements.txt
& 'D:\anaconda\envs\ai-study\python.exe' -m streamlit run app.py
```

打开终端显示的本地网址。侧栏包含学习仪表盘、选题与练习、学习记录。依赖为 `streamlit==1.50.0` 和 `python-dotenv==1.2.2`，测试使用标准库 `unittest` 和 Streamlit 自带的 `AppTest`。

## 当前功能

- **学习仪表盘**：真实本地提交总数、用户自报通过的不同题目数、连续提交天数、下一推荐阶段。
- **八阶段路线**：数组与哈希表、双指针与滑动窗口、栈/队列/二分、链表、二叉树与递归、DFS/BFS/回溯、贪心、动态规划。
- **32 道精选题**：按精确题号、中文/英文题名搜索；难度筛选和算法标签组合筛选（所选标签全部匹配）；练习摘要、示例、约束、官方链接和 Python 模板。
- **独立草稿**：每题通过 Session State 保存，切题、切页后恢复；查看 Hint、诊断和重运行不会覆盖代码。草稿只在当前浏览器会话内保留，关闭或刷新会话前请自行备份。
- **渐进辅导**：DeepSeek 结合当前题目与代码生成分析、错误类型、知识点和三级 Hint。切题、修改代码或开始新诊断会清除旧结果及 Hint 进度；过时请求的响应不保存。
- **刷题绿墙**：过去 365 天，按北京时间统计主动记录的本地提交。颜色对应每日 0、1、2、3、4 次及以上；悬停查看日期和次数。
- **兼容历史**：保留旧记录、不完整记录及非字典异常条目；展示题号、题名、时间、Hint 使用、诊断来源、请求模型和用户自报通过状态。活动与诊断分别展示。
- **深色界面**：主题集中在 `.streamlit/config.toml`，布局及热力图样式集中在 `utils/ui.py`。

## 三类操作的区别

| 操作 | 保存位置 | 增加提交/绿墙 | 增加完成数 |
| --- | --- | --- | --- |
| AI 诊断 / 重新诊断 | `data/records.json` | 否 | 否 |
| 记录一次本地提交 | `data/activities.json`，`kind=submission` | 是，每次主动点击计一次 | 否 |
| 记录 LeetCode 已通过 | `data/activities.json`，`kind=accepted` | 否 | 按不同题号去重 |

通过按钮需要勾选用户确认。这是**用户自报状态**，没有登录 LeetCode、查询判题结果或同步官方提交。学生代码不会在本地执行，不提供执行沙箱。

同题多次主动提交均计数；相同活动 ID 的重试只保存一次。普通重运行不会创建活动。没有明确日期/题号的旧诊断不会被猜测成提交或 Accepted。

连续天数以提交日计算：今天有提交时从今天向前计数；今天未提交但昨天有提交时，保留截至昨天的连续天数。仅标记通过不增加提交日。推荐第一个尚未全部标记通过的阶段，全部完成后保持第 8 阶段。

## AI 诊断的实际范围

练习页通过 `analyze_code(code, problem)` 调用 **DeepSeek API**，发送当前题目的摘要、示例、约束等上下文和代码，接收错误类型、知识点、分析及恰好三条递进 Hint。Prompt 保存在 `prompts/diagnose_prompt.txt`，要求只给启发和定位方向，不给完整答案；模型的教学质量仍需人工检查。响应按 JSON 严格校验非空必填字段及三条非空 Hint，失败不会当作成功诊断保存。

服务端使用 `python-dotenv` 按 UTF-8 加载项目根目录 `.env`，`override=False`，已有进程环境变量优先。该文件只需配置 `DEEPSEEK_API_KEY`，可选 `DEEPSEEK_MODEL`；不在页面、日志或 Git 中展示密钥。每次点击会向 DeepSeek 发送代码，可能产生 API 费用，请勿在练习代码中放入秘密信息。

根据本次核对的[官方文档](https://api-docs.deepseek.com/)，默认请求模型为 `deepseek-flash`，对该模型显式关闭思考模式（`thinking.type=disabled`）。可通过 `DEEPSEEK_MODEL` 配置账号可用的模型；旧模型 ID 不附加新模型的 `thinking` 开关，这不代表旧 ID 仍获官方支持。结构化响应遵循 [JSON Output](https://api-docs.deepseek.com/guides/json_mode/)，认证、余额、限流等状态参照[官方错误码](https://api-docs.deepseek.com/quick_start/error_codes/)。

HTTP 连接及读取操作设置 30 秒超时，不自动重试。401、402、429、超时、空响应、非法 JSON 和缺字段都会清楚报错并保留草稿；**不会自动回退为规则 / Mock**。本地规则仍作为显式兼容接口保留，其结果标为“本地规则 / Mock”，不冒充 DeepSeek。每次请求使用题号、代码和唯一请求标识隔离结果，编辑、切题或发起更新的请求后丢弃旧响应。

诊断属于模型静态分析，学生代码不会被执行，也不能证明代码正确或 LeetCode Accepted。Hint 初始只展示第一级，逐次展开到第三级；重新诊断从第一级开始。

## 题库来源与扩展

题库为随仓库提供的 `data/problem_catalog.json`，32 道经典题覆盖八阶段。题号、题名、难度和链接采用公开题目元数据；中文练习摘要与示例由本项目编写，**不是官方题面全文**。约束用于配套练习，完整题意、当前约束与判题以每题 LeetCode 官方链接为准。

本版本以本地题库为稳定默认来源，不调用未公开、可能变化或受限的 LeetCode GraphQL 接口，不批量抓取官方全文。因此离线或接口不可用时仍可搜索、筛选和练习；查看官方完整题面需要网络。本版本提供精选本地题库搜索，没有提供全量在线题库搜索。

扩展时按已有 JSON 对象增加唯一整数 `id`，以及 `title_zh`、`title_en`、`slug`、`difficulty`、`tags`、`stage`、`summary`、`examples`、`constraints`、`python_template`、`official_url`、`source_note`。阶段为 1–8；添加可合法使用的摘要/示例并核对官方元数据。回归测试检查题号唯一、阶段覆盖及模板语法。

## 数据保护与存储边界

正式诊断文件仍为 `data/records.json`，已有历史不做启动迁移、不删除条目。新诊断附带 `record_id`、`leetcode_id`、`title`、`created_at`、`hints_used`、`source`、`model` 和 `is_mock`；展开 Hint 只更新该条新记录。缺失的旧日期和来源等元数据展示为“未记录”，不推测旧记录来自模型。刷题活动独立保存到 `data/activities.json`，缺文件时读取为空活动，首次主动保存才创建。

两个本地数据文件均被 Git 忽略。保存采用完整读改写锁、同目录临时文件及原子替换；损坏 JSON 或错误根节点会报错，避免当作空历史覆盖。并发保障针对**单个 Python 进程中的多会话**；多进程部署需共享数据库或额外进程间锁。原子替换不等同于断电持久化，长期使用请备份数据目录。

测试或演示可用环境变量隔离数据：

```powershell
$env:AI_TUTOR_RECORDS_PATH = 'D:\Temp\ai-tutor-demo\records.json'
$env:AI_TUTOR_ACTIVITIES_PATH = 'D:\Temp\ai-tutor-demo\activities.json'
& 'D:\anaconda\envs\ai-study\python.exe' -m streamlit run app.py
```

路径可不存在，实际保存时创建父目录。结束后使用 `Remove-Item Env:AI_TUTOR_RECORDS_PATH, Env:AI_TUTOR_ACTIVITIES_PATH -ErrorAction SilentlyContinue` 恢复默认路径。

## 验证

```powershell
& 'D:\anaconda\envs\ai-study\python.exe' -B -m unittest discover -s tests -v
git diff --check
git diff --cached --check
git status --short
```

自动化测试使用临时目录、虚构输入和模拟 HTTP 响应，不联网、不加载真实密钥、不写正式学习记录或提交数据。覆盖 DeepSeek 请求与失败响应、三级 Hint、草稿及过时请求隔离、题库、活动幂等/并发、提交与通过分离、365 天热力图、时区与连续天数、来源展示、旧记录兼容及页面流程。
