import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile } from 'node:fs/promises';

const require = createRequire(import.meta.url);
const { createImageConnectionActions, createStoredKeyModelDiscoveryActions, panelSections } = require('../src/client-bundle.cjs');

test('说明面板覆盖用途、输入、输出、限制、依赖与状态', () => {
  const card = {
    help: { purpose: '绘制技术路线', inputs: ['赛题'], outputs: ['流程图'], limits: ['不编造'], dependencies: ['Draw.io'] },
  };
  const sections = panelSections(card, { preflight: { status: 'ready' }, providers: { summary: '百炼已配置' } });
  assert.deepEqual(sections.map(([title]) => title), ['用途', '输入', '输出', '限制', '依赖', '环境状态', '供应商状态']);
  assert.match(JSON.stringify(sections), /本机依赖已就绪/);
  assert.match(JSON.stringify(sections), /百炼已配置/);
});

test('bundle 声明折叠 ARIA、键盘原生按钮与窄屏布局', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /'aria-expanded': open/);
  assert.match(source, /'aria-controls': panelId/);
  assert.match(source, /role: 'complementary'/);
  assert.match(source, /@media\(max-width:760px\)/);
  assert.match(source, /dsh-mm-info-launcher/);
  assert.match(source, /dsh-mm-info-launcher\{position:fixed;z-index:89;top:12px;right:72px/);
  assert.match(source, /dsh-mm-info\{position:fixed;z-index:90;top:56px/);
  assert.match(source, /button\[class\*="_sessionLogButton"\]/);
  assert.match(source, /'aria-label': '技能说明'/);
  assert.match(source, /button\.setAttribute\('aria-label', '下载会话日志'\)/);
  assert.match(source, /}, '技能说明'\)/);
  assert.match(source, /'aria-label': '搜索 Skill'/);
  assert.match(source, /点击查看简单说明/);
  assert.match(source, /mathmodelCards\.help\(\)/);
  assert.match(source, /dsh-mm-skill-list/);
  assert.match(source, /if \(!isActive\) return info/);
  assert.match(source, /event\.key === 'Escape'/);
  assert.match(source, /buttonRef\.current\?\.focus\(\)/);
  assert.match(source, /catalogTtlMs = 2_000/);
  for (const ref of ['DASHSCOPE_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY', 'CUSTOM_IMAGE_API_KEY']) {
    assert.match(source, new RegExp(ref));
  }
});

test('技能说明与下载按钮使用同一图标行且抽屉保持独立区间', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  const desktopLauncherTop = Number(source.match(/dsh-mm-info-launcher\{[^}]*top:(\d+)px/)?.[1]);
  const desktopLauncherRight = Number(source.match(/dsh-mm-info-launcher\{[^}]*right:(\d+)px/)?.[1]);
  const desktopPanelTop = Number(source.match(/dsh-mm-info\{[^}]*top:(\d+)px/)?.[1]);
  const mobilePanelTop = Number(source.match(/@media\(max-width:760px\).*?\.dsh-mm-info\{top:(\d+)px/)?.[1]);
  const launcherHeight = 36;
  assert.equal(desktopLauncherTop, 12, '技能说明按钮必须与原生标题栏按钮同一水平行');
  assert.equal(desktopLauncherRight, 72, '技能说明按钮必须位于下载按钮左侧并预留间距');
  assert.ok(desktopPanelTop - (desktopLauncherTop + launcherHeight) >= 8, '桌面入口与抽屉至少保留 8px');
  assert.ok(mobilePanelTop - (desktopLauncherTop + launcherHeight) >= 8, '窄屏入口与抽屉至少保留 8px');
});

test('左上角品牌仅由插件覆盖，使用 MetaMath 真实图标且保留官方新会话入口', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /metaMathBrandMark/);
  assert.match(source, /__METAMATH_BRAND_MARK__/);
  assert.match(source, /\.hHd-Xa_logoRow > button\.hHd-Xa_brand\.hHd-Xa_wide/);
  assert.match(source, /brand\.dataset\.dshMetamathBrand = 'true'/);
  assert.match(source, /word\.textContent = 'MetaMath'/);
  assert.match(source, /chip\.textContent = 'HARNESS'/);
});

test('中央主视觉鲸鱼图标由插件运行时替换为 MetaMath 标记，且不修改官方包', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /metaMathHeroMark/);
  assert.match(source, /__METAMATH_HERO_MARK__/);
  assert.match(source, /span\[class\*="_fishHitbox"\]/);
  assert.match(source, /hitbox\.dataset\.dshMetamathHero = 'true'/);
  assert.match(source, /officialFish\.style\.display = 'none'/);
  assert.match(source, /\.dsh-mm-hero-mark\{width:34px;height:34px/);
});

test('中央主标题替换为“大道至简”金属艺术字图并隐藏预览版徽章', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /metaMathHeroTitle/);
  assert.match(source, /__METAMATH_HERO_TITLE__/);
  assert.match(source, /titleImg\.alt = '大道至简'/);
  assert.match(source, /span\[class\*="_headlineText"\]/);
  assert.match(source, /span\[class\*="_previewBadge"\]/);
  assert.match(source, /badge\.style\.display = 'none'/);
  assert.match(source, /row\.style\.gridTemplateColumns = '34px auto'/);
  assert.match(source, /\.dsh-mm-hero-title-img\{height:34px/);
});

test('生图模型设置使用连接级 Remote，浏览器不持有凭据引用或 Key', async () => {
  const calls = [];
  const actions = createImageConnectionActions({
    list: async () => ({ connections: [] }),
    upsert: async (draft, id) => { calls.push(['upsert', draft, id]); return { id: 'img_connection_01' }; },
    setKey: async (id, value) => { calls.push(['setKey', id, value]); },
    clearKey: async (id) => { calls.push(['clearKey', id]); },
    discoverModels: async (id) => { calls.push(['discoverModels', id]); return { models: [] }; },
    verify: async (id, authorized) => { calls.push(['verify', id, authorized]); },
    setActive: async (id) => { calls.push(['setActive', id]); },
    deleteConnection: async (id, clear) => { calls.push(['deleteConnection', id, clear]); },
  });
  const loaded = await actions.load();
  assert.deepEqual(loaded, { connections: [] });
  await actions.save({ name: '自定义', template: 'openai-compatible', adapter: 'openai-images', model: 'image-pro' });
  await actions.setKey('img_connection_01', 'fixture-key');
  await actions.verify('img_connection_01');
  await actions.remove('img_connection_01', false);
  assert.deepEqual(calls, [
    ['upsert', { name: '自定义', template: 'openai-compatible', adapter: 'openai-images', model: 'image-pro' }, undefined],
    ['setKey', 'img_connection_01', 'fixture-key'],
    ['verify', 'img_connection_01', true],
    ['deleteConnection', 'img_connection_01', false],
  ]);
});

test('生图模型区域挂载在模型页末尾且不覆盖官方模型组件', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /data-dsh-mathmodel-image-settings/);
  assert.match(source, /独立于对话模型，所有模式均可通过 \/ai-draw-skills 或 image_generate 使用/);
  assert.match(source, /section\.appendChild\(mount\)/);
  assert.match(source, /ImageConnectionSettings/);
  assert.doesNotMatch(source, /IMAGE_PROVIDER_META/);
  assert.doesNotMatch(source, /ImageProviderSettings/);
  assert.match(source, /'aria-expanded': pickerOpen/);
  assert.match(source, /'aria-controls': pickerId/);
  assert.match(source, /role: 'radiogroup'/);
  assert.match(source, /event\.key === 'Escape'/);
  assert.match(source, /@media\(max-width:700px\).*?position:fixed/s);
  assert.doesNotMatch(source, /settings\.section'.*id: 'models'/s);
});

test('OpenCode RT 直接嵌入官方添加提供方下拉框，不另起模型设置区', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /option\.value = 'opencode-rt'/);
  assert.match(source, /select\[aria-label="提供方"\]/);
  assert.match(source, /data-dsh-mathmodel-opencode-rt-add/);
  assert.match(source, /value: 'OpenCode RT', readOnly: true/);
  assert.match(source, /child\.dataset\.dshMathmodelOpencodeRtAdd !== 'true'\) child\.style\.display = open/);
  assert.match(source, /mathmodelOpenCodeRt\/configure/);
  assert.doesNotMatch(source, /mathmodel-opencode-rt-settings/);
  assert.doesNotMatch(source, /opencode\.ai\/zen\/go\/v1\/images\/generations/);
});

test('已配置自定义供应商的模型发现走受管 Key Remote，浏览器不读取 Key', async () => {
  const calls = [];
  const actions = createStoredKeyModelDiscoveryActions({ discover: async (provider) => { calls.push(provider); return { models: [] }; } });
  await actions.discover('fixture-provider');
  assert.deepEqual(calls, ['fixture-provider']);
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /mathmodelStoredKeyModelDiscovery\/discover/);
  assert.match(source, /mathmodelOpenCodeRt\/refresh/);
  assert.match(source, /provider === 'opencode-rt'/);
  assert.match(source, /将复用“\$\{picker\.provider\}”已保存的受管 API Key/);
  assert.match(source, /event\.stopImmediatePropagation\(\)/);
  assert.match(source, /加入当前草稿/);
  assert.match(source, /dsh-mm-settings-overlay\{z-index:1000/);
  assert.match(source, /dsh-mm-overlay dsh-mm-settings-overlay/);
  assert.doesNotMatch(source, /mathmodelStoredKeyModelDiscovery[^]{0,800}apiKey/);
});
