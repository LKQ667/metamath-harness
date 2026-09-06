import { mkdir, rename, rm, stat, writeFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { basename, join } from 'node:path';

const MAX_FILES = 256;
const MAX_FILE_BYTES = 64 * 1024 * 1024;
const MAX_TOTAL_BYTES = 192 * 1024 * 1024;
const MAX_CONFIG_BYTES = 1024 * 1024;
const CONFIG_RE = /^(.+)-config\.(json|jsonc)$/;

export interface PetPackUploadFile {
  path: string;
  data: string;
}

export interface PetPackUploadPayload {
  files?: PetPackUploadFile[];
}

export interface PetPackImportOptions {
  petDir: string;
  existingPetIds: ReadonlySet<string>;
}

export interface PetPackImportResult {
  prefix: string;
  petCount: number;
  animationCount: number;
}

const importErrorStatuses = new WeakMap<PetPackImportError, number>();

export class PetPackImportError extends Error {
  constructor(message: string, status = 400) {
    super(message);
    importErrorStatuses.set(this, status);
  }

  get status(): number {
    return importErrorStatuses.get(this) ?? 400;
  }
}

function stripJsonc(text: string): string {
  let out = '';
  let inString = false;
  let escaped = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];
    if (inString) {
      out += ch;
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === '"') inString = false;
      continue;
    }
    if (ch === '"') {
      inString = true;
      out += ch;
    } else if (ch === '/' && next === '/') {
      i += 2;
      while (i < text.length && text[i] !== '\n' && text[i] !== '\r') i++;
      i--;
    } else if (ch === '/' && next === '*') {
      const end = text.indexOf('*/', i + 2);
      if (end < 0) throw new PetPackImportError('配置文件的块注释未闭合');
      i = end + 1;
    } else {
      out += ch;
    }
  }
  return out;
}

function safeSegment(segment: string): boolean {
  const hasControlCharacter = [...segment].some((character) => character.charCodeAt(0) <= 0x1f);
  return (
    segment.length > 0 &&
    segment.length <= 120 &&
    segment !== '.' &&
    segment !== '..' &&
    !segment.startsWith('.') &&
    !/[<>:"/\\|?*]/.test(segment) &&
    !hasControlCharacter
  );
}

function normalizeUploadPaths(files: PetPackUploadFile[]): Array<PetPackUploadFile & { parts: string[] }> {
  const parsed = files.map((file) => {
    if (!file || typeof file.path !== 'string' || typeof file.data !== 'string') {
      throw new PetPackImportError('上传文件条目无效');
    }
    if (file.path.startsWith('/') || /^[A-Za-z]:/.test(file.path) || file.path.includes('\\')) {
      throw new PetPackImportError('上传路径必须是文件夹内的相对路径');
    }
    const parts = file.path.split('/');
    if (parts.length < 1 || parts.some((part) => !safeSegment(part))) {
      throw new PetPackImportError('上传路径包含非法文件名或路径段');
    }
    return { ...file, parts };
  });
  const first = parsed[0]?.parts[0];
  const hasCommonPickerRoot = !!first && parsed.every((file) => file.parts.length >= 2 && file.parts[0] === first);
  return parsed.map((file) => ({ ...file, parts: hasCommonPickerRoot ? file.parts.slice(1) : file.parts }));
}

function decodeBase64(value: string): Buffer {
  if (value.length === 0 || value.length % 4 !== 0 || !/^[A-Za-z0-9+/]*={0,2}$/.test(value)) {
    throw new PetPackImportError('上传文件内容不是有效的 base64');
  }
  const data = Buffer.from(value, 'base64');
  if (data.length === 0 || data.length > MAX_FILE_BYTES) {
    throw new PetPackImportError(`单个文件必须大于 0 且不超过 ${MAX_FILE_BYTES / 1024 / 1024} MiB`);
  }
  return data;
}

function stringArray(value: unknown, label: string): string[] {
  if (!Array.isArray(value) || !value.every((item) => typeof item === 'string' && item.length > 0)) {
    throw new PetPackImportError(`${label} 必须是字符串数组`);
  }
  return value;
}

function validateConfig(
  configBytes: Buffer,
  existingPetIds: ReadonlySet<string>,
): { petCount: number; referenced: Set<string> } {
  if (configBytes.length > MAX_CONFIG_BYTES) throw new PetPackImportError('配置文件不得超过 1 MiB');
  let config: Record<string, unknown>;
  try {
    const parsed = JSON.parse(stripJsonc(configBytes.toString('utf8'))) as unknown;
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('root');
    config = parsed as Record<string, unknown>;
  } catch (error) {
    if (error instanceof PetPackImportError) throw error;
    throw new PetPackImportError('配置文件不是有效的 JSON/JSONC 对象');
  }

  if (!Array.isArray(config.pets) || config.pets.length === 0) {
    throw new PetPackImportError('配置 pets 必须是非空数组');
  }
  const localIds = new Set<string>();
  for (const pet of config.pets) {
    const id = pet && typeof pet === 'object' ? (pet as Record<string, unknown>).id : undefined;
    if (typeof id !== 'string' || !safeSegment(id)) throw new PetPackImportError('每个 pets[] 必须有安全且非空的 id');
    if (localIds.has(id)) throw new PetPackImportError(`配置内宠物 id 重复：${id}`);
    if (existingPetIds.has(id)) throw new PetPackImportError(`宠物 id 已存在：${id}`, 409);
    localIds.add(id);
  }

  const animations = config.animations;
  if (!animations || typeof animations !== 'object' || Array.isArray(animations)) {
    throw new PetPackImportError('配置 animations 必须是对象');
  }
  const a = animations as Record<string, unknown>;
  const referenced = new Set<string>();
  for (const key of ['idle', 'turn', 'drag', 'clicks']) {
    for (const name of stringArray(a[key], `animations.${key}`)) referenced.add(name);
  }
  const moves = a.moves;
  if (!moves || typeof moves !== 'object' || Array.isArray(moves))
    throw new PetPackImportError('animations.moves 必须是对象');
  const moveRecord = moves as Record<string, unknown>;
  if (!moveRecord.default || typeof moveRecord.default !== 'object' || !Array.isArray(moveRecord.actions)) {
    throw new PetPackImportError('animations.moves.default/actions 不完整');
  }
  for (const action of moveRecord.actions) {
    const name = action && typeof action === 'object' ? (action as Record<string, unknown>).name : undefined;
    if (typeof name !== 'string' || name.length === 0)
      throw new PetPackImportError('animations.moves.actions[].name 无效');
    referenced.add(name);
  }
  if (!Array.isArray(a.categories)) throw new PetPackImportError('animations.categories 必须是数组');
  let categoryWeight = 0;
  for (const category of a.categories) {
    if (!category || typeof category !== 'object') throw new PetPackImportError('animations.categories[] 无效');
    const record = category as Record<string, unknown>;
    if (typeof record.weight !== 'number' || record.weight < 0)
      throw new PetPackImportError('分类 weight 必须是非负数');
    categoryWeight += record.weight;
    for (const name of stringArray(record.actions, 'animations.categories[].actions')) referenced.add(name);
  }
  if (!a.events || typeof a.events !== 'object' || Array.isArray(a.events)) {
    throw new PetPackImportError('animations.events 必须是对象');
  }
  for (const [event, pool] of Object.entries(a.events as Record<string, unknown>)) {
    for (const name of stringArray(pool, `animations.events.${event}`)) referenced.add(name);
  }
  const weights = config.animationWeights;
  if (!weights || typeof weights !== 'object' || Array.isArray(weights)) {
    throw new PetPackImportError('animationWeights 必须是对象');
  }
  const weightRecord = weights as Record<string, unknown>;
  const topWeights = ['idle', 'turn', 'move'].map((key) => weightRecord[key]);
  if (!topWeights.every((value) => typeof value === 'number' && value >= 0)) {
    throw new PetPackImportError('animationWeights 必须包含非负的 idle/turn/move');
  }
  const totalWeight = (topWeights as number[]).reduce((sum, value) => sum + value, 0) + categoryWeight;
  if (Math.abs(totalWeight - 100) > Number.EPSILON) {
    throw new PetPackImportError(`动画权重总和必须为 100，当前为 ${totalWeight}`);
  }
  if (referenced.size === 0) throw new PetPackImportError('配置至少需要引用一个动画');
  for (const name of referenced) {
    if (!safeSegment(name)) throw new PetPackImportError(`动画名不安全：${name}`);
  }
  return { petCount: config.pets.length, referenced };
}

async function pathExists(path: string): Promise<boolean> {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

export async function importPetPack(
  payload: PetPackUploadPayload,
  options: PetPackImportOptions,
): Promise<PetPackImportResult> {
  if (!Array.isArray(payload?.files) || payload.files.length < 2 || payload.files.length > MAX_FILES) {
    throw new PetPackImportError(`宠物包文件数必须在 2 到 ${MAX_FILES} 之间`);
  }
  const files = normalizeUploadPaths(payload.files);
  const configs = files.filter((file) => file.parts.length === 1 && CONFIG_RE.test(file.parts[0]));
  if (configs.length !== 1) throw new PetPackImportError('文件夹根目录必须恰好包含一个 <名称>-config.json 或 .jsonc');
  const configName = configs[0].parts[0];
  const match = CONFIG_RE.exec(configName);
  const prefix = match?.[1] ?? '';
  if (!safeSegment(prefix)) throw new PetPackImportError('宠物包名称包含非法字符');
  const animationDirName = `${prefix}-animation`;
  const animationFiles = files.filter(
    (file) =>
      file.parts.length === 2 && file.parts[0] === animationDirName && file.parts[1].toLowerCase().endsWith('.webm'),
  );
  if (animationFiles.length === 0 || animationFiles.length !== files.length - 1) {
    throw new PetPackImportError(`除配置外只允许 ${animationDirName} 目录中的 .webm 文件`);
  }

  const decoded = new Map<string, Buffer>();
  let totalBytes = 0;
  for (const file of files) {
    const key = file.parts.join('/');
    if (decoded.has(key)) throw new PetPackImportError(`上传路径重复：${key}`);
    const bytes = decodeBase64(file.data);
    totalBytes += bytes.length;
    if (totalBytes > MAX_TOTAL_BYTES) throw new PetPackImportError('宠物包原始文件总大小不得超过 192 MiB');
    decoded.set(key, bytes);
  }
  const configBytes = decoded.get(configName);
  if (!configBytes) throw new PetPackImportError('配置文件内容缺失');
  const { petCount, referenced } = validateConfig(configBytes, options.existingPetIds);
  const available = new Set(animationFiles.map((file) => basename(file.parts[1], '.webm')));
  for (const name of referenced) {
    if (!available.has(name)) throw new PetPackImportError(`配置引用的动画不存在：${name}.webm`);
  }

  await mkdir(options.petDir, { recursive: true });
  const targetConfig = join(options.petDir, configName);
  const targetAnimations = join(options.petDir, animationDirName);
  if ((await pathExists(targetConfig)) || (await pathExists(targetAnimations))) {
    throw new PetPackImportError(`宠物包已存在：${prefix}`, 409);
  }

  const staging = join(options.petDir, `.import-${randomUUID()}`);
  const stagingAnimations = join(staging, animationDirName);
  await mkdir(stagingAnimations, { recursive: true });
  try {
    await writeFile(join(staging, configName), configBytes, { flag: 'wx' });
    for (const file of animationFiles) {
      const bytes = decoded.get(file.parts.join('/'));
      if (!bytes) throw new PetPackImportError(`动画文件内容缺失：${file.parts[1]}`);
      await writeFile(join(stagingAnimations, file.parts[1]), bytes, { flag: 'wx' });
    }
    await rename(stagingAnimations, targetAnimations);
    try {
      await rename(join(staging, configName), targetConfig);
    } catch (error) {
      await rename(targetAnimations, stagingAnimations).catch(() => undefined);
      throw error;
    }
    return { prefix, petCount, animationCount: animationFiles.length };
  } finally {
    await rm(staging, { recursive: true, force: true });
  }
}
