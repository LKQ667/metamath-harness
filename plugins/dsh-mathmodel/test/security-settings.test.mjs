import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CredentialFacade, CREDENTIAL_ALLOWLIST, DEFAULT_PROVIDER_SETTINGS, ProviderSettingsFacade,
  redactText, validateProviderSettings,
} from '../lib/index.js';

class FakeCredentials {
  values = new Map();
  async describe(ref) { return { configured: this.values.has(ref), writable: true, ...(this.values.has(ref) ? { source: 'file' } : {}) }; }
  async set(ref, value) { this.values.set(ref, value); }
  async unset(ref) { this.values.delete(ref); }
  async resolve() { throw new Error('配置代理绝不能读取凭据值'); }
}

test('凭据代理只允许四个引用且 describe 永不返回值', async () => {
  assert.deepEqual(CREDENTIAL_ALLOWLIST, ['DASHSCOPE_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY', 'CUSTOM_IMAGE_API_KEY']);
  const facade = new CredentialFacade(new FakeCredentials());
  const info = await facade.set('DASHSCOPE_API_KEY', 'secret-fixture-value');
  assert.deepEqual(info, { ref: 'DASHSCOPE_API_KEY', configured: true, writable: true, source: 'file' });
  assert.equal('value' in info, false);
  await assert.rejects(() => facade.describe('DEEPSEEK_API_KEY'), /不允许管理/);
  assert.equal((await facade.unset('DASHSCOPE_API_KEY')).configured, false);
});

test('凭据写入错误会删除提交值和常见 token 形态', async () => {
  const provider = new FakeCredentials();
  provider.set = async (_ref, value) => { throw new Error(`写入失败 ${value} Bearer sk-test_1234567`); };
  await assert.rejects(
    () => new CredentialFacade(provider).set('OPENAI_API_KEY', 'known-secret-value'),
    (error) => !error.message.includes('known-secret-value') && !error.message.includes('sk-test_'),
  );
  assert.equal(redactText('https://x.test?a=1&api_key=secret'), 'https://x.test?a=1&api_key=[REDACTED]');
});

test('普通设置拒绝未知键、重复供应商和带凭据 URL', () => {
  assert.throws(() => validateProviderSettings({ secret: 'x' }), /未知供应商设置/);
  assert.throws(() => validateProviderSettings({ providerOrder: ['dashscope', 'dashscope', 'openai', 'gemini'] }), /各一次/);
  assert.throws(() => validateProviderSettings({ customBaseUrl: 'not-a-url' }), /必须是有效 URL/);
  assert.throws(() => validateProviderSettings({ customBaseUrl: 'http://example.com/v1' }), /必须使用 HTTPS/);
  assert.throws(() => validateProviderSettings({ customBaseUrl: 'https://user:pass@example.com/v1' }), /不得内嵌凭据/);
  assert.throws(() => validateProviderSettings({ openaiModel: '   ' }), /openaiModel 不能为空/);
  assert.throws(() => validateProviderSettings({ customBaseUrl: 'https://example.com/v1', customModel: '' }), /customModel 不能为空/);
  assert.equal(validateProviderSettings({ customBaseUrl: 'http://localhost:3000/v1', customModel: 'fixture-model' }).customBaseUrl, 'http://localhost:3000/v1');
});

test('设置 facade 通过 DSH scope 更新和复位', async () => {
  let value = { ...DEFAULT_PROVIDER_SETTINGS, providerOrder: [...DEFAULT_PROVIDER_SETTINGS.providerOrder] };
  const scope = {
    get: () => value,
    update: async (patch) => { value = { ...value, ...patch }; },
    replace: async () => { value = { ...DEFAULT_PROVIDER_SETTINGS, providerOrder: [...DEFAULT_PROVIDER_SETTINGS.providerOrder] }; },
  };
  const facade = new ProviderSettingsFacade(scope);
  assert.equal((await facade.update({ customModel: 'image-model' })).customModel, 'image-model');
  assert.equal((await facade.reset()).customModel, '');
});
