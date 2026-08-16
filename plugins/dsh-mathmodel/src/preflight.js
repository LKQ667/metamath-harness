import { access } from 'node:fs/promises';
import { constants } from 'node:fs';
import { spawn } from 'node:child_process';
import { isAbsolute, join, relative, resolve } from 'node:path';

const WINDOWS = process.platform === 'win32';
const DRAWIO_CANDIDATES = WINDOWS
  ? ['C:\\Program Files\\draw.io\\draw.io.exe', 'D:\\draw.io\\draw.io.exe']
  : ['/usr/bin/drawio', '/usr/local/bin/drawio'];
const PYTHON_CANDIDATES = WINDOWS ? ['D:\\python\\python.exe'] : [];
const COMMANDS = [
  { id: 'xelatex', label: 'XeLaTeX', names: ['xelatex'], bundled: ['texlive/bin/windows/xelatex.exe'], args: ['--version'], guidance: '安装最小 TeX Live，并确保 xelatex 可执行。' },
  { id: 'latexmk', label: 'latexmk', names: ['latexmk'], bundled: ['texlive/bin/windows/latexmk.exe'], args: ['--version'], guidance: '在 TeX Live 中启用 latexmk。' },
  { id: 'drawio', label: 'Draw.io', names: ['draw.io', 'drawio'], bundled: ['drawio/draw.io.exe'], candidates: DRAWIO_CANDIDATES, args: ['--version'], guidance: '安装 Draw.io Desktop；无需修改系统 PATH，也可在标准路径发现。' },
  { id: 'pdftoppm', label: 'pdftoppm', names: ['pdftoppm'], bundled: ['poppler/Library/bin/pdftoppm.exe', 'poppler/bin/pdftoppm.exe'], args: ['-v'], guidance: '安装 Poppler PDF 工具。' },
  { id: 'pdfinfo', label: 'pdfinfo', names: ['pdfinfo'], bundled: ['poppler/Library/bin/pdfinfo.exe', 'poppler/bin/pdfinfo.exe'], args: ['-v'], guidance: '安装 Poppler PDF 工具。' },
];

const PYTHON_PACKAGES = [
  ['numpy', 'NumPy'],
  ['matplotlib', 'Matplotlib'],
  ['pandas', 'Pandas'],
  ['scipy', 'SciPy'],
];

async function executable(path) {
  try {
    await access(path, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

export async function runReadonlyProcess(file, args = [], { timeoutMs = 5000 } = {}) {
  return await new Promise((resolve) => {
    if (WINDOWS && /\.(?:cmd|bat)$/i.test(file)) {
      resolve({ ok: false, code: null, stdout: '', stderr: '', error: '为避免 shell 注入，不直接执行脚本包装器' });
      return;
    }
    let child;
    try {
      child = spawn(file, args, { windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    } catch (error) {
      resolve({ ok: false, code: null, stdout: '', stderr: '', error: error.message });
      return;
    }
    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => child.kill(), timeoutMs);
    child.stdout.on('data', (chunk) => { stdout = (stdout + chunk).slice(-16_384); });
    child.stderr.on('data', (chunk) => { stderr = (stderr + chunk).slice(-16_384); });
    child.on('error', (error) => {
      clearTimeout(timer);
      resolve({ ok: false, code: null, stdout, stderr, error: error.message });
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      resolve({ ok: code === 0, code, stdout, stderr, error: null });
    });
  });
}

export async function locateExecutable(names, candidates = [], run = runReadonlyProcess) {
  for (const candidate of candidates) {
    if (await executable(candidate)) return candidate;
  }
  const finder = WINDOWS ? 'where.exe' : 'which';
  for (const name of names) {
    const result = await run(finder, [name], { timeoutMs: 3000 });
    if (result.ok) {
      const first = result.stdout.split(/\r?\n/).map((item) => item.trim()).find(Boolean);
      if (first) return first;
    }
  }
  return null;
}

function isWithin(root, candidate) {
  const rel = relative(resolve(root), resolve(candidate));
  return rel === '' || (!rel.startsWith('..') && !isAbsolute(rel));
}

async function locateDependency({ names, bundled = [], candidates = [] }, locate, run, env) {
  const runtimeRoot = env.DSH_RUNTIME_ROOT ? resolve(env.DSH_RUNTIME_ROOT) : null;
  if (runtimeRoot) {
    for (const item of bundled) {
      const candidate = resolve(runtimeRoot, item);
      if (isWithin(runtimeRoot, candidate) && await executable(candidate)) {
        return { path: candidate, source: 'bundled' };
      }
    }
  }
  if (env.DSH_PORTABLE_STRICT === '1') return { path: null, source: null };
  const path = await locate(names, candidates, run);
  return { path, source: path ? 'system' : null };
}

function firstVersionLine(result) {
  return `${result.stdout}\n${result.stderr}`.split(/\r?\n/).map((line) => line.trim()).find(Boolean)?.slice(0, 240) ?? null;
}

export class PreflightService {
  constructor({ locate = locateExecutable, run = runReadonlyProcess, env = process.env } = {}) {
    this.locate = locate;
    this.runProcess = run;
    this.env = env;
  }

  async #command(definition) {
    const located = await locateDependency(definition, this.locate, this.runProcess, this.env);
    const { path, source } = located;
    if (!path) return { id: definition.id, label: definition.label, status: 'missing', path: null, version: null, guidance: definition.guidance };
    const result = await this.runProcess(path, definition.args, { timeoutMs: 8000 });
    return {
      id: definition.id,
      label: definition.label,
      status: result.ok ? 'available' : 'degraded',
      path,
      source,
      version: firstVersionLine(result),
      guidance: result.ok ? null : `${definition.label} 已发现，但版本探测失败；请在终端手动运行其 --version 检查。`,
    };
  }

  async run() {
    const pythonLocated = await locateDependency(
      { names: ['python', 'python3'], bundled: ['python/python.exe'], candidates: PYTHON_CANDIDATES },
      this.locate,
      this.runProcess,
      this.env,
    );
    const pythonPath = pythonLocated.path;
    const python = pythonPath
      ? await this.runProcess(pythonPath, ['--version'], { timeoutMs: 5000 })
      : null;
    const items = [{
      id: 'python',
      label: 'Python',
      status: python?.ok ? 'available' : pythonPath ? 'degraded' : 'missing',
      path: pythonPath,
      source: pythonLocated.source,
      version: python ? firstVersionLine(python) : null,
      guidance: python?.ok ? null : '安装 Python 3.11+，或在卡片中选择已有解释器路径。',
    }];

    for (const [moduleName, label] of PYTHON_PACKAGES) {
      if (!pythonPath) {
        items.push({ id: moduleName, label, status: 'missing', path: null, version: null, guidance: `先配置 Python，再安装 ${moduleName}。` });
        continue;
      }
      const result = await this.runProcess(
        pythonPath,
        ['-c', `import ${moduleName} as m; print(getattr(m, '__version__', 'available'))`],
        { timeoutMs: 8000 },
      );
      items.push({
        id: moduleName,
        label,
        status: result.ok ? 'available' : 'missing',
        path: pythonPath,
        source: pythonLocated.source,
        version: result.ok ? firstVersionLine(result) : null,
        guidance: result.ok ? null : `在当前解释器中安装 ${moduleName}；插件不会自动安装。`,
      });
    }

    items.push(...await Promise.all(COMMANDS.map((definition) => this.#command(definition))));
    return {
      schema: 'dsh.mathmodel.preflight/v1',
      status: items.every((item) => item.status === 'available') ? 'ready' : 'attention',
      checkedAt: new Date().toISOString(),
      readonly: true,
      portableStrict: this.env.DSH_PORTABLE_STRICT === '1',
      items,
    };
  }
}
