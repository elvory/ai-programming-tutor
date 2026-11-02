async (page) => {
  const base = 'http://127.0.0.1:8011';
  const health = await page.request.get(`${base}/api/health`);
  if (health.headers()['x-ai-tutor-test-fixture'] !== 'temporary-data;mock-deepseek') throw new Error('Refusing to write outside tests/browser_server.py');
  const checks = [];
  const ensure = (ok, name) => { if (!ok) throw new Error(name); checks.push(name); };
  const errors = [], failed = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('requestfailed', request => { if (request.failure()?.errorText !== 'net::ERR_ABORTED') failed.push(request.url()); });
  await page.setViewportSize({ width: 1600, height: 1100 });
  await page.goto(base);
  await page.locator('.monaco-editor').waitFor();
  const boot = async () => (await page.request.get(`${base}/api/bootstrap`)).json();
  const history = async () => (await page.request.get(`${base}/api/history`)).json();
  const chooseProblem = async id => {
    await page.getByRole('button', { name: '题库', exact: true }).click();
    await page.getByRole('textbox', { name: '搜索题目' }).fill(String(id));
    await page.getByText('1 道匹配题目', { exact: true }).waitFor();
    await page.locator('.problem-row').first().click();
    await page.locator('.monaco-editor').waitFor();
  };
  const language = () => page.getByRole('combobox', { name: '编程语言', exact: true });
  const chooseLanguage = async value => { await language().selectOption(value); await page.waitForTimeout(80); };
  const key = (id, lang) => lang === 'python' ? `ai-tutor:draft:v1:${id}` : `ai-tutor:draft:v2:${id}:${lang}`;
  const codeFor = {
    python: '# QA Python 中文草稿\nclass Solution:\n    def twoSum(self, nums, target):\n        return []\n',
    java: '// QA Java 中文草稿\nclass Solution {\n    public int[] twoSum(int[] nums, int target) { return new int[0]; }\n}\n',
    c: '// QA C 中文草稿\n#include <stdlib.h>\nint* twoSum(int* nums, int n, int target, int* returnSize) {\n    *returnSize = 0;\n    return NULL;\n}\n',
    cpp: '// QA C++ 中文草稿\n#include <vector>\nclass Solution {\npublic:\n    std::vector<int> twoSum(std::vector<int>& nums, int target) { return {}; }\n};\n',
  };
  const setCode = async (id, lang, text) => {
    await page.locator('.monaco-editor').click({ position: { x: 120, y: 65 } });
    await page.keyboard.press('Control+A');
    if (text) await page.evaluate(code => {
      const transfer = new DataTransfer(); transfer.setData('text/plain', code);
      document.activeElement.dispatchEvent(new ClipboardEvent('paste', { clipboardData: transfer, bubbles: true, cancelable: true }));
    }, text); else await page.keyboard.press('Backspace');
    await page.waitForFunction(([storageKey, expected]) => localStorage.getItem(storageKey)?.replace(/\r\n/g, '\n') === expected, [key(id, lang), text]);
  };
  await page.getByRole('button', { name: '学习路线', exact: true }).click();
  await page.getByRole('heading', { name: '算法能力画像', exact: true }).waitFor();
  ensure(await page.locator('.heatmap-grid .heatmap-day').count() === 365, '365-day real service heatmap remains');
  ensure(await page.locator('.capability-dimensions li').count() === 6, 'six complete dimension labels rendered');
  ensure(await page.getByText('样本不足 · 暂不判断强弱').isVisible(), 'empty profile warns insufficient evidence');
  ensure(await page.locator('.recharts-polar-grid-concentric-polygon').count() >= 4, 'radar has actual hexagonal 0–100 grid');
  await page.screenshot({ path: 'outputs/phase3-capability-empty.png', fullPage: true });
  await page.getByRole('button', { name: '工作台', exact: true }).click();
  await chooseProblem(1);
  ensure(await language().inputValue() === 'python', 'Python remains default language');
  for (const lang of ['python', 'java', 'c', 'cpp']) {
    await chooseLanguage(lang);
    await setCode(1, lang, codeFor[lang]);
    ensure(await page.locator('.monaco-editor').innerText().then(text => text.replace(/\u00a0/g, ' ').includes(`QA ${lang === 'cpp' ? 'C++' : lang === 'c' ? 'C' : lang === 'java' ? 'Java' : 'Python'}`)), `${lang} edited in real Monaco`);
    const uri = await page.locator('.monaco-editor').getAttribute('data-uri');
    const highlighted = await page.locator('.view-lines').evaluate((element, keyword) =>
      [...element.querySelectorAll('span')].some(span => span.textContent === keyword && getComputedStyle(span).color === 'rgb(198, 147, 216)'), lang === 'c' ? 'int' : 'class');
    ensure(uri.includes(`problem-1-${lang}.`) && highlighted, `${lang} has independent Monaco model and real keyword highlighting`);
  }
  await chooseProblem(20);
  await setCode(20, 'cpp', '// independent problem 20 C++\n');
  await chooseProblem(1);
  for (const lang of ['python', 'java', 'c', 'cpp']) {
    await chooseLanguage(lang);
    ensure((await page.evaluate(k => localStorage.getItem(k), key(1, lang))).replace(/\r\n/g, '\n') === codeFor[lang], `${lang} draft survives problem/language switches`);
    ensure((await page.locator('.monaco-editor').innerText()).includes('中文草稿'), `${lang} buffer restores unicode content`);
  }
  await page.reload(); await page.locator('.monaco-editor').waitFor();
  ensure(await language().inputValue() === 'cpp', 'language preference survives reload');
  for (const lang of ['python', 'java', 'c', 'cpp']) {
    await chooseLanguage(lang);
    ensure((await page.locator('.monaco-editor').innerText()).includes('中文草稿'), `${lang} draft visible after reload`);
  }
  await chooseLanguage('c'); await setCode(1, 'c', '');
  await chooseLanguage('java'); await chooseLanguage('c');
  ensure((await page.locator('.monaco-editor .view-lines').innerText()).trim() === '', 'intentionally empty C draft survives language switch');
  await page.reload(); await page.locator('.monaco-editor').waitFor();
  ensure((await page.locator('.monaco-editor .view-lines').innerText()).trim() === '', 'intentionally empty C draft survives reload');
  await setCode(1, 'c', codeFor.c);
  for (const lang of ['python', 'java', 'c', 'cpp']) {
    await chooseLanguage(lang);
    const before = await history();
    const requestPromise = page.waitForRequest(request => request.url().endsWith('/api/diagnoses') && request.method() === 'POST');
    await page.getByRole('button', { name: 'AI 诊断', exact: true }).click();
    const request = await requestPromise;
    ensure(request.postDataJSON().language === lang, `${lang} diagnosis sends actual language parameter`);
    await page.locator('.hint-card').first().waitFor();
    ensure(await page.locator('.hint-card').count() === 1, `${lang} initially exposes only Hint 1`);
    ensure((await page.locator('.hint-card').first().innerText()).includes(lang), `${lang} mocked response carries matching language`);
    await page.getByRole('button', { name: /查看下一条提示/ }).click();
    await page.waitForFunction(() => document.querySelectorAll('.hint-card').length === 2);
    await page.getByRole('button', { name: /查看下一条提示/ }).click();
    await page.waitForFunction(() => document.querySelectorAll('.hint-card').length === 3);
    ensure(await page.getByRole('button', { name: /已展开全部三级提示/ }).isDisabled(), `${lang} exactly three progressive hints`);
    const after = await history();
    ensure(after.records.length === before.records.length + 1 && after.activities.length === before.activities.length, `${lang} diagnosis records once without submitting`);
  }
  const beforeSubmit = await boot();
  await page.getByRole('button', { name: '记录提交', exact: true }).click();
  await page.getByRole('status').filter({ hasText: '已记录一次本地提交' }).waitFor();
  const submitted = await boot();
  ensure(submitted.summary.total_submissions === beforeSubmit.summary.total_submissions + 1, 'explicit local submission updates service heatmap');
  ensure(submitted.capability.completed_unique === 0, 'local submission does not imply passed problem');
  const accept = async (id, lang) => {
    await chooseProblem(id); await chooseLanguage(lang);
    const requestPromise = page.waitForRequest(request => request.url().endsWith('/api/accepted') && request.method() === 'POST');
    // CLI pauses at native dialogs. Stub only the confirmation choice in this
    // dedicated fixture browser and still verify its language-specific text.
    await page.evaluate(() => { window.confirm = message => { window.__phase3LastConfirmation = message; return true; }; });
    await page.getByRole('button', { name: '标记 LeetCode 已通过', exact: true }).click();
    const request = await requestPromise;
    const confirmation = await page.evaluate(() => window.__phase3LastConfirmation);
    ensure(request.postDataJSON().language === lang && confirmation.includes({ python: 'Python 3', java: 'Java', c: 'C', cpp: 'C++' }[lang]), `self-report UI records ${id}/${lang} with language-specific confirmation`);
    await page.waitForFunction(() => document.querySelector('.accept-control')?.disabled);
  };
  await accept(1, 'python'); await accept(1, 'java'); await accept(217, 'c'); await accept(125, 'cpp');
  const completed = await boot();
  ensure(completed.capability.completed_unique === 3, 'four accepted events across languages count three unique problems');
  ensure(completed.capability.dimensions[0].percentage === 50, 'array/hash completion uses real 2/4 denominator');
  await page.getByRole('button', { name: '学习记录', exact: true }).click();
  await page.locator('.history-table-wrap').first().waitFor();
  ensure((await page.locator('main').innerText()).includes('C++'), 'history displays submission language');
  await page.getByRole('button', { name: '学习路线', exact: true }).click();
  await page.getByRole('heading', { name: '算法能力画像', exact: true }).waitFor();
  ensure((await page.locator('.capability-dimensions').innerText()).includes('50%'), 'radar refreshes from actual accepted events');
  await page.screenshot({ path: 'outputs/phase3-capability-desktop.png', fullPage: true });
  await page.locator('.learning-overview').screenshot({ path: 'outputs/phase3-capability-detail.png' });
  await page.locator('.recharts-radar-dot').first().hover();
  await page.locator('.capability-tooltip').waitFor();
  ensure((await page.locator('.capability-tooltip').innerText()).includes('2 / 4'), 'radar hover exposes actual completed/total data');
  const heatmapBox = await page.locator('.activity-section').boundingBox();
  const profileBox = await page.locator('.capability-section').boundingBox();
  ensure(profileBox.x > heatmapBox.x && Math.abs(profileBox.y - heatmapBox.y) < 3, 'desktop heatmap left and radar right');
  ensure(await page.getByRole('heading', { name: '推荐题单', exact: true }).isVisible(), 'recommended problem checklist fills lower-left space');
  const checklistBox = await page.locator('.problem-checklist').boundingBox();
  ensure(checklistBox.y > heatmapBox.y && Math.abs(checklistBox.x - heatmapBox.x) < 3, 'problem checklist sits directly below the heatmap');
  await page.getByRole('combobox', { name: '题单阶段' }).selectOption('2');
  ensure(await page.locator('.checklist-row').count() === 4, 'checklist shows actual four stage-two catalog problems');
  await page.locator('.checklist-row').filter({ hasText: '无重复字符的最长子串' }).click();
  await page.getByRole('heading', { name: '3. 无重复字符的最长子串', exact: true }).waitFor();
  ensure(await language().inputValue() === 'cpp', 'checklist opens actual exercise with current language preserved');
  await page.getByRole('button', { name: '学习路线', exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  const mobileProfile = await page.locator('.capability-section').boundingBox();
  const mobileHeatmap = await page.locator('.activity-section').boundingBox();
  ensure(mobileProfile.y > mobileHeatmap.y, 'mobile overview stacks vertically');
  ensure(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'mobile dashboard has no horizontal page overflow');
  await page.screenshot({ path: 'outputs/phase3-capability-mobile.png', fullPage: true });
  await page.setViewportSize({ width: 1600, height: 1100 });
  await page.getByRole('button', { name: '工作台', exact: true }).click();
  await chooseProblem(1);
  await page.locator('.monaco-editor').waitFor();
  await chooseLanguage('java');
  await page.screenshot({ path: 'outputs/phase3-java-workbench.png', fullPage: true });
  // A language change with identical text must still invalidate a pending result.
  await setCode(1, 'java', '// QA_SLOW identical language-switch source\n');
  const beforeStale = (await history()).records.length;
  await page.getByRole('button', { name: 'AI 诊断', exact: true }).click();
  await page.locator('.analysis-loading').waitFor();
  await chooseLanguage('c');
  await page.waitForTimeout(1900);
  ensure((await history()).records.length === beforeStale, 'language switch during pending request prevents saved stale diagnosis');
  ensure(await page.locator('.hint-card').count() === 0, 'stale other-language hints never reappear');
  // Keep the four expected drafts for persistent-profile reopen verification.
  await chooseLanguage('java'); await setCode(1, 'java', codeFor.java);
  await chooseLanguage('python');
  ensure(errors.length === 0, `zero page/console errors: ${errors.join(';')}`);
  ensure(failed.length === 0, `zero unexpected network failures: ${failed.join(';')}`);
  return { scenario: 'production build + real FastAPI/services + temporary data + mocked DeepSeek HTTP', checks,
    check_count: checks.length, page_errors: errors, failed_requests: failed, real_deepseek_requests: 0 };
}
