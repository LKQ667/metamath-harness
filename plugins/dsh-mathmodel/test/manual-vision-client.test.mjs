import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { appendStagedImagesDraft, createManualVisionActions } = require('../src/client-bundle.cjs');

function fixture() {
  let draft = '请分析图片';
  let imageIds = ['one'];
  const removed = [];
  const released = [];
  const notices = [];
  const input = {
    state: { getSnapshot: () => ({ draft, imageIds }) },
    setDraft: (value) => { draft = value; },
    removeImage: (id) => { removed.push(id); imageIds = imageIds.filter((item) => item !== id); },
    notify: (level, text) => notices.push([level, text]),
  };
  return {
    get draft() { return draft; }, get imageIds() { return imageIds; }, removed, released, notices,
    input,
  };
}

test('手动附图只写回草稿，不自动发送，并在成功后移除原图', async () => {
  const state = fixture();
  const calls = [];
  const actions = createManualVisionActions({
    stage: async (images, workspace) => { calls.push([images, workspace]); return { files: [{ name: '图.png', path: 'uploads/img-1786790000000-1.png', bytes: 4 }] }; },
    workspaceOf: () => 'F:\\工作区',
    draftImages: () => [{ id: 'one', file: { name: '图.png' } }],
    releaseDraftImages: (attachments) => state.released.push(...attachments.map((item) => item.id)),
    inputForSession: () => state.input,
    notify: () => {},
    encodeImage: async (file) => ({ mediaType: 'image/png', data: 'iVBORw==', name: file.name }),
  });
  await actions.stageToDraft({ sessionId: 'session-1', imageIds: ['one'] });
  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0][0], [{ mediaType: 'image/png', data: 'iVBORw==', name: '图.png' }]);
  assert.equal(calls[0][1], 'F:\\工作区');
  assert.match(state.draft, /^请分析图片\n\n\[已附图片（claude-vision-skill）——请用 vision_analyze 工具查看原图\]/);
  assert.match(state.draft, /uploads\/img-1786790000000-1\.png/);
  assert.deepEqual(state.removed, ['one']);
  assert.deepEqual(state.released, ['one']);
  assert.deepEqual(state.imageIds, []);
  assert.match(state.notices.at(-1)[1], /视觉工具/);
});

test('会话没有工作区时附图失败且不改写草稿', async () => {
  const state = fixture();
  const actions = createManualVisionActions({
    stage: async () => { throw new Error('不应调用'); },
    workspaceOf: () => undefined,
    draftImages: () => [{ id: 'one', file: { name: '图.png' } }],
    releaseDraftImages: (attachments) => state.released.push(...attachments.map((item) => item.id)),
    inputForSession: () => state.input,
    notify: () => {},
    encodeImage: async () => ({ mediaType: 'image/png', data: 'iVBORw==' }),
  });
  await assert.rejects(() => actions.stageToDraft({ sessionId: 'session-1', imageIds: ['one'] }), /工作区/);
  assert.equal(state.draft, '请分析图片');
  assert.deepEqual(state.removed, []);
  assert.deepEqual(state.released, []);
});

test('手动附图失败时不改写草稿、不移除图片', async () => {
  const state = fixture();
  const actions = createManualVisionActions({
    stage: async () => { throw new Error('工作区写入失败'); },
    workspaceOf: () => 'F:\\工作区',
    draftImages: () => [{ id: 'one', file: { name: '图.png' } }],
    releaseDraftImages: (attachments) => state.released.push(...attachments.map((item) => item.id)),
    inputForSession: () => state.input,
    notify: () => {},
    encodeImage: async () => ({ mediaType: 'image/png', data: 'iVBORw==' }),
  });
  await assert.rejects(() => actions.stageToDraft({ sessionId: 'session-1', imageIds: ['one'] }), /工作区写入失败/);
  assert.equal(state.draft, '请分析图片');
  assert.deepEqual(state.removed, []);
  assert.deepEqual(state.released, []);
});

test('附图块使用可追溯边界且包含 vision_analyze 指引', () => {
  assert.equal(
    appendStagedImagesDraft('', [{ name: 'x.png', path: 'uploads/img-1-1.png' }]),
    '[已附图片（claude-vision-skill）——请用 vision_analyze 工具查看原图]\n图片 1（x.png）：uploads/img-1-1.png\n[/已附图片]',
  );
  assert.throws(() => appendStagedImagesDraft('', [{ name: 'x.png', path: '' }]), /文件路径/);
});
