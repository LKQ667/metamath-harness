import { mkdir, cp } from 'node:fs/promises';
await mkdir(new URL('../lib/', import.meta.url), { recursive: true });
for (const file of ['index.js', 'session-header.js']) {
  await cp(new URL(`../src/${file}`, import.meta.url), new URL(`../lib/${file}`, import.meta.url));
}
console.log('已从 src 构建 lib');
