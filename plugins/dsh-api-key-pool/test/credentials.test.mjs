import { test } from 'node:test';
import assert from 'node:assert/strict';
import { CredentialFacade, CREDENTIAL_SCOPE, maskKey, fingerprintOf } from '../src/credentials.js';

/** 模拟 ctx.credentials（对齐 dsh-credentials-local 的接口语义）。 */
function mockCredentials() {
  const records = new Map();
  return {
    records,
    async readRecord(key) { return records.get(key); },
    async listRecords() {
      return [...records.entries()].map(([key, record]) => ({ key, kind: record.kind }));
    },
    async modifyRecord(key, mutate) {
      const current = records.get(key);
      const next = await mutate(current);
      if (next === undefined) return current;
      records.set(key, next);
      return next;
    },
    async deleteRecord(key) { records.delete(key); },
  };
}

test('Key 字符集：空白/控制字符拒绝，可打印 ASCII 放行', async () => {
  const facade = new CredentialFacade(mockCredentials());
  await assert.rejects(() => facade.addKey(''), /不能为空/);
  await assert.rejects(() => facade.addKey('   '), /不能为空/);
  await assert.rejects(() => facade.addKey('sk-bad\nnewline'), /无法携带的字符/);
  await assert.rejects(() => facade.addKey('sk-bad\ttab'), /无法携带的字符/);
  await assert.rejects(() => facade.addKey('中文密钥'), /无法携带的字符/);
  await assert.rejects(() => facade.addKey(12345), /必须是字符串/);

  const ok = await facade.addKey('  sk-printable-ASCII-123  ');
  assert.match(ok.keyId, /^k-[0-9a-f-]{36}$/);
});

test('重复指纹：同值二次新增被拒绝', async () => {
  const facade = new CredentialFacade(mockCredentials());
  const first = await facade.addKey('sk-duplicate-check');
  await assert.rejects(() => facade.addKey('sk-duplicate-check'), /指纹重复/);
  // trim 后同值也算重复
  await assert.rejects(() => facade.addKey('  sk-duplicate-check  '), /指纹重复/);
  // 不同值不受影响
  const second = await facade.addKey('sk-another-key');
  assert.notEqual(first.keyId, second.keyId);
  const ids = await facade.listKeyIds();
  assert.equal(ids.length, 2);
});

test('新增写入 {kind:"api-key"} 记录到专属 scope', async () => {
  const service = mockCredentials();
  const facade = new CredentialFacade(service);
  const { keyId } = await facade.addKey('sk-scope-check');
  const record = service.records.get(`${CREDENTIAL_SCOPE}/${keyId}`);
  assert.deepEqual(record, { kind: 'api-key', key: 'sk-scope-check' });
});

test('删除与回滚：删除幂等，删除后解析为 undefined', async () => {
  const facade = new CredentialFacade(mockCredentials());
  const { keyId } = await facade.addKey('sk-removal-flow');

  assert.equal(await facade.resolveValue(keyId), 'sk-removal-flow');
  assert.equal(await facade.removeKey(keyId), true);
  assert.equal(await facade.resolveValue(keyId), undefined);
  // 二次删除：不存在 → false，不抛错
  assert.equal(await facade.removeKey(keyId), false);
  // 非法 keyId：false，不抛错
  assert.equal(await facade.removeKey('not-a-key-id'), false);
  assert.equal(await facade.resolveValue('not-a-key-id'), undefined);
});

test('空存储值视为不存在', async () => {
  const service = mockCredentials();
  const facade = new CredentialFacade(service);
  const { keyId } = await facade.addKey('sk-then-blanked');
  service.records.set(`${CREDENTIAL_SCOPE}/${keyId}`, { kind: 'api-key', key: '   ' });
  assert.equal(await facade.resolveValue(keyId), undefined);
});

test('脱敏列表：输出不含完整 Key', async () => {
  const facade = new CredentialFacade(mockCredentials());
  const raw = 'sk-fixture-secret-1234';
  await facade.addKey(raw);
  await facade.addKey('sk-fixture-secret-5678');
  const entries = await facade.describeKeys();
  assert.equal(entries.length, 2);
  for (const entry of entries) {
    assert.ok(!JSON.stringify(entry).includes(raw));
    assert.ok(!JSON.stringify(entry).includes('sk-fixture-secret-5678'));
    assert.match(entry.keyId, /^k-/);
    assert.equal(entry.fingerprint.length, 16);
    assert.match(entry.masked, /^sk-….{4}$/);
  }
});

test('孤儿报告：未被引用的记录被列出', async () => {
  const facade = new CredentialFacade(mockCredentials());
  const a = await facade.addKey('sk-orphan-a');
  const b = await facade.addKey('sk-orphan-b');
  const c = await facade.addKey('sk-orphan-c');
  const orphans = await facade.orphanKeyIds([a.keyId, c.keyId]);
  assert.deepEqual(orphans, [b.keyId]);
  const none = await facade.orphanKeyIds([a.keyId, b.keyId, c.keyId]);
  assert.deepEqual(none, []);
});

test('maskKey/fingerprintOf 基本行为', () => {
  assert.equal(maskKey('short'), '…');
  assert.equal(maskKey('123456789012'), '…');
  assert.equal(maskKey('12345678901234'), '123…1234');
  assert.equal(maskKey(undefined), '…');
  const fp1 = fingerprintOf('same');
  const fp2 = fingerprintOf('same');
  const fp3 = fingerprintOf('different');
  assert.equal(fp1, fp2);
  assert.notEqual(fp1, fp3);
});
