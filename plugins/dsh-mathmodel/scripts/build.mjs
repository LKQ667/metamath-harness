import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const brandMark = await readFile(resolve(root, 'src/assets/metamath-brand-mark.png'), 'base64');
const heroTitle = await readFile(resolve(root, 'src/assets/metamath-hero-title.png'), 'base64');
const files = [
  ['src/index.js', 'lib/index.js'],
  ['src/host.js', 'lib/host.js'],
  ['src/typert-shared.js', 'lib/typert-shared.js'],
  ['src/typert.host.js', 'lib/typert.host.js'],
  ['src/typert.remote-client.js', 'lib/typert.remote-client.js'],
  ['src/client-bundle.cjs', 'lib/client.js'],
  ['src/version.js', 'lib/version.js'],
  ['src/cards/schema.js', 'lib/cards/schema.js'],
  ['src/cards/registry.js', 'lib/cards/registry.js'],
  ['src/cards/prompt.js', 'lib/cards/prompt.js'],
  ['src/cards/remote.js', 'lib/cards/remote.js'],
  ['src/preflight.js', 'lib/preflight.js'],
  ['src/security/redact.js', 'lib/security/redact.js'],
  ['src/security/credentials.js', 'lib/security/credentials.js'],
  ['src/security/provider-settings.js', 'lib/security/provider-settings.js'],
  ['src/security/image-connections.js', 'lib/security/image-connections.js'],
  ['src/security/image-credentials.js', 'lib/security/image-credentials.js'],
  ['src/vision.js', 'lib/vision.js'],
  ['src/opencode-rt.js', 'lib/opencode-rt.js'],
  ['src/model-discovery.js', 'lib/model-discovery.js'],
  ['src/image/adapters.js', 'lib/image/adapters.js'],
  ['src/image/assets.js', 'lib/image/assets.js'],
  ['src/image/codex-auth.js', 'lib/image/codex-auth.js'],
  ['src/image/grok-auth.js', 'lib/image/grok-auth.js'],
  ['src/image/verify.js', 'lib/image/verify.js'],
  ['src/image/connections.js', 'lib/image/connections.js'],
  ['src/image/service.js', 'lib/image/service.js'],
  ['src/tool-contracts.js', 'lib/tool-contracts.js'],
  ['src/tools.js', 'lib/tools.js'],
  ['types/index.d.ts', 'lib/types/index.d.ts'],
  ['types/client.d.ts', 'lib/types/client.d.ts'],
  ['types/tools.d.ts', 'lib/types/tools.d.ts'],
];

for (const [source, target] of files) {
  const output = resolve(root, target);
  await mkdir(dirname(output), { recursive: true });
  if (source === 'src/client-bundle.cjs') {
    const bundle = await readFile(resolve(root, source), 'utf8');
    await writeFile(output, bundle.replace('__METAMATH_BRAND_MARK__', brandMark).replace('__METAMATH_HERO_TITLE__', heroTitle));
  } else {
    await copyFile(resolve(root, source), output);
  }
}

console.log(`dsh-mathmodel: 已构建 ${files.length} 个文件`);
