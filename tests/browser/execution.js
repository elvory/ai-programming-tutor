async (page) => {
  const base = 'http://127.0.0.1:8000';
  const health = await page.request.get(`${base}/api/health`);
  if (health.headers()['x-ai-tutor-test-fixture'] !== 'temporary-data;mock-deepseek')
    throw new Error('Refusing to write outside isolated tests/browser_server.py');
  const checks = [], outcomes = [], errors = [];
  const ensure = (condition, name) => { if (!condition) throw new Error(name); checks.push(name); };
  let posts = 0, sessionToken = '';
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (request.url().endsWith('/api/execution/run') && request.method() === 'POST') posts++; });
  page.on('response', async response => {
    if (response.url().endsWith('/api/execution/session') && response.ok())
      sessionToken = (await response.json()).token;
  });
  const boot = async () => (await page.request.get(`${base}/api/bootstrap`)).json();
  const before = await boot();
  const stats = value => JSON.stringify({ summary: value.summary, heatmap: value.heatmap, capability: value.capability });
  await page.setViewportSize({ width: 1600, height: 1100 });
  await page.goto(base);
  await page.locator('.monaco-editor').waitFor();
  const runButton = () => page.getByRole('button', { name: '运行公开示例', exact: true });
  const panel = () => page.getByRole('region', { name: '代码执行结果', exact: true });
  const lang = () => page.getByRole('combobox', { name: '编程语言', exact: true });
  const chooseLanguage = async language => {
    await lang().selectOption(language);
    await page.waitForFunction(value => document.querySelector('.monaco-editor')?.getAttribute('data-uri')?.includes(`problem-1-${value}.`), language);
  };
  const draftKey = (language) => language === 'python' ? 'ai-tutor:draft:v1:1' : `ai-tutor:draft:v2:1:${language}`;
  const edit = async (text, language = 'python') => {
    await page.locator('.monaco-editor').click({ position: { x: 120, y: 65 } });
    await page.keyboard.press('Control+A');
    await page.evaluate(code => {
      const transfer = new DataTransfer(); transfer.setData('text/plain', code);
      document.activeElement.dispatchEvent(new ClipboardEvent('paste', { clipboardData: transfer, bubbles: true, cancelable: true }));
    }, text);
    await page.waitForFunction(([key, source]) => localStorage.getItem(key)?.replace(/\r\n/g, '\n') === source, [draftKey(language), text]);
  };
  const correct = "import sys\nclass Solution:\n    def twoSum(self, nums, target):\n        print('中文 stdout')\n        print('browser stderr', file=sys.stderr)\n        for i in range(len(nums)):\n            for j in range(i + 1, len(nums)):\n                if nums[i] + nums[j] == target:\n                    return [j, i]\n";
  const slow = "import time\nclass Solution:\n    def twoSum(self, nums, target):\n        time.sleep(1.3)\n        print('STALE_SENTINEL')\n        return [1, 2]\n";
  const run = async (code, expectedStatus) => {
    await edit(code);
    const response = page.waitForResponse(response => response.url().endsWith('/api/execution/run') && response.request().method() === 'POST');
    await runButton().click();
    ensure(await runButton().isDisabled(), 'run button disabled while request is pending');
    const reply = await response;
    ensure(reply.status() === 200, 'real execution endpoint returns a structured response');
    const result = await reply.json();
    ensure(result.status === expectedStatus, `real Docker status ${expectedStatus}`);
    await page.waitForFunction(() => !document.querySelector('button[aria-label="运行公开示例"]')?.disabled);
    await panel().waitFor();
    ensure((await panel().innerText()).includes('公开示例'), 'result identifies public examples');
    ensure(result.cleanup_confirmed && result.judge.official_accepted === false, 'cleanup confirmed without official acceptance');
    outcomes.push({ status: result.status, passed: result.judge.passed, total: result.judge.total,
      execution_time_ms: result.execution_time_ms, cleanup_confirmed: result.cleanup_confirmed });
    return result;
  };

  ensure(await lang().inputValue() === 'python', 'fresh fixture defaults to Python');
  const successful = await run(correct, 'SUCCESS');
  ensure(successful.judge.all_passed, 'correct Two Sum passes public example');
  ensure((await panel().innerText()).includes('中文 stdout') && (await panel().innerText()).includes('browser stderr'), 'page shows both real stdout and stderr');
  const displayedTime = (await panel().innerText()).match(/([0-9]+(?:\.[0-9]+)?)\s*ms/);
  ensure(displayedTime && Math.abs(Number(displayedTime[1]) - successful.execution_time_ms) < 0.01, 'page shows measured sandbox time');
  await page.screenshot({ path: 'D:/Projects/Python/ai-programming-tutor/outputs/m3-lite-desktop.png', fullPage: true });
  const wrong = await run('class Solution:\n    def twoSum(self, nums, target):\n        return []\n', 'SUCCESS');
  ensure(!wrong.judge.all_passed && wrong.judge.passed === 0, 'wrong answer is distinct from successful execution');
  await run('class Solution syntax error\n', 'COMPILE_ERROR');
  ensure((await panel().innerText()).includes('invalid syntax'), 'page shows actual syntax diagnostic');
  await run("class Solution:\n    def twoSum(self, nums, target):\n        raise ValueError('browser-runtime-error')\n", 'RUNTIME_ERROR');
  ensure((await panel().innerText()).includes('browser-runtime-error'), 'page shows runtime diagnostic');
  await run('class Solution:\n    def twoSum(self, nums, target):\n        while True:\n            pass\n', 'TIME_LIMIT_EXCEEDED');
  ensure((await panel().innerText()).includes('超时'), 'page identifies real external timeout');

  for (const change of ['edit', 'language', 'problem']) {
    await edit(slow);
    const response = page.waitForResponse(reply => reply.url().endsWith('/api/execution/run') && reply.request().method() === 'POST');
    const count = posts;
    await runButton().click();
    await page.waitForFunction(() => document.querySelector('button[aria-label="运行公开示例"]')?.disabled);
    // Native click on a disabled button is inert; no extra HTTP request.
    await runButton().evaluate(button => { button.click(); button.click(); });
    if (change === 'edit') {
      await edit(correct);
      await edit(slow); // A -> B -> A must still reject the old result.
    } else if (change === 'language') {
      await chooseLanguage('java');
      ensure(await runButton().isDisabled(), 'Java execution remains unavailable');
      await chooseLanguage('python');
    } else {
      await page.getByRole('button', { name: '下一题', exact: true }).click();
      ensure(await runButton().isDisabled(), 'other problems remain unavailable');
      await page.getByRole('button', { name: '上一题', exact: true }).click();
    }
    const oldResult = await (await response).json();
    ensure(oldResult.status === 'SUCCESS' && oldResult.cleanup_confirmed, `${change}: old request finishes and cleans up in Docker`);
    await page.waitForFunction(() => !document.querySelector('button[aria-label="运行公开示例"]')?.disabled);
    ensure(posts === count + 1, `${change}: duplicate clicks issue only one execution`);
    ensure(!(await page.locator('.test-panel').innerText()).includes('STALE_SENTINEL'), `${change}: late Docker output is discarded`);
    ensure((await page.locator('.test-panel').innerText()).includes('重新运行'), `${change}: obsolete result requires a new run`);
  }

  await edit(correct);
  await page.getByRole('button', { name: 'AI 诊断', exact: true }).click();
  await page.locator('.hint-card').first().waitFor();
  for (let level = 2; level <= 3; level++) {
    await page.getByRole('button', { name: /查看下一条提示/ }).click();
    await page.waitForFunction(expected => document.querySelectorAll('.hint-card').length === expected, level);
  }
  const diagnosisHistory = await (await page.request.get(`${base}/api/history`)).json();
  await run(correct, 'SUCCESS');
  ensure(await page.locator('.hint-card').count() === 3, 'execution preserves all three existing AI hints');
  const afterHistory = await (await page.request.get(`${base}/api/history`)).json();
  ensure(afterHistory.records.length === diagnosisHistory.records.length, 'execution does not append AI history');
  ensure(stats(await boot()) === stats(before), 'execution and diagnosis do not alter submissions, green wall or radar');

  for (const language of ['java', 'c', 'cpp']) {
    await chooseLanguage(language);
    await edit(`// ${language} isolated draft\n`, language);
    ensure(await runButton().isDisabled(), `${language} shows unavailable execution without fake result`);
  }
  await chooseLanguage('python');
  await page.reload();
  await page.locator('.monaco-editor').waitFor();
  await page.waitForFunction(() => document.querySelector('.monaco-editor')?.textContent?.replace(/\u00a0/g, ' ').includes('中文 stdout'));
  ensure(await page.evaluate(() => localStorage.getItem('ai-tutor:draft:v1:1')?.includes('中文 stdout')), 'Python draft survives page reload');
  for (const language of ['java', 'c', 'cpp']) {
    await chooseLanguage(language);
    await page.waitForFunction(value => document.querySelector('.monaco-editor')?.textContent?.replace(/\u00a0/g, ' ').includes(`${value} isolated draft`), language);
    ensure((await page.locator('.monaco-editor').innerText()).replace(/\u00a0/g, ' ').includes(`${language} isolated draft`), `${language} draft survives page reload`);
  }
  await chooseLanguage('python');
  await run(correct, 'SUCCESS');
  ensure(await page.evaluate(token => ![localStorage, sessionStorage].some(storage =>
    Object.values(storage).some(value => String(value).includes(token))), sessionToken), 'execution token is not stored in localStorage or sessionStorage');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('navigation', { name: '工作台面板' }).getByRole('button', { name: '代码', exact: true }).click();
  ensure(await runButton().isVisible(), 'run button remains available at mobile width');
  ensure(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'mobile page has no horizontal overflow');
  await page.screenshot({ path: 'D:/Projects/Python/ai-programming-tutor/outputs/m3-lite-mobile.png', fullPage: true });
  ensure(errors.length === 0, 'browser has no uncaught page errors');
  return { fixture: 'temporary-data;mock-deepseek', execution: 'real-docker', checks, outcomes,
    execution_requests: posts, page_errors: errors, screenshots: ['m3-lite-desktop.png', 'm3-lite-mobile.png'] };
}
