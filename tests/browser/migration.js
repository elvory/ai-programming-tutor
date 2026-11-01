async (page) => {
  const fixture = await page.request.get('http://127.0.0.1:8000/api/health');
  if (fixture.headers()['x-ai-tutor-test-fixture'] !== 'temporary-data;mock-deepseek') throw new Error('Use tests/browser_server.py: refusing to test against production data');
  const checks = [];
  const ensure = (condition, name) => { if (!condition) throw new Error(name); checks.push(name); };
  const previous = await page.evaluate(() => localStorage.getItem('ai-tutor:draft:v1:198'));
  await page.getByRole('button', { name: '打开工作台设置', exact: true }).click();
  await page.getByLabel('导入草稿文件', { exact: true }).setInputFiles('tests/browser/legacy-drafts.json');
  await page.getByRole('status').filter({ hasText: '已导入' }).waitFor();
  ensure(await page.evaluate(() => localStorage.getItem('ai-tutor:draft:v1:198')) === previous, 'legacy import never overwrites a conflicting current draft');
  ensure(await page.evaluate(() => localStorage.getItem('ai-tutor:draft:v1:70') === '# migrated legacy draft\npass\n'), 'legacy import persists a missing problem draft');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出全部草稿', exact: true }).click();
  const download = await downloadPromise;
  await download.saveAs('work/playwright/qa-drafts-export.json');
  ensure(download.suggestedFilename().startsWith('ai-tutor-drafts-'), 'browser draft export produces a downloadable JSON backup');
  await page.getByRole('button', { name: '关闭设置', exact: true }).click();
  return { checks, check_count: checks.length };
}
