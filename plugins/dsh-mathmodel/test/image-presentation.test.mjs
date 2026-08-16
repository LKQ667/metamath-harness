import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { attachGeneratedImages, imageOutput, presentImageResult } from '../src/tools.js';

test('生成文件保存为原生附件引用且模型输出不含绝对路径', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-image-presentation-'));
  const file = join(root, 'cat.png');
  await writeFile(file, Buffer.from('89504e470d0a1a0a', 'hex'));
  const calls = [];
  const ref = { attachmentId: 'sha256:test', mediaType: 'image/png', bytes: 8, width: 1, height: 1, name: 'cat.png' };
  const result = await attachGeneratedImages(
    { ok: true, provider: 'custom', model: 'image-model', files: [file] },
    { workspace: root, attachments: { saveImage: async (input) => { calls.push(input); return ref; } } },
  );
  assert.equal(calls[0].mediaType, 'image/png');
  assert.equal(calls[0].name, 'cat.png');
  assert.deepEqual(result.attachments, [ref]);
  assert.deepEqual(result.displayFiles, ['cat.png']);
  const rendered = imageOutput.render({}, result)[0].text;
  assert.match(rendered, /cat\.png/);
  assert.doesNotMatch(rendered, new RegExp(root.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
});

test('展示层只对成功附件结果渲染图片块', () => {
  const ref = { attachmentId: 'sha256:test', mediaType: 'image/png', bytes: 8, width: 1, height: 1 };
  const meta = imageOutput.presentationMeta({}, { ok: true, attachments: [ref] });
  const view = presentImageResult({}, { isError: false, content: [{ type: 'text', text: 'ok' }], meta });
  assert.equal(view.card, 'generic');
  assert.equal(view.title, '已生成 1 张图片');
  assert.deepEqual(view.content.at(-1), { type: 'image', attachment: ref });
  assert.equal(presentImageResult({}, { isError: true, content: [], meta }), undefined);
  assert.equal(presentImageResult({}, { isError: false, content: [], meta: imageOutput.presentationMeta({}, { ok: false }) }), undefined);
});
