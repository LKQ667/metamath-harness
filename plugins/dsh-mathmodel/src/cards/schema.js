import { parseDocument } from 'yaml';

export const CARD_SCHEMA = 'dsh.mathmodel.card/v1';
export const REQUEST_SCHEMA = 'dsh.mathmodel.request/v1';

const CARD_KEYS = new Set(['schema', 'skill', 'title', 'summary', 'category', 'fields', 'prompt', 'help']);
const FIELD_KEYS = new Set([
  'id', 'label', 'type', 'description', 'required', 'default', 'options', 'min', 'max', 'placeholder',
]);
const PROMPT_KEYS = new Set(['objective', 'instructions']);
const HELP_KEYS = new Set(['purpose', 'inputs', 'outputs', 'limits', 'dependencies']);
const FIELD_TYPES = new Set(['select', 'multiselect', 'number', 'boolean', 'text', 'path', 'credential-status']);

function fail(path, message) {
  throw new TypeError(`卡片 ${path} ${message}`);
}

function objectAt(value, path) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) fail(path, '必须是对象');
  return value;
}

function rejectUnknown(value, allowed, path) {
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) fail(`${path}.${key}`, '是未知字段');
  }
}

function stringAt(value, path, { nonempty = true } = {}) {
  if (typeof value !== 'string' || (nonempty && value.trim() === '')) fail(path, '必须是非空字符串');
  return value;
}

function stringArrayAt(value, path) {
  if (!Array.isArray(value)) fail(path, '必须是字符串数组');
  return value.map((item, index) => stringAt(item, `${path}[${index}]`));
}

function validateOptions(field, path) {
  if (!['select', 'multiselect'].includes(field.type)) {
    if (field.options !== undefined) fail(`${path}.options`, '只允许用于 select 或 multiselect');
    return;
  }
  const options = stringArrayAt(field.options, `${path}.options`);
  if (options.length === 0 || new Set(options).size !== options.length) fail(`${path}.options`, '必须非空且不能重复');
}

function validateDefault(field, path) {
  if (field.default === undefined) return;
  const value = field.default;
  if (field.type === 'boolean' && typeof value !== 'boolean') fail(`${path}.default`, '必须是布尔值');
  if (field.type === 'number' && (typeof value !== 'number' || !Number.isFinite(value))) fail(`${path}.default`, '必须是有限数字');
  if (['text', 'path', 'credential-status', 'select'].includes(field.type) && typeof value !== 'string') fail(`${path}.default`, '必须是字符串');
  if (field.type === 'multiselect' && !Array.isArray(value)) fail(`${path}.default`, '必须是数组');
  if (field.type === 'select' && !field.options.includes(value)) fail(`${path}.default`, '不在 options 中');
  if (field.type === 'multiselect' && value.some((item) => !field.options.includes(item))) fail(`${path}.default`, '含 options 之外的值');
}

function validateField(raw, index) {
  const path = `fields[${index}]`;
  const field = objectAt(raw, path);
  rejectUnknown(field, FIELD_KEYS, path);
  stringAt(field.id, `${path}.id`);
  if (!/^[a-z][a-z0-9_-]*$/.test(field.id)) fail(`${path}.id`, '只能使用小写字母、数字、_ 或 -');
  stringAt(field.label, `${path}.label`);
  stringAt(field.type, `${path}.type`);
  if (!FIELD_TYPES.has(field.type)) fail(`${path}.type`, `不支持类型 ${field.type}`);
  if (field.description !== undefined) stringAt(field.description, `${path}.description`);
  if (field.placeholder !== undefined) stringAt(field.placeholder, `${path}.placeholder`, { nonempty: false });
  if (field.required !== undefined && typeof field.required !== 'boolean') fail(`${path}.required`, '必须是布尔值');
  for (const key of ['min', 'max']) {
    if (field[key] !== undefined && (field.type !== 'number' || typeof field[key] !== 'number' || !Number.isFinite(field[key]))) {
      fail(`${path}.${key}`, '只允许 number 字段使用有限数字');
    }
  }
  if (field.min !== undefined && field.max !== undefined && field.min > field.max) fail(path, 'min 不能大于 max');
  validateOptions(field, path);
  validateDefault(field, path);
  return Object.freeze({ ...field, ...(field.options ? { options: Object.freeze([...field.options]) } : {}) });
}

export function validateCard(raw) {
  const card = objectAt(raw, 'root');
  rejectUnknown(card, CARD_KEYS, 'root');
  if (card.schema !== CARD_SCHEMA) fail('schema', `必须为 ${CARD_SCHEMA}`);
  for (const key of ['skill', 'title', 'summary', 'category']) stringAt(card[key], key);
  if (!/^[a-z0-9][a-z0-9-]*$/.test(card.skill)) fail('skill', '格式无效');
  if (!Array.isArray(card.fields)) fail('fields', '必须是数组');
  const fields = card.fields.map(validateField);
  if (new Set(fields.map((field) => field.id)).size !== fields.length) fail('fields', 'id 不能重复');
  const prompt = objectAt(card.prompt, 'prompt');
  rejectUnknown(prompt, PROMPT_KEYS, 'prompt');
  stringAt(prompt.objective, 'prompt.objective');
  const instructions = stringArrayAt(prompt.instructions, 'prompt.instructions');
  const help = objectAt(card.help, 'help');
  rejectUnknown(help, HELP_KEYS, 'help');
  for (const key of HELP_KEYS) {
    if (key === 'purpose') stringAt(help[key], `help.${key}`);
    else stringArrayAt(help[key], `help.${key}`);
  }
  return Object.freeze({
    ...card,
    fields: Object.freeze(fields),
    prompt: Object.freeze({ ...prompt, instructions: Object.freeze([...instructions]) }),
    help: Object.freeze(Object.fromEntries(Object.entries(help).map(([key, value]) => [key, Array.isArray(value) ? Object.freeze([...value]) : value]))),
  });
}

export function parseAndValidateCard(text, source = 'mathmodel-card.yml') {
  const document = parseDocument(text, { prettyErrors: true, strict: true, uniqueKeys: true });
  if (document.errors.length > 0) throw new TypeError(`${source}: ${document.errors[0].message}`);
  return validateCard(document.toJS({ maxAliasCount: 0 }));
}
