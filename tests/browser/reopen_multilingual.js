async (page) => {
  const base = 'http://127.0.0.1:8011';
  const health = await page.request.get(`${base}/api/health`);
  if (health.headers()['x-ai-tutor-test-fixture'] !== 'temporary-data;mock-deepseek') throw new Error('Use isolated browser fixture');
  const checks = [];
  await page.goto(base);
  await page.locator('.monaco-editor').waitFor();
  for (const language of ['python', 'java', 'c', 'cpp']) {
    await page.getByRole('combobox', { name: '编程语言', exact: true }).selectOption(language);
    await page.waitForTimeout(80);
    if (!(await page.locator('.monaco-editor').innerText()).includes('中文草稿')) throw new Error(`${language} lost after closing and reopening browser`);
    checks.push(`${language} draft survives actual browser process close/reopen`);
  }
  return { checks, check_count: checks.length, storage: 'dedicated persistent browser profile; no user profile access' };
}
