import { cp, mkdir, readdir, rm } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const src = join(root, 'src');
const lib = join(root, 'lib');

await rm(lib, { recursive: true, force: true });
await mkdir(lib, { recursive: true });
const entries = await readdir(src, { withFileTypes: true });
for (const entry of entries) {
  if (entry.isFile()) await cp(join(src, entry.name), join(lib, entry.name));
}
console.log(`[build] src -> lib（${entries.filter((e) => e.isFile()).length} 个文件）`);
