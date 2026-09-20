/** 版本绑定的默认重试门禁：恢复既有 6 次，不改变退避/错误码。 */
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, existsSync, lstatSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { execFileSync } from 'node:child_process';

export const SUPPORTED_VERSION = '0.1.5-rc.2';
export const TARGET_RETRIES = 6;
const ANCHOR = /\bconst DEFAULT_MAX_RETRIES = (\d+);/gu;

export function prepare(source) {
  const matches = [...source.matchAll(ANCHOR)];
  if (matches.length !== 1 || ![5, 6].includes(Number(matches[0][1]))) {
    throw new Error('重试锚点/值失配，拒绝修改；须重新核对上游。');
  }
  return source.replace(ANCHOR, 'const DEFAULT_MAX_RETRIES = 6;');
}

export function assertIndependentFile(path, inspect = lstatSync) {
  const info = inspect(path);
  if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1) {
    throw new Error(`目标不是独立普通文件，拒绝修改共享/链接产物：${path}`);
  }
}

export function patchPackage(packageDir, check = false) {
  const manifest = JSON.parse(readFileSync(join(packageDir, 'package.json'), 'utf8'));
  if (manifest.name !== '@deepseek-ai/dsh-llm' || manifest.version !== SUPPORTED_VERSION) {
    throw new Error(`未验证的 dsh-llm 包/版本：${manifest.name}@${manifest.version}`);
  }
  const rows = ['lib/index.js', 'lib/types/retry-policy.js'].map((tail) => {
    const path = join(packageDir, tail);
    const original = readFileSync(path, 'utf8');
    execFileSync(process.execPath, ['--check', path], { windowsHide: true, stdio: 'pipe' });
    const candidate = prepare(original);
    return { path, original, candidate };
  });
  if (check) {
    if (rows.some((row) => row.original !== row.candidate)) throw new Error('默认重试尚未恢复为6（双文件门禁失败）。');
    return rows;
  }
  const changed = rows.filter((row) => row.original !== row.candidate);
  // pnpm 可能硬链接共享仓库；原地写入会改到其他安装。双文件一起失败关闭。
  for (const row of changed) {
    assertIndependentFile(row.path);
  }
  // 双文件全部预检完成后才备份/写入；失败回滚本次内容，最早备份不覆盖。
  const written = [];
  try {
    for (const row of changed) {
      const backup = `${row.path}.bak-hotfix-retries`;
      if (!existsSync(backup)) writeFileSync(backup, row.original, { encoding: 'utf8', flag: 'wx' });
      written.push(row);
      writeFileSync(row.path, row.candidate, 'utf8');
      execFileSync(process.execPath, ['--check', row.path], { windowsHide: true, stdio: 'pipe' });
      if (readFileSync(row.path, 'utf8') !== row.candidate) throw new Error('重试补丁回读不一致');
    }
  } catch (error) {
    for (const row of written.reverse()) writeFileSync(row.path, row.original, 'utf8');
    throw error;
  }
  return rows;
}

function defaultPackage() {
  if (!process.env.APPDATA) throw new Error('未设置 APPDATA，请显式指定 dsh-llm 包目录');
  const dshManifest = join(process.env.APPDATA, 'npm/node_modules/@deepseek-ai/dsh/package.json');
  const require = createRequire(dshManifest);
  return dirname(dirname(require.resolve('@deepseek-ai/dsh-llm')));
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    const args = process.argv.slice(2);
    const check = args.includes('--check');
    const paths = args.filter((arg) => arg !== '--check');
    if (paths.length > 1 || paths.some((arg) => arg.startsWith('--'))) throw new Error('用法：node patch-llm-retries.mjs [--check] [dsh-llm目录]');
    const packageDir = paths[0] ? resolve(paths[0]) : defaultPackage();
    const rows = patchPackage(packageDir, check);
    console.log(`[OK] ${packageDir}：双文件默认6次；${check ? '只读检查' : '幂等重放'}；变更${rows.filter((row) => row.original !== row.candidate).length}项。运行中的实例需重启才生效。`);
  } catch (error) {
    console.error(`[FAIL] ${error.message}`);
    process.exitCode = 1;
  }
}
