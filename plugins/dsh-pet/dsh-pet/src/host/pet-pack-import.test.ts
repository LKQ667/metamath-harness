import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { describe, test } from 'node:test';

import { importPetPack, PetPackImportError, type PetPackUploadPayload } from './pet-pack-import.ts';

function validConfig(id = 'niu-lai'): string {
  return JSON.stringify({
    pets: [{ id, name: '牛来' }],
    animations: {
      idle: ['待机'],
      turn: [],
      drag: [],
      clicks: ['叫妈妈'],
      moves: { default: {}, actions: [] },
      categories: [],
      events: {},
    },
    animationWeights: { idle: 100, turn: 0, move: 0 },
  });
}

function payload(config = validConfig()): PetPackUploadPayload {
  return {
    files: [
      { path: 'niu-lai/niu-lai-config.json', data: Buffer.from(config).toString('base64') },
      { path: 'niu-lai/niu-lai-animation/待机.webm', data: Buffer.from('webm-idle').toString('base64') },
      { path: 'niu-lai/niu-lai-animation/叫妈妈.webm', data: Buffer.from('webm-mama').toString('base64') },
    ],
  };
}

function withTempPetDir(fn: (petDir: string) => Promise<void>): Promise<void> {
  const root = mkdtempSync(join(tmpdir(), 'dsh-pet-import-test-'));
  return fn(join(root, 'pet')).finally(() => rmSync(root, { recursive: true, force: true }));
}

describe('importPetPack', () => {
  test('导入完整目录并保持原始文件内容', async () => {
    await withTempPetDir(async (petDir) => {
      const result = await importPetPack(payload(), { petDir, existingPetIds: new Set(['main']) });
      assert.deepEqual(result, { prefix: 'niu-lai', petCount: 1, animationCount: 2 });
      assert.equal(readFileSync(join(petDir, 'niu-lai-config.json'), 'utf8'), validConfig());
      assert.equal(readFileSync(join(petDir, 'niu-lai-animation', '叫妈妈.webm'), 'utf8'), 'webm-mama');
    });
  });

  test('拒绝路径穿越', async () => {
    await withTempPetDir(async (petDir) => {
      const bad = payload();
      bad.files?.push({ path: '../escape.webm', data: Buffer.from('x').toString('base64') });
      await assert.rejects(
        importPetPack(bad, { petDir, existingPetIds: new Set() }),
        (error: unknown) => error instanceof PetPackImportError && error.status === 400,
      );
    });
  });

  test('拒绝配置引用缺失素材', async () => {
    await withTempPetDir(async (petDir) => {
      const bad = payload();
      bad.files = bad.files?.filter((file) => !file.path.endsWith('叫妈妈.webm'));
      await assert.rejects(importPetPack(bad, { petDir, existingPetIds: new Set() }), /叫妈妈\.webm/);
    });
  });

  test('拒绝覆盖同名前缀', async () => {
    await withTempPetDir(async (petDir) => {
      await importPetPack(payload(), { petDir, existingPetIds: new Set() });
      await assert.rejects(
        importPetPack(payload(validConfig('niu-lai-2')), { petDir, existingPetIds: new Set() }),
        (error: unknown) => error instanceof PetPackImportError && error.status === 409,
      );
    });
  });

  test('拒绝与现有宠物实例冲突的 id', async () => {
    await withTempPetDir(async (petDir) => {
      await assert.rejects(
        importPetPack(payload(), { petDir, existingPetIds: new Set(['niu-lai']) }),
        (error: unknown) => error instanceof PetPackImportError && error.status === 409,
      );
    });
  });
});
