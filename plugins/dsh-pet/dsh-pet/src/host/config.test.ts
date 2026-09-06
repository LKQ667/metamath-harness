import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { readAllConfig, setFilePetVisibility } from './config.ts';

test('文件宠物允许空 events，并保留自己的动画池', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-pet-config-'));
  const petDir = join(root, 'pet');
  await mkdir(petDir);
  const base = {
    whisperPrompt: 'default',
    chatMemoryRounds: 5,
    notificationsEnabled: true,
    physics: {
      gravity: 1400,
      restitution: 0.78,
      groundFriction: 2.5,
      ceilingBounce: true,
      throwPower: 1,
      petCollision: false,
    },
    pets: [
      {
        id: 'main',
        name: 'main',
        size: 260,
        balanceEnabled: true,
        whisperEnabled: false,
        display: 'web',
        position: { corner: 'top-right', marginX: 24, marginY: 100 },
      },
    ],
    animations: {
      idle: ['默认待机'],
      turn: ['默认转向'],
      drag: ['默认拖拽'],
      clicks: ['默认点击'],
      moves: { default: {}, actions: [] },
      categories: [],
      events: { balance: ['默认余额'] },
    },
    eventsRefreshSec: { balance: 1800, whisper: 300 },
    animationWeights: { idle: 100, turn: 0, move: 0 },
  };
  const niulai = {
    pets: [{ ...base.pets[0], id: 'niulai', name: '牛来', position: { ...base.pets[0].position } }],
    animations: {
      idle: ['待机'],
      turn: ['转向'],
      drag: ['拖拽'],
      clicks: ['点击回应'],
      moves: { default: {}, actions: [] },
      categories: [],
      events: {},
    },
    animationWeights: { idle: 100, turn: 0, move: 0 },
  };
  const defaultFile = join(root, 'config.jsonc');
  const userFile = join(root, 'main-config.json');
  await writeFile(defaultFile, JSON.stringify(base));
  await writeFile(join(petDir, 'niulai-config.json'), JSON.stringify(niulai));

  try {
    const merged = readAllConfig({ defaultFile, userFile, petDir });
    assert.deepEqual(merged.niulai.animations, niulai.animations);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('文件宠物关闭后可恢复原显示模式', async () => {
  const root = await mkdtemp(join(tmpdir(), 'dsh-pet-visibility-'));
  const petDir = join(root, 'pet');
  await mkdir(petDir);
  const configFile = join(petDir, 'niulai-config.json');
  await writeFile(configFile, JSON.stringify({ pets: [{ id: 'niulai', display: 'both' }] }));
  const paths = { defaultFile: join(root, 'default.json'), userFile: join(root, 'user.json'), petDir };

  try {
    assert.deepEqual(await setFilePetVisibility(paths, 'niulai', false), { display: 'none' });
    let saved = JSON.parse(await readFile(configFile, 'utf8'));
    assert.equal(saved.pets[0].display, 'none');
    assert.equal(saved.pets[0].dshPetDisplayBeforeClose, 'both');

    assert.deepEqual(await setFilePetVisibility(paths, 'niulai', true), { display: 'both' });
    saved = JSON.parse(await readFile(configFile, 'utf8'));
    assert.equal(saved.pets[0].display, 'both');
    assert.equal(saved.pets[0].dshPetDisplayBeforeClose, undefined);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
