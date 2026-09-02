import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { TYPERT } from '../src/typert.host.js';
import { TYPERT_REMOTE } from '../src/typert.remote-client.js';
import { API_KEY_POOL_INVOCATIONS } from '../src/typert-shared.js';
import { validateTypertManifest } from '../../../.dsh/profiles/node_modules/@deepseek-ai/dsh-typert-loader/lib/index.js';

test('Host Typert 清单通过官方 Harness 校验器', () => {
  const validated = validateTypertManifest('@deepseek-harness/dsh-api-key-pool', TYPERT);
  assert.equal(validated.invocations.length, 7);
  assert.deepEqual(
    new Set(validated.invocations.map((item) => item.namespace)),
    new Set(['apiKeyPool']),
  );
  assert.deepEqual(
    validated.invocations.map((item) => item.method),
    ['list', 'upsertPool', 'deletePool', 'addKey', 'removeKey', 'resetCooldown', 'probe'],
  );
});

test('Host 与 Client 共享同一份 invocation 描述符', () => {
  assert.equal(TYPERT.invocations, API_KEY_POOL_INVOCATIONS);
  assert.equal(TYPERT_REMOTE.descriptors, API_KEY_POOL_INVOCATIONS);
  assert.deepEqual(
    TYPERT_REMOTE.descriptors.map((item) => item.id),
    TYPERT.invocations.map((item) => item.id),
  );
});

test('可选参数声明为 optional（poolId/keyId 允许缺省）', () => {
  const addKey = API_KEY_POOL_INVOCATIONS.find((item) => item.method === 'addKey');
  assert.equal(addKey.parameters[1].name, 'poolId');
  const resetCooldown = API_KEY_POOL_INVOCATIONS.find((item) => item.method === 'resetCooldown');
  assert.equal(resetCooldown.parameters[1].name, 'keyId');
});

test('upsertPool 的 wire schema 必须保留卡片写入的每个模型字段', () => {
  const upsertPool = API_KEY_POOL_INVOCATIONS.find((item) => item.method === 'upsertPool');
  const poolSchema = upsertPool.parameters[0].codec.schema;
  // zod 默认剥掉未声明的键：漏字段会表现为「界面填了、配置里没有」，所以逐字段守住
  const parsed = poolSchema.parse({
    id: 'deepseek-official',
    displayName: '官方',
    api: 'openai-completions',
    baseURL: 'https://api.deepseek.com',
    models: [{
      id: 'deepseek-v4-flash-vision-exp',
      name: '识图模型',
      contextWindow: 256000,
      maxTokens: 8000,
      input: ['text', 'image'],
    }],
    enabled: true,
  });
  assert.deepEqual(parsed.models[0], {
    id: 'deepseek-v4-flash-vision-exp',
    name: '识图模型',
    contextWindow: 256000,
    maxTokens: 8000,
    input: ['text', 'image'],
  });
});

test('浏览器 bundle 的 Remote 签名与 Host 清单一致', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  const browserDescriptors = [...source.matchAll(/descriptor\('([^']+)', '([^']+)'(?:, \[([^\]]*)\])?\)/g)].map((match) => ({
    id: `${match[1]}.${match[2]}`,
    parameters: [...(match[3] ?? '').matchAll(/param\('([^']+)'\)/g)].map((parameter) => parameter[1]),
  }));
  const hostDescriptors = TYPERT.invocations.map((item) => ({
    id: `${item.service}.${item.method}`,
    parameters: item.parameters.map((parameter) => parameter.name),
  }));
  assert.deepEqual(browserDescriptors, hostDescriptors);
});

test('浏览器入口先挂载 Remote，再注入设置卡片插槽', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  const mount = source.indexOf('await ctx.remote.$mount(TYPERT_REMOTE)');
  const resolveRemote = source.indexOf("ctx.get('remote.apiKeyPool')");
  const slotInject = source.indexOf("ctx.slots.inject('settings.plugin.item'");
  assert.ok(mount >= 0, '必须调用 $mount 挂载 Remote');
  assert.ok(resolveRemote > mount, '必须在挂载之后才能取 remote');
  assert.ok(slotInject > mount, '设置卡片必须在 Remote 就绪后注入');
  assert.match(source, /await disposeRemote\(\)/);
});

test('浏览器 bundle 源码不含完整 Key 形态的硬编码秘密', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  // 只允许脱敏形态（sk-…）出现在源码；完整 Key 需 20+ 连续可打印字符且无省略号
  const suspicious = [...source.matchAll(/sk-[A-Za-z0-9_-]{12,}/g)].map((m) => m[0]);
  assert.deepEqual(suspicious, [], 'client bundle 不得硬编码任何完整形态 API Key');
});

test('全部 Remote 调用都经过 unwrapRemote 解包 {ok,value} 信封', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  // 定义行本身（unwrapRemote = ...）不算调用点
  const callSites = [...source.matchAll(/remote\.([a-zA-Z]+)\(/g)]
    .map((m) => m[1])
    .filter((name) => name !== 'remote');
  assert.ok(callSites.length >= 7, `应有至少 7 个 Remote 调用点，实际 ${callSites.length}`);
  const wrapped = [...source.matchAll(/unwrapRemote\((?:await )?remote\.[a-zA-Z]+\(/g)].length;
  assert.equal(wrapped, callSites.length, '每个 remote.* 调用点都必须被 unwrapRemote 包裹');
});

test('号池卡片保存结果有明确成功提示，字段校验失败时保持自定义设置展开', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /号池 \$\{result\.poolId\} 已保存；上方统计已刷新。/);
  assert.match(source, /setAdvOpen\(true\)/);
  assert.match(source, /role: 'status'/);
  assert.match(source, /role: 'alert'/);
});

test('Key 填写方式对齐原生模型页：单一只写密钥字段 + 折叠自定义设置', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  // 主字段：type=password 的 API 密钥输入框，占位与校验文案与原生同源
  assert.match(source, /keyInput: 'API 密钥'/);
  assert.match(source, /keyPlaceholder: '输入 API 密钥'/);
  assert.match(source, /keyStored: '已配置——输入新值可添加'/);
  assert.match(source, /keyIllegalCharacters: '该 API 密钥格式错误，请检查。'/);
  assert.match(source, /type: 'password'/);
  assert.match(source, /customized: '自定义设置'/);
  assert.match(source, /autoComplete: 'off'/);
  // 原生不询问环境变量名，号池同样不再出现「挂载池」下拉与「仅入库」路径
  assert.doesNotMatch(source, /挂载池|仅入库|新建池|收起新建池/);
});

test('多枚 Key：一次粘贴可拆分，逐枚字段级校验，界面只留脱敏预览', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /function splitKeys/);
  assert.match(source, /LEGAL_KEY_PATTERN = \/\^\[\\x21-\\x7E\]\+\$\//);
  assert.match(source, /ENV_ASSIGNMENT_PATTERN/);
  // 完整 Key 只经 addKey 上行，界面仅显示脱敏预览，也不写任何浏览器存储
  assert.match(source, /function maskPreview/);
  assert.match(source, /return `\$\{value\.slice\(0, 3\)\}…\$\{value\.slice\(-4\)\}`/);
  assert.doesNotMatch(source, /localStorage\.|sessionStorage\.|document\.cookie/);
});

test('Provider ID 由显示名或端点派生，编辑态保持固定', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /function suggestPoolId/);
  assert.match(source, /POOL_ID_PATTERN = \/\^/);
  assert.match(source, /disabled: !creating/);
});

test('模型目录沿用原生逐行编辑器：一行一个模型，不再要求逗号分隔', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /function ModelListEditor/);
  assert.match(source, /COPY\.addModel/);
  assert.match(source, /COPY\.modelContextWindow/);
  assert.match(source, /COPY\.modelMaxTokens/);
  assert.match(source, /function modelRowsFailure/);
  assert.match(source, /models: submitModels/);
  // 逗号分隔的旧写法必须彻底消失
  assert.doesNotMatch(source, /多个用逗号分隔|deepseek-chat，deepseek-reasoner|draft\.models\.split/);
});

test('容量读写沿用原生 K/M 词表（1M = 1000K），默认值按未填显示', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /function parseCapacity/);
  assert.match(source, /function formatCapacity/);
  assert.match(source, /1M = 1000K/);
  assert.match(source, /CAPACITY_DEFAULT = \{ contextWindow: 262144, maxTokens: 32768 \}/);
  assert.match(source, /CAPACITY_HINT = \{ contextWindow: '256K', maxTokens: '32K' \}/);
});

test('模型行带原生同款「识图（图片输入）」勾选，勾选写入 [text, image]', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /modelVision: '识图（图片输入）'/);
  assert.match(source, /modelVisionHint: '勾选即声明该模型支持图片输入/);
  assert.match(source, /const VISION_INPUT = Object\.freeze\(\['text', 'image'\]\)/);
  assert.match(source, /const hasVision = \(model\) => Array\.isArray\(model\?\.input\) && model\.input\.includes\('image'\)/);
  // 勾选写入完整模态，取消勾选清空整个字段（与原生 patch 语义一致）
  assert.match(source, /input: event\.target\.checked \? \[\.\.\.VISION_INPUT\] : undefined/);
  assert.match(source, /hasVision\(row\) \? \{ input: \[\.\.\.VISION_INPUT\] \}/);
});
