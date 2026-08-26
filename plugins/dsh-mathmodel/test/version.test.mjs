import test from 'node:test';
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import {
  assertCompatibleHarnessVersion,
  detectHarnessVersion,
  SUPPORTED_DSH_VERSION,
} from '../lib/index.js';

test('只接受当前锁定的 DeepSeek Harness 版本', () => {
  assert.equal(assertCompatibleHarnessVersion(SUPPORTED_DSH_VERSION), SUPPORTED_DSH_VERSION);
});

test('错误版本给出可操作的中文错误', () => {
  assert.throws(
    () => assertCompatibleHarnessVersion('0.1.0-rc.7'),
    /需要 0\.1\.1-rc\.2，当前 0\.1\.0-rc\.7/,
  );
});

test('未知版本失败关闭', () => {
  assert.throws(() => assertCompatibleHarnessVersion(null), /当前 未检测到/);
});

test('从当前 Web Profile 解析锚点可发现官方 Harness', () => {
  const profileManifest = resolve(import.meta.dirname, '../../../.dsh/profiles/web/package.json');
  assert.equal(detectHarnessVersion(pathToFileURL(profileManifest)), SUPPORTED_DSH_VERSION);
});
