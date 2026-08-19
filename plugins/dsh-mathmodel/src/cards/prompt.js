import { REQUEST_SCHEMA } from './schema.js';

function validateValue(field, value) {
  if (value === undefined || value === null || value === '') {
    if (field.required) throw new TypeError(`${field.label} 为必填项`);
    return value;
  }
  if (field.type === 'boolean' && typeof value !== 'boolean') throw new TypeError(`${field.label} 必须是布尔值`);
  if (field.type === 'number') {
    if (typeof value !== 'number' || !Number.isFinite(value)) throw new TypeError(`${field.label} 必须是有限数字`);
    if (field.min !== undefined && value < field.min) throw new TypeError(`${field.label} 不能小于 ${field.min}`);
    if (field.max !== undefined && value > field.max) throw new TypeError(`${field.label} 不能大于 ${field.max}`);
  }
  if (['text', 'path', 'credential-status', 'select'].includes(field.type) && typeof value !== 'string') throw new TypeError(`${field.label} 必须是字符串`);
  if (field.type === 'select' && !field.options.includes(value)) throw new TypeError(`${field.label} 的值不在允许范围`);
  if (field.type === 'multiselect' && (!Array.isArray(value) || value.some((item) => !field.options.includes(item)))) {
    throw new TypeError(`${field.label} 含不允许的选项`);
  }
  return value;
}

export function renderCardPrompt(card, submitted = {}) {
  if (submitted === null || typeof submitted !== 'object' || Array.isArray(submitted)) throw new TypeError('卡片提交值必须是对象');
  const known = new Set(card.fields.map((field) => field.id));
  for (const key of Object.keys(submitted)) {
    if (!known.has(key)) throw new TypeError(`提交包含未知字段 ${key}`);
  }
  const values = {};
  for (const field of card.fields) {
    const value = submitted[field.id] ?? field.default;
    const checked = validateValue(field, value);
    if (checked !== undefined && checked !== '') values[field.id] = checked;
  }
  const userNotes = typeof values.user_notes === 'string' ? values.user_notes : '';
  delete values.user_notes;
  const request = {
    schema: REQUEST_SCHEMA,
    skill: card.skill,
    objective: card.prompt.objective,
    options: values,
    userNotes,
  };
  const policyInstruction = values.bar_policy === '禁用'
    ? '柱状图策略为“禁用”：零例外禁止 bar/Bar、barh、broken_barh、barplot、mark_bar、vbar、hbar 及 kind="bar/barh"；时间区间改用线段与端点标记，门禁必须扫描真实源码。'
    : values.bar_policy === '少用'
      ? '柱状图策略为“少用”：仅在 manifest 同源条目具有完整 bar_exception 时允许柱形图。'
      : '';
  // run_to_pdf 卡片把 Goal 激活指令提升到用户消息正文首条，避免依赖模型自觉读取 Skill 文档导致概率不触发。
  // Goal 存续期间三条铁规：静默收尾（仅“…”）、门禁单回合闭环修复、禁用 Goal 写工具（续轮调用必被 harness 拒绝）。
  const goalInstruction = values.run_to_pdf === true
    ? '首轮动作：先调用 get_goal；当前会话无 Goal 立即调用 create_goal，objective 固定为“持续完成本数学建模论文项目并交付通过全部门禁的最终 PDF”；已有同目标 Goal 直接继续推进，禁止覆盖无关 Goal。Goal 存续期间铁规：(1) 禁止调用 update_goal 等 Goal 写工具，续轮调用必然被 harness 拒绝，Goal 由 harness 自动续期；(2) 每回合收尾仅输出“…”，禁止中期报告、总结或进展说明，阶段状态只写入项目文件留痕；(3) 门禁退出码非 0 时，先完整读取该阶段 failures_summary.json 清单，同一回合内修复全部失败项再重跑，直至退出码为 0 才允许收尾；(4) 仅两种情况允许输出完整文本：verify_delivery.py 输出 ok: true 后的唯一一次交付报告（此后续轮仅回“…”），或触发数据缺失/矛盾强制报告条款时的阻塞报告'
    : '';
  const instructions = [
    ...(goalInstruction ? [goalInstruction] : []),
    ...card.prompt.instructions,
    ...(policyInstruction ? [policyInstruction] : []),
  ];
  return `/${card.skill}\n\n\`\`\`json\n${JSON.stringify(request, null, 2)}\n\`\`\`\n\n执行要求：\n${instructions.map((item) => `- ${item}`).join('\n')}`;
}
