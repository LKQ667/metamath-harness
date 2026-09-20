/**
 * 表情包池单元测试 —— 钉住「配置 memes ↔ 磁盘图片」的对齐规则与选图/校验语义：
 * 文件缺失的条目必须剔除（用户删图不必同步改配置）、描述为空的条目剔除、
 * 非对象/数组等非法形态 → 空池（不抛错，退化为纯文本碎碎念）。
 *
 * 跑法：node --experimental-strip-types --test src/host/memes.test.ts
 */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

import { matchMeme, pickMeme, readMemePool } from './memes.ts';

/** 造一个临时 assets 根，并按 names 写同名 png（内容无关，只要存在） */
function withAssets(names: string[], run: (assetsRoot: string) => void): void {
  const dir = mkdtempSync(join(tmpdir(), 'dsh-pet-memes-test-'));
  try {
    const memesDir = join(dir, 'memes');
    mkdirSync(memesDir, { recursive: true });
    for (const n of names) writeFileSync(join(memesDir, n + '.png'), 'x');
    run(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

describe('readMemePool —— 配置与磁盘的对齐', () => {
  test('命中的条目进池（描述去空白）', () => {
    withAssets(['可爱', '吃白饭的大肥鱼'], (root) => {
      const pool = readMemePool({ 可爱: ' 卖萌立绘 ', 吃白饭的大肥鱼: '躺平扒饭' }, root);
      assert.equal(pool.length, 2);
      assert.equal(pool.find((m) => m.name === '可爱')?.desc, '卖萌立绘');
      assert.ok(pool.some((m) => m.name === '吃白饭的大肥鱼'));
    });
  });

  test('配置里有、磁盘上没有的图 → 剔除（删图不必同步改配置）', () => {
    withAssets(['可爱'], (root) => {
      const pool = readMemePool({ 可爱: '卖萌', 不存在的图: '随便写' }, root);
      assert.deepEqual(
        pool.map((m) => m.name),
        ['可爱'],
      );
    });
  });

  test('磁盘上有、配置里没写的图 → 不进池（无从得知描述）', () => {
    withAssets(['可爱', '未登记的图'], (root) => {
      const pool = readMemePool({ 可爱: '卖萌' }, root);
      assert.equal(pool.length, 1);
    });
  });

  test('描述为空/仅空白/非字符串 → 剔除', () => {
    withAssets(['a', 'b', 'c'], (root) => {
      const pool = readMemePool({ a: '', b: '   ', c: 42 }, root);
      assert.equal(pool.length, 0);
    });
  });

  test('非法 memes 形态 → 空池且不抛错', () => {
    withAssets(['可爱'], (root) => {
      for (const bad of [undefined, null, 42, 'str', ['可爱'] as unknown]) {
        assert.deepEqual(readMemePool(bad, root), []);
      }
    });
  });

  test('目录不存在 → 空池（未打包/被删也不崩）', () => {
    const dir = mkdtempSync(join(tmpdir(), 'dsh-pet-memes-test-'));
    try {
      assert.deepEqual(readMemePool({ 可爱: '卖萌' }, join(dir, 'nope')), []);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe('pickMeme —— 随机抽图', () => {
  const pool = [
    { name: 'a', desc: 'A' },
    { name: 'b', desc: 'B' },
    { name: 'c', desc: 'C' },
  ];

  test('空池 → undefined', () => {
    assert.equal(pickMeme([]), undefined);
  });

  test('按 random 落点取对应项', () => {
    assert.equal(pickMeme(pool, () => 0)?.name, 'a');
    assert.equal(pickMeme(pool, () => 0.5)?.name, 'b');
    assert.equal(pickMeme(pool, () => 0.99)?.name, 'c');
  });

  test('random 返回 1（边界）不越界', () => {
    assert.equal(pickMeme(pool, () => 1)?.name, 'a');
  });
});

describe('matchMeme —— 模型选图校验', () => {
  const pool = [
    { name: '可爱', desc: '卖萌' },
    { name: '死掉了', desc: '累瘫' },
  ];

  test('池内命中 → 返回该条目', () => {
    assert.equal(matchMeme(pool, '死掉了')?.desc, '累瘫');
  });

  test('池外名称（模型幻觉）→ undefined', () => {
    assert.equal(matchMeme(pool, '不存在的图'), undefined);
  });

  test('空白/非字符串 → undefined', () => {
    assert.equal(matchMeme(pool, ''), undefined);
    assert.equal(matchMeme(pool, '   '), undefined);
    assert.equal(matchMeme(pool, undefined as unknown as string), undefined);
  });

  test('前后空白被容忍（模型多打空格也能命中）', () => {
    assert.equal(matchMeme(pool, ' 可爱 ')?.desc, '卖萌');
  });
});
