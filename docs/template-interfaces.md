# 多语言模板接口与验证

现有 32 道题通过 `services/problem_service.py` 将独立的 `data/problem_templates.json` 合并到只读题库结果中。原始 `data/problem_catalog.json` 不改动；`templates.python` 始终逐字取自原有 `python_template`。覆盖情况为 Python 32/32、Java 32/32、C 32/32、C++ 32/32，共 128 份初始代码。

模板按题号和 slug 双重匹配，防止外部题库复用题号时套用错误签名。新增的外部题目若未补充模板，仅提供已有 Python 模板，不凭空推断其他语言接口。模板文件可用 `AI_TUTOR_TEMPLATES_PATH` 指向隔离测试副本；服务按路径、修改时间和文件大小缓存，调用方得到独立副本。

语言 ID 为 `python`、`java`、`c`、`cpp`，缺省语言为 Python 3。模板是待实现的函数骨架；Java/C++ 用明确的 TODO 异常保留合法返回类型，C 用明确标注的占位返回值并初始化输出长度。模板并不实现题目算法，也不表示运行或通过。

## 接口约定

方法名、参数含义和题号来自项目现有 Python 签名、摘要、示例及每题的公开 LeetCode 链接；Java/C/C++ 使用这些题目的 LeetCode 函数式提交约定。以下表格列出本次人工核对并写入的精确签名。当前未连接 LeetCode 自动同步系统，在线接口最新版本尚未验证；正式提交前应以题目官方页面为准。

- Java 使用 `class Solution`，必要的集合类型来自 `java.util.*`；字符网格为 `char[][]`，整数网格为 `int[][]`。
- C++ 使用 `class Solution`，数组/嵌套数组为 `vector` 引用，字符串按对应题目的 `string` 参数处理；模板包含 `<vector>`、`<string>`、`<stdexcept>`。
- C 包含 `<stdbool.h>`、`<stddef.h>`、`<stdlib.h>`。输入数组有长度参数，二维输入有行数和每行列数指针；输出数组通过 `returnSize` 返回长度，二维输出额外使用 `returnColumnSizes`。
- C 的二维字符串输出 `groupAnagrams` 返回 `char***`；二维整数输出返回 `int**`。这些返回值和列数数组需要学习者按题目约定分配，调用方负责释放；模板中的空返回值仅是占位。
- 链表题提供 `ListNode` 约定，树题提供 `TreeNode` 约定。Java/C/C++ 的节点完整字段定义放在注释里，说明由 LeetCode 判题环境提供；避免正式提交时重复声明。没有将链表环题的示例 `pos` 错作函数参数。

## 32 道题签名

| 题号 / 官方题目 | Java | C | C++ |
| --- | --- | --- | --- |
| [#1](https://leetcode.cn/problems/two-sum/) | `int[] twoSum(int[] nums, int target)` | `int* twoSum(int* nums, int numsSize, int target, int* returnSize)` | `vector<int> twoSum(vector<int>& nums, int target)` |
| [#217](https://leetcode.cn/problems/contains-duplicate/) | `boolean containsDuplicate(int[] nums)` | `bool containsDuplicate(int* nums, int numsSize)` | `bool containsDuplicate(vector<int>& nums)` |
| [#242](https://leetcode.cn/problems/valid-anagram/) | `boolean isAnagram(String s, String t)` | `bool isAnagram(char* s, char* t)` | `bool isAnagram(string s, string t)` |
| [#49](https://leetcode.cn/problems/group-anagrams/) | `List<List<String>> groupAnagrams(String[] strs)` | `char*** groupAnagrams(char** strs, int strsSize, int* returnSize, int** returnColumnSizes)` | `vector<vector<string>> groupAnagrams(vector<string>& strs)` |
| [#125](https://leetcode.cn/problems/valid-palindrome/) | `boolean isPalindrome(String s)` | `bool isPalindrome(char* s)` | `bool isPalindrome(string s)` |
| [#3](https://leetcode.cn/problems/longest-substring-without-repeating-characters/) | `int lengthOfLongestSubstring(String s)` | `int lengthOfLongestSubstring(char* s)` | `int lengthOfLongestSubstring(string s)` |
| [#11](https://leetcode.cn/problems/container-with-most-water/) | `int maxArea(int[] height)` | `int maxArea(int* height, int heightSize)` | `int maxArea(vector<int>& height)` |
| [#42](https://leetcode.cn/problems/trapping-rain-water/) | `int trap(int[] height)` | `int trap(int* height, int heightSize)` | `int trap(vector<int>& height)` |
| [#20](https://leetcode.cn/problems/valid-parentheses/) | `boolean isValid(String s)` | `bool isValid(char* s)` | `bool isValid(string s)` |
| [#704](https://leetcode.cn/problems/binary-search/) | `int search(int[] nums, int target)` | `int search(int* nums, int numsSize, int target)` | `int search(vector<int>& nums, int target)` |
| [#739](https://leetcode.cn/problems/daily-temperatures/) | `int[] dailyTemperatures(int[] temperatures)` | `int* dailyTemperatures(int* temperatures, int temperaturesSize, int* returnSize)` | `vector<int> dailyTemperatures(vector<int>& temperatures)` |
| [#150](https://leetcode.cn/problems/evaluate-reverse-polish-notation/) | `int evalRPN(String[] tokens)` | `int evalRPN(char** tokens, int tokensSize)` | `int evalRPN(vector<string>& tokens)` |
| [#206](https://leetcode.cn/problems/reverse-linked-list/) | `ListNode reverseList(ListNode head)` | `struct ListNode* reverseList(struct ListNode* head)` | `ListNode* reverseList(ListNode* head)` |
| [#21](https://leetcode.cn/problems/merge-two-sorted-lists/) | `ListNode mergeTwoLists(ListNode list1, ListNode list2)` | `struct ListNode* mergeTwoLists(struct ListNode* list1, struct ListNode* list2)` | `ListNode* mergeTwoLists(ListNode* list1, ListNode* list2)` |
| [#141](https://leetcode.cn/problems/linked-list-cycle/) | `boolean hasCycle(ListNode head)` | `bool hasCycle(struct ListNode* head)` | `bool hasCycle(ListNode* head)` |
| [#19](https://leetcode.cn/problems/remove-nth-node-from-end-of-list/) | `ListNode removeNthFromEnd(ListNode head, int n)` | `struct ListNode* removeNthFromEnd(struct ListNode* head, int n)` | `ListNode* removeNthFromEnd(ListNode* head, int n)` |
| [#104](https://leetcode.cn/problems/maximum-depth-of-binary-tree/) | `int maxDepth(TreeNode root)` | `int maxDepth(struct TreeNode* root)` | `int maxDepth(TreeNode* root)` |
| [#226](https://leetcode.cn/problems/invert-binary-tree/) | `TreeNode invertTree(TreeNode root)` | `struct TreeNode* invertTree(struct TreeNode* root)` | `TreeNode* invertTree(TreeNode* root)` |
| [#102](https://leetcode.cn/problems/binary-tree-level-order-traversal/) | `List<List<Integer>> levelOrder(TreeNode root)` | `int** levelOrder(struct TreeNode* root, int* returnSize, int** returnColumnSizes)` | `vector<vector<int>> levelOrder(TreeNode* root)` |
| [#98](https://leetcode.cn/problems/validate-binary-search-tree/) | `boolean isValidBST(TreeNode root)` | `bool isValidBST(struct TreeNode* root)` | `bool isValidBST(TreeNode* root)` |
| [#200](https://leetcode.cn/problems/number-of-islands/) | `int numIslands(char[][] grid)` | `int numIslands(char** grid, int gridSize, int* gridColSize)` | `int numIslands(vector<vector<char>>& grid)` |
| [#78](https://leetcode.cn/problems/subsets/) | `List<List<Integer>> subsets(int[] nums)` | `int** subsets(int* nums, int numsSize, int* returnSize, int** returnColumnSizes)` | `vector<vector<int>> subsets(vector<int>& nums)` |
| [#46](https://leetcode.cn/problems/permutations/) | `List<List<Integer>> permute(int[] nums)` | `int** permute(int* nums, int numsSize, int* returnSize, int** returnColumnSizes)` | `vector<vector<int>> permute(vector<int>& nums)` |
| [#994](https://leetcode.cn/problems/rotting-oranges/) | `int orangesRotting(int[][] grid)` | `int orangesRotting(int** grid, int gridSize, int* gridColSize)` | `int orangesRotting(vector<vector<int>>& grid)` |
| [#53](https://leetcode.cn/problems/maximum-subarray/) | `int maxSubArray(int[] nums)` | `int maxSubArray(int* nums, int numsSize)` | `int maxSubArray(vector<int>& nums)` |
| [#55](https://leetcode.cn/problems/jump-game/) | `boolean canJump(int[] nums)` | `bool canJump(int* nums, int numsSize)` | `bool canJump(vector<int>& nums)` |
| [#45](https://leetcode.cn/problems/jump-game-ii/) | `int jump(int[] nums)` | `int jump(int* nums, int numsSize)` | `int jump(vector<int>& nums)` |
| [#56](https://leetcode.cn/problems/merge-intervals/) | `int[][] merge(int[][] intervals)` | `int** merge(int** intervals, int intervalsSize, int* intervalsColSize, int* returnSize, int** returnColumnSizes)` | `vector<vector<int>> merge(vector<vector<int>>& intervals)` |
| [#70](https://leetcode.cn/problems/climbing-stairs/) | `int climbStairs(int n)` | `int climbStairs(int n)` | `int climbStairs(int n)` |
| [#198](https://leetcode.cn/problems/house-robber/) | `int rob(int[] nums)` | `int rob(int* nums, int numsSize)` | `int rob(vector<int>& nums)` |
| [#322](https://leetcode.cn/problems/coin-change/) | `int coinChange(int[] coins, int amount)` | `int coinChange(int* coins, int coinsSize, int amount)` | `int coinChange(vector<int>& coins, int amount)` |
| [#1143](https://leetcode.cn/problems/longest-common-subsequence/) | `int longestCommonSubsequence(String text1, String text2)` | `int longestCommonSubsequence(char* text1, char* text2)` | `int longestCommonSubsequence(string text1, string text2)` |

## 本次验证

- **已通过**：9 个多语言模板/语言验证用例，覆盖 32 题四语言完整性、原有 Python 保留、搜索/详情/路线一致性、未知题号/slug 防误配、模板校验只读与路径隔离、复杂返回值/节点/字符网格签名。
- **已通过**：原题库服务 10 个测试；调用者修改模板结果不影响后续读取。
- **已通过**：32 份 Python 模板 `ast.parse`；32 份 Java 模板在临时目录中由本机 `D:\JAVA\bin\javac.exe` 编译。Java 验证只添加包命名隔离和判题器节点桩，没有执行生成的类。
- **部分通过**：C/C++ 已完成接口、头文件、输出长度与节点约定的静态检查；当前 PATH 未找到 gcc/g++/clang/clang++，C/C++ 编译验证**未测试**。
- **未测试**：LeetCode 官方判题、学生代码运行以及在线接口版本同步。应用本阶段不提供用户代码编译、运行或自动判题。

自动化测试只读取正式题库，写入隔离临时目录，不调用 DeepSeek，也不改写正式学习记录。
