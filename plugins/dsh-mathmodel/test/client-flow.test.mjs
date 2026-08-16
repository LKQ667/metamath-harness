import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { createCardFlow, createCredentialActions, createSkillSource } = require('../src/client-bundle.cjs');
const card = {
  skill: 'demo-card', title: '演示卡片', summary: '配置后写入草稿', category: 'test',
  fields: [{ id: 'mode', label: '模式', type: 'select', options: ['safe'], default: 'safe' }],
};

test('普通 Skill 保持官方字面插入行为，卡片 Skill 只打开表单', async () => {
  const opened = [];
  const cards = new Map([['demo-card', card]]);
  cards.catalog = [{ name: 'demo-card' }, { name: 'plain-skill' }];
  const source = createSkillSource({ fetchCatalog: async () => cards.catalog, cardsForSession: () => cards, flow: { open: (value) => opened.push(value) } });
  const plain = source.onPick({ candidate: { name: 'plain-skill' }, session: { sessionId: 's1' }, span: { start: 0, end: 12, draftRev: 1 } });
  assert.deepEqual(plain, { text: '/plain-skill ' });
  const handled = source.onPick({ candidate: { name: 'demo-card' }, session: { sessionId: 's1' }, span: { start: 0, end: 10, draftRev: 2 } });
  assert.equal(handled, 'handled');
  assert.equal(opened.length, 1);
});

test('取消保留原草稿并解除 composer block', () => {
  const blocks = [];
  const flow = createCardFlow({ renderDraft: async () => ({}), insertDraft: async () => true, setBlock: (...args) => blocks.push(args), notify: () => {} });
  flow.open({ sessionId: 's1', span: { start: 0, end: 5, draftRev: 3 }, card });
  flow.cancel();
  assert.equal(flow.getSnapshot().open, false);
  assert.deepEqual(blocks.at(-1), ['s1', undefined]);
});

test('确认只调用 CAS 草稿插入，不具备发送动作', async () => {
  const inserts = [];
  const span = { start: 0, end: 10, draftRev: 7 };
  const flow = createCardFlow({
    renderDraft: async () => ({ text: '/demo-card\n{}' }),
    insertDraft: async (...args) => { inserts.push(args); return true; },
    setBlock: () => {}, notify: () => {},
  });
  flow.open({ sessionId: 's1', span, card });
  assert.equal(await flow.confirm(), true);
  assert.deepEqual(inserts, [['s1', span, '/demo-card\n{}']]);
  assert.equal(flow.getSnapshot().open, false);
});

test('CAS 冲突不覆盖草稿并提示重新打开', async () => {
  const notices = [];
  const flow = createCardFlow({ renderDraft: async () => ({ text: 'draft' }), insertDraft: async () => false, setBlock: () => {}, notify: (...args) => notices.push(args) });
  flow.open({ sessionId: 's1', span: { start: 0, end: 3, draftRev: 1 }, card });
  assert.equal(await flow.confirm(), false);
  assert.match(notices[0][2], /草稿已变化/);
  assert.equal(flow.getSnapshot().open, false);
});

test('凭据配置后保持原卡片打开且不把 Key 放入表单状态', async () => {
  const flow = createCardFlow({ renderDraft: async () => ({ text: '' }), insertDraft: async () => true, setBlock: () => {}, notify: () => {} });
  const visionCard = { ...card, fields: [...card.fields, { id: 'dashscope_key_status', label: 'Key 状态', type: 'credential-status', default: '未检测' }] };
  flow.open({ sessionId: 's1', span: { start: 0, end: 2, draftRev: 1 }, card: visionCard });
  let stored;
  const actions = createCredentialActions({
    describe: async () => ({ configured: false, writable: true }),
    set: async (_ref, value) => { stored = value; return { configured: true, writable: true, source: 'file' }; },
    unset: async () => ({ configured: false, writable: true }),
  }, flow);
  await actions.set('dashscope_key_status', 'fixture-secret');
  const state = flow.getSnapshot();
  assert.equal(stored, 'fixture-secret');
  assert.equal(state.open, true);
  assert.equal(state.values.mode, 'safe');
  assert.equal(state.values.dashscope_key_status, '已配置（file）');
  assert.doesNotMatch(JSON.stringify(state), /fixture-secret/);
});
