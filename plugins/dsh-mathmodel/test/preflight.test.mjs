import test from 'node:test';
import assert from 'node:assert/strict';
import { PreflightService } from '../lib/index.js';

test('可用夹具稳定覆盖全部必需依赖', async () => {
  const service = new PreflightService({
    locate: async (names) => `fixture-${names[0]}`,
    run: async () => ({ ok: true, code: 0, stdout: 'fixture 1.0', stderr: '', error: null }),
    env: {},
  });
  const report = await service.run();
  assert.equal(report.schema, 'dsh.mathmodel.preflight/v1');
  assert.equal(report.readonly, true);
  const expected = ['python', 'numpy', 'matplotlib', 'pandas', 'scipy', 'xelatex', 'latexmk', 'drawio', 'pdftoppm', 'pdfinfo'];
  assert.deepEqual(report.items.map((item) => item.id), expected);
  const missing = report.items.filter((item) => item.status !== 'available');
  assert.deepEqual(missing, [], JSON.stringify(missing, null, 2));
  assert.ok(report.items.every((item) => item.source === 'system'));
});

test('缺失夹具只返回指导且不尝试运行不存在的命令', async () => {
  let runCalls = 0;
  const service = new PreflightService({
    locate: async () => null,
    run: async () => {
      runCalls += 1;
      throw new Error('不应运行');
    },
    env: {},
  });
  const report = await service.run();
  assert.equal(report.status, 'attention');
  assert.equal(report.readonly, true);
  assert.equal(runCalls, 0);
  assert.ok(report.items.every((item) => item.status === 'missing' && item.guidance));
});

test('严格便携模式禁止回退 PATH 或系统候选', async () => {
  let locateCalls = 0;
  const service = new PreflightService({
    locate: async () => { locateCalls += 1; return 'C:\\system\\tool.exe'; },
    run: async () => ({ ok: true, code: 0, stdout: 'fixture', stderr: '', error: null }),
    env: { DSH_RUNTIME_ROOT: 'Z:\\missing-runtime', DSH_PORTABLE_STRICT: '1' },
  });
  const report = await service.run();
  assert.equal(report.portableStrict, true);
  assert.equal(report.status, 'attention');
  assert.equal(locateCalls, 0);
  assert.ok(report.items.every((item) => item.status === 'missing' && item.source == null));
});
