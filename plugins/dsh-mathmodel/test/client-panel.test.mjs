import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
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
  assert.match(source, /dsh-mm-info-launcher\{position:fixed;z-index:89;top:12px;right:calc\(72px \+ var\(--dsh-sidebar-width,0px\)\)/);
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
  const desktopLauncherRight = Number(source.match(/dsh-mm-info-launcher\{[^}]*right:calc\((\d+)px \+ var\(--dsh-sidebar-width,0px\)\)/)?.[1]);
  const desktopPanelTop = Number(source.match(/dsh-mm-info\{[^}]*top:(\d+)px/)?.[1]);
  const mobilePanelTop = Number(source.match(/@media\(max-width:760px\).*?\.dsh-mm-info\{top:(\d+)px/)?.[1]);
  const launcherHeight = 36;
  assert.equal(desktopLauncherTop, 12, '技能说明按钮必须与原生标题栏按钮同一水平行');
  assert.equal(desktopLauncherRight, 72, '技能说明按钮基准右距必须保持 72px（better-sidebar 展开时再叠加其推挤变量）');
  assert.ok(desktopPanelTop - (desktopLauncherTop + launcherHeight) >= 8, '桌面入口与抽屉至少保留 8px');
  assert.ok(mobilePanelTop - (desktopLauncherTop + launcherHeight) >= 8, '窄屏入口与抽屉至少保留 8px');
});

test('品牌与 favicon 使用桌面快捷方式 ICO，覆盖展开和收起侧栏语义插槽', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  const build = await readFile(new URL('../scripts/build.mjs', import.meta.url), 'utf8');
  const built = await readFile(new URL('../lib/client.js', import.meta.url), 'utf8');
  const shortcutIcon = await readFile(new URL('../../../MetaMath-Harness.ico', import.meta.url));
  const embeddedIcon = built.match(/data:image\/x-icon;base64,([A-Za-z0-9+/=]+)/)?.[1];

  assert.match(build, /\.\.\/\.\.\/MetaMath-Harness\.ico/);
  assert.match(source, /metaMathBrandIcon/);
  assert.match(source, /__METAMATH_BRAND_ICON__/);
  assert.match(source, /sidebar\.brand\.mark/);
  assert.match(source, /sidebar\.brand\.name/);
  assert.match(source, /installMetaMathFavicon/);
  assert.match(source, /querySelectorAll\('link\[rel~="icon"\]'\)/);
  assert.match(source, /favicon\.href = metaMathBrandIcon/);
  assert.doesNotMatch(source, /svg\[width="182"\]\[height="24"\]/);
  assert.match(source, /word\.textContent = 'MetaMath'/);
  assert.match(source, /chip\.textContent = 'HARNESS'/);
  assert.ok(embeddedIcon, '构建产物必须包含桌面快捷方式 ICO');
  assert.equal(
    createHash('sha256').update(Buffer.from(embeddedIcon, 'base64')).digest('hex'),
    createHash('sha256').update(shortcutIcon).digest('hex'),
    '构建产物图标必须与桌面快捷方式 ICO 逐字节一致',
  );
});

test('品牌修复不改动大道至简相关源码片段', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  const start = source.indexOf('// 中央主视觉：');
  const endMarker = 'new MutationObserver(installMetaMathHeroTitle).observe(document.documentElement, { childList: true, subtree: true });';
  const end = source.indexOf(endMarker, start) + endMarker.length;
  assert.ok(start >= 0 && end >= endMarker.length, '必须能定位大道至简相关源码片段');
  assert.equal(
    createHash('sha256').update(source.slice(start, end)).digest('hex').toUpperCase(),
    'ACDEB684B7E9A4CD7336BCC8D128381B491078C51F22233BBB661817C7A78FCC',
  );
});

test('中央主视觉官方鲸鱼由插件运行时隐藏，且不修改官方包（GOAL-35）', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /span\[class\*="_fishHitbox"\]/);
  assert.match(source, /hitbox\.style\.display = 'none'/);
  assert.match(source, /officialFish\.style\.display = 'none'/);
  assert.match(source, /hitbox\.dataset\.dshMetamathHeroHidden = 'true'/);
  assert.doesNotMatch(source, /metaMathHeroMark/);
});

test('中央主标题替换为“大道至简”金属艺术字图并隐藏预览版徽章', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  assert.match(source, /metaMathHeroTitle/);
  assert.match(source, /__METAMATH_HERO_TITLE__/);
  assert.match(source, /titleImg\.alt = '大道至简'/);
  assert.match(source, /span\[class\*="_headlineText"\]/);
  assert.match(source, /span\[class\*="_previewBadge"\]/);
  assert.match(source, /badge\.style\.display = 'none'/);
  assert.match(source, /row\.style\.gridTemplateColumns = 'auto'/);
  assert.match(source, /row\.style\.justifyContent = 'center'/);
  assert.match(source, /\.dsh-mm-hero-title-img\{height:72px/);
});

test('技能说明入口与说明抽屉跟随 better-sidebar 布局变量避让（GOAL-66）', async () => {
  const source = await readFile(new URL('../src/client-bundle.cjs', import.meta.url), 'utf8');
  // 固定定位的右上角入口必须叠加 better-sidebar 写在 <html> 上的推挤宽度；
  // 变量缺省（未安装该插件或已收起）时回退 0，行为与历史版本一致。
  assert.match(source, /\.dsh-mm-info-launcher\{position:fixed;z-index:89;top:12px;right:calc\(72px \+ var\(--dsh-sidebar-width,0px\)\)/);
  assert.match(source, /\.dsh-mm-info\{position:fixed;z-index:90;top:56px;right:calc\(12px \+ var\(--dsh-sidebar-width,0px\)\)/);
  // 插件在场（panel-host 存在）时四按钮统一为角标簇规格 28×28@y3：
  // 入口右距 = 64 + var（展开态与 28px Session log 保持 8px）；
  // 收起态 better-sidebar 把官方头右内边距推到 78px，入口右距 = 78 + 28 + 8 = 114。
  assert.match(source, /body:has\(\[data-dsh-panel-host\]\) \.dsh-mm-info-launcher\{top:3px;right:calc\(64px \+ var\(--dsh-sidebar-width,0px\)\);width:28px;height:28px;min-height:28px;border-radius:9px\}/);
  assert.match(source, /body\[data-dsh-sidebar-collapsed\] \.dsh-mm-info-launcher\{right:114px\}/);
  assert.match(source, /body:has\(\[data-dsh-panel-host\]\) \[data-slot="conversation\.session\.header\.utilities"\]>button\[class\*="_sessionLogButton"\]\{width:28px!important;height:28px!important;min-width:28px!important;border-radius:9px!important;transform:translateY\(-11px\)\}/);
  // 窄屏媒体查询保持覆盖式定位，不叠加推挤变量。
  assert.match(source, /@media\(max-width:760px\)\{\.dsh-mm-info\{top:56px;right:6px/);
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
