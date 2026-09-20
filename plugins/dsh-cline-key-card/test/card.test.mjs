// M04/M05 行为回归：卡片保存/清除的范围、上限与诚实状态。
// 从手写 lib/client.js 加载工厂，用最小 React stub 渲染，注入内存凭据服务；
// 不连接真实凭据服务、不读取真实 Key。
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';


const CLIENT = new URL('../lib/client.js', import.meta.url);

function makeReactStub() {
  const state = new Map();
  const setters = [];
  const counter = { i: 0 };
  return {
    _counter: counter,
    useState(init) {
      const i = counter.i++;
      if (!setters[i]) {
        setters[i] = (v) => { state.set(i, typeof v === 'function' ? v(state.get(i)) : v); };
      }
      if (!state.has(i)) state.set(i, typeof init === 'function' ? init() : init);
      return [state.get(i), setters[i]];
    },
    useEffect(cb) { void cb(); },
    useCallback(fn) { return fn; },
    createElement(tag, props, ...children) { return { tag, props, children }; },
  };
}

async function loadCard() {
  const code = await readFile(CLIENT, 'utf8');
  let loaded;
  const fakeWindow = { __ModuleLoader__: { load: (def) => { loaded = def; } } };
  new Function('window', code)(fakeWindow);
  const react = makeReactStub();
  const mod = loaded.factory((name) => { assert.equal(name, 'react'); return react; });
  let captured = null;
  const ctx = {
    remote: {},
    settingsScope: { bind: (spec) => spec },
    slots: {
      inject(_slot, fn) { fn(); },
      register(_spec, comp) { captured = comp; return comp; },
    },
  };
  mod.apply(ctx);
  assert.ok(captured, 'apply 必须注册卡片组件');
  return { mod, captured, react };
}

function collectNodes(node, pred, out = []) {
  if (Array.isArray(node)) { for (const item of node) collectNodes(item, pred, out); return out; }
  if (node === null || node === undefined) return out;
  if (typeof node !== 'object') { if (pred(node)) out.push(node); return out; }
  if (pred(node)) out.push(node);
  if (node.children) collectNodes(node.children, pred, out);
  return out;
}

function makeCredentials(initial = {}) {
  const store = new Map(Object.entries(initial));
  const calls = { set: [], unset: [], describe: [] };
  const failSetFor = new Set();
  const failUnsetFor = new Set();
  let failDescribe = false;
  return {
    store, calls, failSetFor, failUnsetFor,
    setFailDescribe() { failDescribe = true; },
    async set(ref, value) {
      calls.set.push(ref);
      if (failSetFor.has(ref)) return { ok: false, error: { message: 'set failed' } };
      store.set(ref, value);
      return { ok: true };
    },
    async describe(refs) {
      calls.describe.push([...refs]);
      if (failDescribe) return { ok: false };
      const value = {};
      for (const ref of refs) if (store.has(ref)) value[ref] = { configured: true };
      return { ok: true, value };
    },
    async unset(ref) {
      calls.unset.push(ref);
      if (failUnsetFor.has(ref)) return { ok: false, error: { message: 'unset failed' } };
      store.delete(ref);
      return { ok: true };
    },
  };
}

function makeSettingsScope(initialPool = []) {
  const writes = [];
  let failConfig = false;
  const value = { apiKeyEnvPool: [...initialPool], apiKeyCleanupRefs: [] };
  const listeners = new Set();
  return {
    writes,
    setFailConfig() { failConfig = true; },
    getSnapshot() { return { status: 'ready', writable: true, mode: 'host', value }; },
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    async set(field, next) {
      writes.push([field, next]);
      if (failConfig) throw new Error('config failed');
      value[field] = next;
      for (const fn of listeners) fn();
    },
  };
}

async function renderOpenCard(comp, remote, settingsScope, react) {
  const render = () => { react._counter.i = 0; return comp({ remote, settingsScope }); };
  let tree = render();
  const header = collectNodes(tree, n => n.tag === 'button' && n.props && n.props['aria-expanded'] !== undefined)[0];
  header.props.onClick();
  await new Promise(resolve => setImmediate(resolve));
  let cur = {};
  const refresh = () => {
    tree = render();
    cur.tree = tree;
    cur.textarea = collectNodes(tree, n => n.tag === 'textarea')[0];
    const buttons = collectNodes(tree, n => n.tag === 'button' && n.props && typeof n.props.onClick === 'function' && !n.props['aria-expanded']);
    cur.saveButton = buttons.find(b => collectNodes(b.children, n => typeof n === 'string' && n.includes('保存')).length > 0);
    cur.clearButton = buttons.find(b => b !== cur.saveButton && collectNodes(b.children, n => typeof n === 'string' && n.includes('清除')).length > 0);
  };
  refresh();
  return {
    get textarea() { refresh(); return cur.textarea; },
    get saveButton() { refresh(); return cur.saveButton; },
    get clearButton() { refresh(); return cur.clearButton; },
    setDraft(value) { this.textarea.props.onChange({ target: { value } }); },
    messageText() {
      refresh();
      const p = collectNodes(cur.tree, n => n.tag === 'p' && (n.props?.className === 'ckc-msg' || n.props?.className === 'ckc-err'))[0];
      if (!p) return null;
      return p.children.filter(c => typeof c === 'string').join('');
    },
  };
}

function setDraft(card, value) {
  card.textarea.props.onChange({ target: { value } });
}

// 卡片 onClick 为 fire-and-forget 包装，轮询等待消息状态出现。
async function clickAndWait(card, which) {
  const button = which === 'save' ? card.saveButton : card.clearButton;
  button.props.onClick();
  for (let i = 0; i < 200; i++) {
    if (card.messageText()) return;
    await new Promise(resolve => setImmediate(resolve));
  }
  throw new Error('操作后未出现任何状态消息');
}

test('M04: 粘贴 33 把不同 Key，写入前即报错且零写入', async () => {
  const { captured, react } = await loadCard();
  const remote = { credentials: makeCredentials() };
  const scope = makeSettingsScope();
  const card = await renderOpenCard(captured, remote, scope, react);
  const draft = Array.from({ length: 33 }, (_, i) => `sk-key${i + 1}`).join('\n');
  setDraft(card, draft);
  await clickAndWait(card, 'save');
  assert.equal(remote.credentials.calls.set.length, 0, '超限必须零写入');
  assert.equal(scope.writes.length, 0, '超限不得下发池配置');
  const message = card.messageText();
  assert.match(message, /最多保存 32/);
  assert.match(message, /未写入/);
});

test('M04: 重复行与空白行去重后有效；32 把可保存', async () => {
  const { captured, react } = await loadCard();
  const remote = { credentials: makeCredentials() };
  const scope = makeSettingsScope();
  const card = await renderOpenCard(captured, remote, scope, react);
  const lines = ['sk-a', '', '   ', 'sk-a', ...Array.from({ length: 31 }, (_, i) => `sk-k${i}`)];
  setDraft(card, lines.join('\n'));
  await clickAndWait(card, 'save');
  assert.equal(remote.credentials.calls.set.length, 32, '去重后正好 32 把');
  const message = card.messageText();
  assert.match(message, /已保存 32 把/);
});

test('M04/M05: 预置旧超限 ref（_33）后清除无遗漏，统计覆盖池配置 ref', async () => {
  const { captured, react } = await loadCard();
  const remote = { credentials: makeCredentials({ CLINE_API_KEY_33: 'old' }) };
  const scope = makeSettingsScope(['CLINE_API_KEY_33']);
  const card = await renderOpenCard(captured, remote, scope, react);
  await clickAndWait(card, 'clear');
  assert.ok(remote.credentials.calls.unset.includes('CLINE_API_KEY_33'), '池配置引用的旧超限 ref 必须被清除');
  assert.equal(remote.credentials.store.size, 0, '不得残留任何托管 ref');
  const message = card.messageText();
  assert.match(message, /已清除全部/);
  assert.deepEqual(scope.writes, [['apiKeyEnvPool', []], ['apiKeyCleanupRefs', []]]);
});

test('M04: 不扫描不清除其他插件 ref', async () => {
  const { captured, react } = await loadCard();
  const remote = { credentials: makeCredentials({ CLINE_API_KEY_1: 'mine', OTHER_PLUGIN_KEY: 'x' }) };
  const scope = makeSettingsScope();
  const card = await renderOpenCard(captured, remote, scope, react);
  await clickAndWait(card, 'clear');
  const allDescribed = remote.credentials.calls.describe.flat();
  assert.ok(!allDescribed.includes('OTHER_PLUGIN_KEY'), '不得扫描其他插件 ref');
  assert.ok(remote.credentials.store.has('OTHER_PLUGIN_KEY'), '其他插件凭据必须保持不变');
});

test('M05: set 失败时不删旧项、不下发配置、不误报成功', async () => {
  const { captured, react } = await loadCard();
  const remote = { credentials: makeCredentials({ CLINE_API_KEY_3: 'old3' }) };
  remote.credentials.failSetFor.add('CLINE_API_KEY_2');
  const scope = makeSettingsScope();
  const card = await renderOpenCard(captured, remote, scope, react);
  setDraft(card, 'sk-a\nsk-b\nsk-c');
  await clickAndWait(card, 'save');
  assert.ok(remote.credentials.store.has('CLINE_API_KEY_3'), '写入失败时不得删除旧池位');
  assert.equal(scope.writes.length, 0, '写入失败不得下发池配置');
  assert.equal(remote.credentials.calls.unset.length, 0, '写入失败不得触发任何 unset');
  const message = card.messageText();
  assert.match(message, /保存未完成/);
  assert.match(message, /CLINE_API_KEY_2/);
  assert.doesNotMatch(message, /已保存/);
});

test('M05: unset 失败时清除不得显示全部完成，列出失败 ref', async () => {
  const { captured, react } = await loadCard();
  const remote = { credentials: makeCredentials({ CLINE_API_KEY_1: 'x' }) };
  remote.credentials.failUnsetFor.add('CLINE_API_KEY_1');
  const scope = makeSettingsScope();
  const card = await renderOpenCard(captured, remote, scope, react);
  await clickAndWait(card, 'clear');
  assert.ok(remote.credentials.store.has('CLINE_API_KEY_1'), 'unset 失败的 ref 必须残留');
  const message = card.messageText();
  assert.doesNotMatch(message, /已清除全部/);
  assert.match(message, /CLINE_API_KEY_1/);
  assert.match(message, /未全部完成|失败/);
});

test('M05: describe 失败（状态未知）不得涂绿冒充成功', async () => {
  const { captured, react } = await loadCard();
  const remote = { credentials: makeCredentials({ CLINE_API_KEY_1: 'x' }) };
  const scope = makeSettingsScope();
  const card = await renderOpenCard(captured, remote, scope, react);
  // 初始刷新成功后注入 describe 故障，模拟清除过程中状态不可确认。
  remote.credentials.setFailDescribe();
  await clickAndWait(card, 'clear');
  assert.ok(remote.credentials.store.has('CLINE_API_KEY_1'), '无法确认状态的 ref 不得被宣称清除');
  const message = card.messageText();
  assert.doesNotMatch(message, /已清除全部/);
  assert.match(message, /状态未知|失败/);
});

test('M05: 配置写入失败时保存不得宣布完成、旧池位未清理', async () => {
  const { captured, react } = await loadCard();
  const remote = { credentials: makeCredentials({ CLINE_API_KEY_5: 'old5' }) };
  const scope = makeSettingsScope();
  scope.setFailConfig();
  const card = await renderOpenCard(captured, remote, scope, react);
  setDraft(card, 'sk-new');
  await clickAndWait(card, 'save');
  assert.ok(remote.credentials.store.has('CLINE_API_KEY_1'), '新 Key 已写入');
  assert.ok(remote.credentials.store.has('CLINE_API_KEY_5'), '配置未生效时旧池位必须保留');
  assert.equal(remote.credentials.calls.unset.length, 0, '配置未确认生效不得触发任何 unset');
  const message = card.messageText();
  assert.doesNotMatch(message, /^已保存 .*（轮询/);
  assert.match(message, /未确认生效/);
});

test('M05: 清除与保存的忙碌标签互不混淆', async () => {
  const { captured, react } = await loadCard();
  const remote = { credentials: makeCredentials({ CLINE_API_KEY_1: 'x' }) };
  const scope = makeSettingsScope();
  const card = await renderOpenCard(captured, remote, scope, react);
  // 空草稿点保存 → 立即返回错误，不进入保存忙碌态。
  setDraft(card, '');
  await clickAndWait(card, 'save');
  const message = card.messageText();
  assert.match(message, /请先粘贴/);
});



test('保存新池后清除动态快照里的旧超限ref', async () => {
  const { captured, react } = await loadCard();
  const remote = { credentials: makeCredentials({ CLINE_API_KEY_33: 'old' }) };
  const scope = makeSettingsScope(['CLINE_API_KEY_33']);
  const card = await renderOpenCard(captured, remote, scope, react);
  setDraft(card, 'fake-new');
  await clickAndWait(card, 'save');
  assert.deepEqual([...remote.credentials.store.keys()], ['CLINE_API_KEY_1']);
  assert.deepEqual(scope.getSnapshot().value.apiKeyEnvPool, ['CLINE_API_KEY_1']);
  assert.deepEqual(scope.getSnapshot().value.apiKeyCleanupRefs, []);
});

test('保存清理失败后重新挂载，全部清除仍找到超限ref', async () => {
  const first = await loadCard();
  const remote = { credentials: makeCredentials({ CLINE_API_KEY_33: 'old' }) };
  remote.credentials.failUnsetFor.add('CLINE_API_KEY_33');
  const scope = makeSettingsScope(['CLINE_API_KEY_33']);
  const card = await renderOpenCard(first.captured, remote, scope, first.react);
  setDraft(card, 'fake-new');
  await clickAndWait(card, 'save');
  assert.deepEqual(scope.getSnapshot().value.apiKeyCleanupRefs, ['CLINE_API_KEY_33']);
  assert.match(card.messageText(), /清理未完成/);
  const second = await loadCard();
  const reloaded = await renderOpenCard(second.captured, remote, scope, second.react);
  await clickAndWait(reloaded, 'clear');
  assert.deepEqual(scope.getSnapshot().value.apiKeyCleanupRefs, ['CLINE_API_KEY_33']);
  remote.credentials.failUnsetFor.clear();
  await clickAndWait(reloaded, 'clear');
  assert.equal(remote.credentials.store.size, 0);
  assert.deepEqual(scope.getSnapshot().value.apiKeyCleanupRefs, []);
});

test('配置未ready时保存与清除均不修改凭据', async () => {
  for (const status of ['loading', 'unavailable']) {
    const { captured, react } = await loadCard();
    const remote = { credentials: makeCredentials({ CLINE_API_KEY_1: 'old' }) };
    const scope = makeSettingsScope();
    scope.getSnapshot = () => ({ status, writable: false });
    const card = await renderOpenCard(captured, remote, scope, react);
    setDraft(card, 'fake-new');
    await clickAndWait(card, 'save');
    assert.equal(remote.credentials.calls.set.length, 0);
    assert.match(card.messageText(), /配置尚未就绪/);
    await clickAndWait(card, 'clear');
    assert.equal(remote.credentials.calls.unset.length, 0);
  }
});
