import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, existsSync, rmSync, linkSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { patchPackage, prepare, assertIndependentFile, SUPPORTED_VERSION } from './patch-llm-retries.mjs';

const source = 'const DEFAULT_MAX_RETRIES = 5;\nconst backoff = { maxDelayMs: 10000 };\n';
function fixture(run) {
  const root = mkdtempSync(join(tmpdir(), 'dsh-retry-gate-'));
  mkdirSync(join(root, 'lib/types'), { recursive: true });
  writeFileSync(join(root, 'package.json'), JSON.stringify({ name: '@deepseek-ai/dsh-llm', version: SUPPORTED_VERSION }));
  const paths = ['lib/index.js', 'lib/types/retry-policy.js'].map((tail) => join(root, tail));
  for (const path of paths) writeFileSync(path, source);
  try { run(root, paths); } finally { rmSync(root, { recursive: true, force: true }); }
}
test('exact change only; idempotent dual-file check and original backup', () => fixture((root, paths) => {
  assert.throws(() => patchPackage(root, true), /尚未恢复/);
  patchPackage(root);
  for (const path of paths) {
    assert.equal(readFileSync(path, 'utf8'), source.replace('= 5;', '= 6;'));
    assert.equal(readFileSync(`${path}.bak-hotfix-retries`, 'utf8'), source);
  }
  assert.equal(patchPackage(root).filter((row) => row.original !== row.candidate).length, 0);
  patchPackage(root, true);
}));
test('unknown version rejected without writes', () => fixture((root, paths) => {
  writeFileSync(join(root, 'package.json'), JSON.stringify({ name: '@deepseek-ai/dsh-llm', version: '0.1.6-rc.1' }));
  assert.throws(() => patchPackage(root), /未验证/);
  for (const path of paths) assert.equal(readFileSync(path, 'utf8'), source);
}));
test('second file anchor drift leaves first file and backups untouched', () => fixture((root, paths) => {
  writeFileSync(paths[1], 'const DEFAULT_MAX_RETRIES = 99;');
  assert.throws(() => patchPackage(root), /锚点/);
  assert.equal(readFileSync(paths[0], 'utf8'), source);
  for (const path of paths) assert.equal(existsSync(`${path}.bak-hotfix-retries`), false);
}));
test('syntax failure preflight leaves first file unchanged', () => fixture((root, paths) => {
  writeFileSync(paths[1], `${source}const broken = ;`);
  assert.throws(() => patchPackage(root));
  assert.equal(readFileSync(paths[0], 'utf8'), source);
}));
test('absent or repeated anchor fails closed', () => {
  assert.throws(() => prepare(''), /锚点/);
  assert.throws(() => prepare(source + source), /锚点/);
});
test('shared hardlink rejected before either target or backup changes', () => fixture((root, paths) => {
  const shared = join(root, 'shared-store.js');
  linkSync(paths[1], shared);
  assert.throws(() => patchPackage(root), /独立普通文件/);
  for (const path of [...paths, shared]) assert.equal(readFileSync(path, 'utf8'), source);
  for (const path of paths) assert.equal(existsSync(`${path}.bak-hotfix-retries`), false);
}));
test('symbolic metadata and non-files rejected without privileged symlink creation', () => {
  // Windows 创建文件符号链接要求特权，不修改系统设置；真实硬链接集成另有用例。
  const inspect = (path) => {
    assert.equal(path, 'synthetic-target.js');
    return { isFile:()=>true, isSymbolicLink:()=>true, nlink:1 };
  };
  assert.throws(()=>assertIndependentFile('synthetic-target.js',inspect), /独立普通文件/);
  assert.throws(()=>assertIndependentFile('synthetic-target.js',()=>({isFile:()=>false,isSymbolicLink:()=>false,nlink:1})), /独立普通文件/);
});
