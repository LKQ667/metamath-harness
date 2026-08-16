import test from 'node:test';
import assert from 'node:assert/strict';
import { PreflightService } from '../lib/index.js';

test('当前机器只读预检覆盖全部必需依赖', async () => {
  const report = await new PreflightService().run();
  assert.equal(report.schema, 'dsh.mathmodel.preflight/v1');
  assert.equal(report.readonly, true);
  const expected = ['python', 'numpy', 'matplotlib', 'pandas', 'scipy', 'xelatex', 'latexmk', 'drawio', 'pdftoppm', 'pdfinfo'];
  assert.deepEqual(report.items.map((item) => item.id), expected);
  const missing = report.items.filter((item) => item.status !== 'available');
  assert.deepEqual(missing, [], JSON.stringify(missing, null, 2));
});
