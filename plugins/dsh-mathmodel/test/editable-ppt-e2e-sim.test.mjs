/**
 * 模拟端到端测试（计划 §10.4）：本地 fake OpenAI Images 服务 + 假凭据，
 * 走真实 ImageConnectionService / ImageGenerationService / editable_ppt_image 契约
 * 与安装后的 editppt CLI，完成单页与双页（并发页面、页内串行、同锁定连接）全链路，
 * 覆盖 generate、带 source 的 edit、带 mask 的 edit 与各结果的 metadata import，
 * 并对全部输出与文本工件做零秘密扫描。不产生任何真实付费调用。
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { execFile } from 'node:child_process';
import { mkdir, mkdtemp, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { basename, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { promisify } from 'node:util';
import {
  EMPTY_IMAGE_CONNECTIONS, ImageConnectionCredentialStore, ImageConnectionService, ImageGenerationService,
} from '../lib/index.js';

const execFileAsync = promisify(execFile);
const PLUGIN_ROOT = resolve(import.meta.dirname, '..');
const WORKSPACE = resolve(PLUGIN_ROOT, '../..');
const SKILL_ROOT = join(WORKSPACE, '.dsh/skills/image-to-editable-ppt');

const FAKE_KEY = 'sk-fixture123';
const stamp = '2026-09-02T03:00:00.000Z';
const TINY_PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==', 'base64');
const TINY_PNG_B64 = TINY_PNG.toString('base64');

function editpptExe() {
  return process.env.EDITPPT_EXE || (process.platform === 'win32' ? 'D:\\CodexHome\\uv\\bin\\editppt.exe' : 'editppt');
}
function pythonExe() {
  return process.env.DSH_PYTHON || 'python';
}

function memoryProvider() {
  const values = new Map();
  return {
    async describe(ref) { return { configured: values.has(ref), writable: true, source: 'managed' }; },
    async resolve(ref) { return { value: values.get(ref) ?? '', source: 'managed' }; },
    async set(ref, value) { values.set(ref, value); },
    async unset(ref) { values.delete(ref); },
  };
}

/** fake OpenAI Images 服务：记录请求形态，返回固定 PNG。 */
async function startFakeProvider() {
  const requests = [];
  const server = createServer((req, res) => {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const body = Buffer.concat(chunks);
      requests.push({
        url: req.url,
        contentType: req.headers['content-type'] ?? '',
        auth: (req.headers.authorization ?? '').startsWith('Bearer ') ? 'bearer' : 'none',
        body,
      });
      res.setHeader('content-type', 'application/json');
      res.end(JSON.stringify({ data: [{ b64_json: TINY_PNG_B64 }] }));
    });
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  const port = server.address().port;
  return { server, port, requests, baseUrl: `http://127.0.0.1:${port}/v1` };
}

async function makeServices(fake) {
  let value = EMPTY_IMAGE_CONNECTIONS;
  const provider = memoryProvider();
  const settings = { get: () => value, async replace(next) { value = next; } };
  const connections = new ImageConnectionService({
    settings,
    legacySettings: { get: () => ({}) },
    credentialStore: new ImageConnectionCredentialStore(provider),
    credentialProvider: provider,
    hasV2UserSection: () => true,
    now: () => stamp,
    fetchImpl: async () => ({ ok: true, json: async () => ({ data: [] }) }),
  });
  const list = await connections.upsert({ name: 'e2e-image', template: 'openai-compatible', adapter: 'openai-images', model: 'gpt-image-2', baseUrl: fake.baseUrl });
  const created = list.connections.at(-1);
  await connections.setKey(created.id, FAKE_KEY);
  const current = value;
  await connections.settings.replace({
    ...current,
    connections: current.connections.map((item) => (item.id === created.id ? {
      ...item,
      verification: {
        status: 'ready', protocol: 'openai-images', model: 'gpt-image-2', template: 'openai-compatible',
        baseUrlFingerprint: 'a'.repeat(64), keyFingerprint: 'b'.repeat(64), verifiedAt: stamp, message: '',
      },
    } : item)),
    activeConnectionId: created.id,
  });
  const service = new ImageGenerationService({ connections });
  return { service, created };
}

async function run(cmd, args, opts = {}) {
  try {
    const { stdout, stderr } = await execFileAsync(cmd, args, { maxBuffer: 32 * 1024 * 1024, ...opts });
    return { code: 0, stdout, stderr };
  } catch (error) {
    return { code: error.code ?? 1, stdout: error.stdout ?? '', stderr: `${error.message}\n${error.stderr ?? ''}` };
  }
}

async function makeSourcePng(path, width, height) {
  const script = `from PIL import Image\nim=Image.new('RGB',(${width},${height}),(245,246,250))\nim.save(r'${path}')\n`;
  const result = await run(pythonExe(), ['-c', script]);
  assert.equal(result.code, 0, `生成测试源图失败：${result.stderr}`);
}

async function writePageArtifacts(pageDir, title) {
  const request = JSON.parse(await readFile(join(pageDir, 'page_request.json'), 'utf8'));
  await mkdir(join(pageDir, 'prompts'), { recursive: true });
  await writeFile(join(pageDir, 'prompts', 'clean-base.md'), '保留背景构成并移除文字与图标');
  await mkdir(join(pageDir, 'assets'), { recursive: true });
  const manifest = {
    schema_version: 1,
    page_id: request.page_id,
    slide: request.slide,
    content_box: request.content_box,
    source: { path: 'source.png', width_px: request.source_size_px.width, height_px: request.source_size_px.height },
    text_inventory: [{ id: 'title', text: title, decision: 'native-text' }],
    required_text: [title],
    visual_inventory: [{ id: 'kpi-icon', description: 'KPI icon separated via source-faithful asset-sheet split', asset: 'assets/icon_a.png' }],
    background_strategy: {
      mode: 'imagegen-full-clean-base',
      source_consistency_contract: 'composition, colors, lighting and background identity preserved from source.png via editable_ppt_image edit',
      removed_foreground: 'title text and KPI icon rebuilt natively or separately',
      comparison_note: 'preview background matches source composition after reconstruction',
    },
    quality_checks: {
      font_size_calibrated: true,
      visual_inventory_matched: true,
      background_strategy_checked: true,
      shape_corner_geometry_checked: true,
    },
    text_boxes: [{ id: 'title', text: title, box_px: [140, 120, 640, 96], font_size: 40, bold: true, color: '#111111' }],
    shapes: [],
    images: [{ id: 'kpi-icon', path: 'assets/icon_a.png', box_px: [220, 320, 96, 96], z_index: 210 }],
    asset_provenance: [{
      path: 'assets/icon_a.png',
      source: 'source.png',
      source_type: 'asset-sheet-separated',
      provenance_note: 'KPI icon separated through source-faithful asset-sheet split via editable_ppt_image edit; registered by editppt image import with DSH metadata',
    }],
  };
  await writeFile(join(pageDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
}

/** 单页重建（模拟 worker）：generate、带 source 的 edit、带 mask 的 edit；页内串行；每个结果 metadata import。 */
async function reconstructPage(ctx, pageDir, title, hooks) {
  const { service, editppt, workspaceRoot, connectionId } = ctx;
  await writePageArtifacts(pageDir, title);
  const slash = (p) => p.split('\\').join('/');
  const relPage = slash(pageDir).slice(slash(workspaceRoot).length + 1);
  const jobs = [
    {
      label: 'support-generate', role: 'asset',
      request: { action: 'generate', connectionId, authorizePaid: true, prompt: '生成与页面风格一致的装饰底纹', size: 'auto' },
    },
    {
      label: 'clean-base', role: 'clean_base',
      request: { action: 'edit', connectionId, authorizePaid: true, prompt: '保留源页背景构成与配色，移除全部文字与前景图标', size: 'auto', quality: 'high' },
    },
    {
      label: 'asset-sheet', role: 'asset_sheet',
      request: { action: 'edit', connectionId, authorizePaid: true, prompt: '把前景 KPI 图标分离到纯色抠图资产表，形状与配色忠实于源' },
    },
    {
      label: 'mask-repair', role: 'asset',
      request: { action: 'edit', connectionId, authorizePaid: true, prompt: '按 mask 修复背景局部瑕疵' },
    },
  ];
  for (const job of jobs) {
    const dest = `assets/${job.label}.png`;
    const request = { ...job.request, outputPath: `${relPage}/${dest}` };
    if (job.label === 'clean-base' || job.label === 'asset-sheet') request.referenceImages = [`${relPage}/source.png`];
    if (job.label === 'mask-repair') {
      request.referenceImages = [`${relPage}/assets/clean-base.png`];
      request.maskImage = `${relPage}/assets/clean-base.png`;
    }
    hooks.start();
    const result = await service.editablePptImage(request, { workspace: workspaceRoot });
    hooks.end();
    assert.equal(result.ok, true, `${job.label} 失败：${JSON.stringify(result.error)}`);
    assert.match(result.sha256, /^[0-9a-f]{64}$/);
    const importResult = await run(editppt, [
      'image', 'import', pageDir,
      '--job-id', `${job.label}-1`,
      '--source-image', join(workspaceRoot, result.file),
      '--dest', dest,
      '--role', job.role,
      '--prompt-file', 'prompts/clean-base.md',
      '--metadata-file', join(workspaceRoot, result.metadataFile),
      '--note', 'DSH current connection; run-pinned',
    ]);
    assert.equal(importResult.code, 0, `import ${job.label} 失败：${importResult.stderr}`);
  }
  // 资产表拆分产物就位（模拟 process-sheet 之后的选中的图标资产）。
  await writeFile(join(pageDir, 'assets', 'icon_a.png'), TINY_PNG);
  const build = await run(editppt, ['page', 'build', pageDir]);
  assert.equal(build.code, 0, `page build 失败：${build.stdout}${build.stderr}`);
  const contact = await run(editppt, ['page', 'contact-sheet', pageDir]);
  assert.equal(contact.code, 0, `contact-sheet 失败：${contact.stderr}`);
  const validate = await run(editppt, ['page', 'validate', pageDir]);
  assert.equal(validate.code, 0, `page validate 失败：${validate.stdout}`);
  await writeFile(join(pageDir, 'validation.json'), JSON.stringify({ passed: true, runtime_validation: JSON.parse(validate.stdout), mode: 'dsh-current-simulated-e2e' }, null, 2));
  await writeFile(join(pageDir, 'page_result.json'), JSON.stringify({
    page_manifest: 'manifest.json', imagegen_jobs: 'imagegen-jobs.json', page_pptx: 'page.pptx',
    preview: 'preview.png', contact_sheet: 'split_assets_contact.png', validation: 'validation.json', page_result: 'page_result.json',
  }, null, 2));
}

async function walk(dir) {
  const out = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...await walk(path));
    else out.push(path);
  }
  return out;
}

test('模拟 E2E：dsh-current 全链路（单页 + 双页并发、页内串行、同锁定连接、零秘密）', { timeout: 420000 }, async (t) => {
  const fake = await startFakeProvider();
  try {
    const probe = await run(editpptExe(), ['--help']);
    if (probe.code !== 0) { t.skip(`editppt 不可用：${probe.stderr}`); return; }
    const pythonProbe = await run(pythonExe(), ['-c', 'import PIL']);
    if (pythonProbe.code !== 0) { t.skip('python/PIL 不可用'); return; }

    const { service, created } = await makeServices(fake);
    const workspaceRoot = await mkdtemp(join(tmpdir(), 'dsh-e2e-'));
    const inputs = join(workspaceRoot, 'inputs');
    await mkdir(inputs, { recursive: true });

    const status = await service.editablePptImage({ action: 'status' }, { workspace: workspaceRoot });
    assert.equal(status.ok, true);
    assert.equal(status.connectionId, created.id);
    const connectionId = status.connectionId;
    const editppt = editpptExe();
    const ctx = { service, editppt, workspaceRoot, connectionId };

    // —— 单页链路 ——
    await makeSourcePng(join(inputs, 'page.png'), 1600, 900);
    const oneRun = join(workspaceRoot, 'run-one');
    const prep1 = await run(editppt, [
      'prepare', join(inputs, 'page.png'),
      '--image-backend', 'dsh-current',
      '--connection-id', connectionId, '--connection-name', 'e2e-image',
      '--image-model', 'gpt-image-2', '--image-protocol', 'openai-images',
      '--job-dir', oneRun, '--no-text-hints',
    ]);
    assert.equal(prep1.code, 0, `prepare 单页失败：${prep1.stderr}`);
    const deck1 = JSON.parse(await readFile(join(oneRun, 'deck_manifest.json'), 'utf8'));
    assert.equal(deck1.image_backend.backend_id, 'dsh-current');
    assert.equal(deck1.image_backend.connection_id, connectionId);
    assert.equal(deck1.image_backend.allow_codex, false);
    const page1 = join(oneRun, 'pages', 'page_001');
    const req1 = JSON.parse(await readFile(join(page1, 'page_request.json'), 'utf8'));
    assert.equal(req1.image_backend.connection_id, connectionId);

    const promptOut = join(page1, 'worker-prompt.md');
    const built = await run(pythonExe(), [join(SKILL_ROOT, 'scripts/build-page-worker-prompt.py'), oneRun, '--page', 'page_001', '--out', promptOut]);
    assert.equal(built.code, 0, `worker prompt 构建失败：${built.stderr}`);
    const promptText = await readFile(promptOut, 'utf8');
    assert.match(promptText, /editable_ppt_image/);
    assert.doesNotMatch(promptText, /codex login|OPENAI_API_KEY|editppt config/);
    const dispatch1 = await run(editppt, ['run', 'dispatch', oneRun, '--page', 'page_001', '--agent-id', 'main', '--prompt-file', promptOut, '--local']);
    assert.equal(dispatch1.code, 0, `local dispatch 失败：${dispatch1.stderr}`);

    let active = 0;
    let maxActive = 0;
    const singleHooks = {
      start() { active += 1; maxActive = Math.max(maxActive, active); assert.ok(active <= 1, '页内图像调用必须串行'); },
      end() { active -= 1; },
    };
    await reconstructPage(ctx, page1, 'Quarterly Revenue', singleHooks);
    assert.equal(maxActive, 1);
    const record1 = await run(editppt, ['run', 'record', oneRun, '--page', 'page_001', '--agent-id', 'main']);
    assert.equal(record1.code, 0, `record 失败：${record1.stdout}${record1.stderr}`);
    const final1 = await run(editppt, ['run', 'finalize', oneRun]);
    assert.equal(final1.code, 0, `finalize 失败：${final1.stdout}${final1.stderr}`);
    const finalValidation1 = JSON.parse(await readFile(join(oneRun, 'final', 'validation.json'), 'utf8'));
    assert.equal(finalValidation1.passed, true, '最终验证报告必须 passed:true');
    const jobs1 = JSON.parse(await readFile(join(page1, 'imagegen-jobs.json'), 'utf8'));
    assert.equal(jobs1.jobs.length, 4);
    for (const job of jobs1.jobs) {
      assert.equal(job.connection_id, connectionId);
      assert.equal(job.status, 'recorded');
      assert.ok(job.metadata_file && job.metadata_sha256);
    }

    // —— 双页并发链路 ——
    await makeSourcePng(join(inputs, 'a.png'), 1600, 900);
    await makeSourcePng(join(inputs, 'b.png'), 1600, 900);
    const twoRun = join(workspaceRoot, 'run-two');
    const prep2 = await run(editppt, [
      'prepare', join(inputs, 'a.png'), join(inputs, 'b.png'),
      '--image-backend', 'dsh-current',
      '--connection-id', connectionId, '--connection-name', 'e2e-image',
      '--image-model', 'gpt-image-2', '--image-protocol', 'openai-images',
      '--job-dir', twoRun, '--no-text-hints',
    ]);
    assert.equal(prep2.code, 0, `prepare 双页失败：${prep2.stderr}`);
    const perPage = new Map([['page_001', 0], ['page_002', 0]]);
    let maxConcurrentPages = 0;
    let activePages = 0;
    // page_jobs.json 的 dispatch/record 是读改写命令：串行记录这两步（模拟父 Agent 顺序登记）；
    // 图像重建显式交错：两页的“页内串行、跨页并发”由此确定性地成立。
    const stateLock = (() => {
      let chain = Promise.resolve();
      return (fn) => {
        const next = chain.then(fn, fn);
        chain = next.then(() => undefined, () => undefined);
        return next;
      };
    })();
    const bothDispatched = { remaining: 2, gate: null };
    bothDispatched.gate = new Promise((release) => { bothDispatched.release = release; });
    const worker = async (pageId, title, agentId) => {
      const pageDir = join(twoRun, 'pages', pageId);
      const workerPrompt = join(pageDir, 'worker-prompt.md');
      assert.equal((await run(pythonExe(), [join(SKILL_ROOT, 'scripts/build-page-worker-prompt.py'), twoRun, '--page', pageId, '--out', workerPrompt])).code, 0);
      await stateLock(async () => {
        assert.equal((await run(editppt, ['run', 'dispatch', twoRun, '--page', pageId, '--agent-id', agentId, '--prompt-file', workerPrompt])).code, 0);
      });
      bothDispatched.remaining -= 1;
      if (bothDispatched.remaining === 0) bothDispatched.release();
      else await bothDispatched.gate; // 两页都登记 dispatched 后才开始重建：确定性跨页并发窗口
      const hooks = {
        start() {
          perPage.set(pageId, perPage.get(pageId) + 1);
          assert.ok(perPage.get(pageId) <= 1, `${pageId} 页内必须串行`);
        },
        end() { perPage.set(pageId, perPage.get(pageId) - 1); },
      };
      // 页面并发窗口以“整页重建”为界：两页重建必须交叠；页内图像调用另有严格串行断言。
      activePages += 1;
      maxConcurrentPages = Math.max(maxConcurrentPages, activePages);
      await reconstructPage(ctx, pageDir, title, hooks);
      activePages -= 1;
      await stateLock(async () => {
        const record = await run(editppt, ['run', 'record', twoRun, '--page', pageId, '--agent-id', agentId]);
        assert.equal(record.code, 0, `record ${pageId} 失败：${record.stdout}${record.stderr}`);
      });
    };
    await Promise.all([worker('page_001', 'Page One Title', 'w1'), worker('page_002', 'Page Two Title', 'w2')]);
    assert.ok(maxConcurrentPages >= 2, '两个页面应存在并发执行窗口');
    const final2 = await run(editppt, ['run', 'finalize', twoRun]);
    assert.equal(final2.code, 0, `双页 finalize 失败：${final2.stdout}${final2.stderr}`);
    const finalValidation2 = JSON.parse(await readFile(join(twoRun, 'final', 'validation.json'), 'utf8'));
    assert.equal(finalValidation2.passed, true);
    for (const pageId of ['page_001', 'page_002']) {
      const jobs = JSON.parse(await readFile(join(twoRun, 'pages', pageId, 'imagegen-jobs.json'), 'utf8'));
      assert.equal(jobs.jobs.length, 4);
      for (const job of jobs.jobs) assert.equal(job.connection_id, connectionId);
    }

    // fake 供应商请求形态：generate 与 edits 都发生、mask 独立字段、Bearer 假 Key
    const generates = fake.requests.filter((entry) => entry.url.endsWith('/images/generations'));
    const edits = fake.requests.filter((entry) => entry.url.endsWith('/images/edits'));
    assert.equal(generates.length, 3);
    assert.equal(edits.length, 9);
    const maskRequest = edits.at(-1);
    const formText = maskRequest.body.toString('latin1');
    assert.match(formText, /name="mask"/);
    assert.equal((formText.match(/name="image\[\]"/g) ?? []).length, 1, 'mask 不得混入 image[]');
    assert.ok(fake.requests.every((entry) => entry.auth === 'bearer'));

    // —— 零秘密扫描（全部 stdout/stderr 与文本工件） ——
    const banned = [FAKE_KEY, 'Authorization', 'Bearer', 'credentialRef', 'MATHMODEL_IMAGE', `127.0.0.1:${fake.port}`];
    const logs = [prep1, prep2, record1, final1, final2, built].map((entry) => `${entry.stdout}\n${entry.stderr}`).join('\n');
    const findings = [];
    for (const token of banned) if (logs.includes(token)) findings.push(`log:${token}`);
    for (const path of await walk(workspaceRoot)) {
      if (!/\.(json|md|txt|tex|dsh-image\.json)$/i.test(path)) continue;
      const text = await readFile(path, 'utf8').catch(() => '');
      for (const token of banned) if (text.includes(token)) findings.push(`${path.slice(workspaceRoot.length)}:${token}`);
    }
    assert.deepEqual(findings, [], `发现秘密泄漏：${findings.join(', ')}`);
    assert.ok((await stat(join(oneRun, 'final'))).isDirectory());
    assert.ok((await stat(join(twoRun, 'final'))).isDirectory());
  } finally {
    fake.server.close();
  }
});
