import { createHash } from 'node:crypto';
import { readFile, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import { parseDocument } from 'yaml';
import { parseAndValidateCard } from './schema.js';

function parseFrontmatter(skillText, source) {
  const match = skillText.match(/^---\s*\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
  if (!match) throw new TypeError(`${source}: 缺少 YAML frontmatter`);
  const doc = parseDocument(match[1], { strict: true, uniqueKeys: true });
  if (doc.errors.length > 0) throw new TypeError(`${source}: ${doc.errors[0].message}`);
  return doc.toJS() ?? {};
}

function isUserInvocable(skillText, source) {
  return parseFrontmatter(skillText, source)['user-invocable'] === true;
}

async function readCandidates(root) {
  const entries = await readdir(root, { withFileTypes: true });
  const candidates = [];
  for (const entry of entries.filter((item) => item.isDirectory()).sort((a, b) => a.name.localeCompare(b.name))) {
    const directory = join(root, entry.name);
    try {
      const [sidecar, skill] = await Promise.all([
        readFile(join(directory, 'mathmodel-card.yml'), 'utf8'),
        readFile(join(directory, 'SKILL.md'), 'utf8'),
      ]);
      candidates.push({ directory, directoryName: entry.name, sidecar, skill });
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
    }
  }
  return candidates;
}

export class CardRegistry {
  #root;
  #fingerprint = null;
  #cards = Object.freeze([]);

  constructor(skillRoot) {
    if (typeof skillRoot !== 'string' || skillRoot.trim() === '') throw new TypeError('skillRoot 必须是非空路径');
    this.#root = skillRoot;
  }

  invalidate() {
    this.#fingerprint = null;
  }

  async list() {
    const candidates = await readCandidates(this.#root);
    const hash = createHash('sha256');
    for (const item of candidates) hash.update(item.directoryName).update('\0').update(item.sidecar).update('\0').update(item.skill).update('\0');
    const fingerprint = hash.digest('hex');
    if (fingerprint === this.#fingerprint) return this.#cards;

    const cards = [];
    for (const item of candidates) {
      if (!isUserInvocable(item.skill, join(item.directory, 'SKILL.md'))) continue;
      const card = parseAndValidateCard(item.sidecar, join(item.directory, 'mathmodel-card.yml'));
      if (card.skill !== item.directoryName) throw new TypeError(`${item.directory}: card.skill 必须与目录名一致`);
      cards.push(card);
    }
    if (new Set(cards.map((card) => card.skill)).size !== cards.length) throw new TypeError('卡片 skill 不能重复');
    this.#cards = Object.freeze(cards);
    this.#fingerprint = fingerprint;
    return this.#cards;
  }

  async get(skill) {
    return (await this.list()).find((card) => card.skill === skill) ?? null;
  }
}

const HELP = Object.freeze({
  abstract: ['国赛摘要撰写', '按国赛一等奖标准撰写单页饱满、零独立公式、没有 AI 味的竞赛摘要，并自带离线质检。', '论文与竞赛', '国赛论文需要写摘要或检查摘要合规时', '符合规范的摘要初稿与质检结果'],
  'academic-search': ['学术论文搜索', '帮你查找论文、作者和引用信息，并整理成可继续使用的文献清单。', '资料与研究', '需要找论文、核对出处或整理参考文献时', '论文清单、元数据或引用信息'],
  'ai-draw-skills': ['科研配图规划', '读懂论文段落，判断该画什么图，并给出清晰的科研配图方案和提示词。', '绘图与展示', '有论文内容但不知道需要配什么图时', '配图建议、提示词和占位说明'],
  'agent-reach': ['全网资料调研', '搜索并汇总互联网上的公开资料、讨论与评价，整理成有出处的调研结论。', '资料与研究', '需要调研话题、搜集资料或了解大家评价时', '带来源链接的调研汇总'],
  'anti-autoresearch': ['论文诚信审查', '检查论文材料里值得核查的异常和证据缺口，只提示风险，不直接判定造假。', '审查与质量', '想检查数据、图片、引用或实验描述是否可疑时', '待核查问题、证据等级和审查报告'],
  'claude-vision-skill': ['图片识别配置', '让 DeepSeek Harness 使用百炼视觉模型读懂截图、图表和照片。', '视觉与工具', '需要识别图片，或首次配置百炼视觉能力时', '图片内容说明或结构化识别结果'],
  'cumcm-single-question': ['国赛单问深研求解', '对竞赛单道小题完成路线探索、建模、真实计算与迭代验证，推荐可行方案。', '思路与建模', '已有题目和预处理结果，需要深入求解某一问时', '求解方案、计算结果、验证记录与图表建议'],
  'domain-modeling': ['概念与边界梳理', '把项目里的核心概念、关系和边界讲清楚，减少团队理解偏差。', '思路与建模', '需求复杂、术语混乱或需要建立统一概念体系时', '领域词汇、关系说明和边界决策'],
  'dsh-preset-creator': ['Agent 模式创作', '在 DeepSeek Harness 里创作新的 Agent 模式（Preset），生成配置并验证组装。', '视觉与工具', '想新建一个自定义模式或元模式时', 'preset.yml、agent.cordis.yml 和组装验证结果'],
  'exploratory-data-analysis': ['探索性数据分析', '对本机 CSV/JSON 等数据文件做有边界的探索分析，审查缺失、泄漏和离群值。', '数据与预处理', '拿到新的数据文件，想先摸清结构与数据质量时', 'EDA 分析报告与数据质量结论'],
  'frontend-design': ['前端界面设计', '按设计规范产出美观、可用的前端界面方案与实现代码。', '视觉与工具', '需要设计或改进网页界面时', '界面方案与前端代码'],
  'grill-ai-review': ['严格评审', '让多名专项评委从不同角度挑问题、打分，并给出优先级明确的改进建议。', '审查与质量', '方案、论文或代码完成一版后，需要严格复查时', '分项评分、关键问题和修改顺序'],
  'grill-me': ['计划拷问', '对你的计划或设计连续追问，找出隐藏假设和薄弱环节。', '思路与建模', '计划成型后、动手前想被严格拷问时', '追问记录与待补决策清单'],
  'grill-with-docs': ['赛题思路启发', '把复杂赛题或材料一步步拆开，只问真正会改变解题路线的关键问题。', '思路与建模', '刚拿到赛题、没有方向或想比较多条建模路线时', '问题拆解、候选路线和压力测试结论'],
  grilling: ['方案压力测试', '通过连续追问找出方案里的隐藏假设、矛盾和薄弱环节。', '思路与建模', '已有初步计划，想在实施前把风险问透时', '风险清单、待补证据和更稳妥的方案'],
  humanizer: ['AI 痕迹定位与自然化', '先找出 AI 味道最浓的段落，再按你的授权做局部、自然的修改。', '写作与润色', '文字太机械、套话太多或结构过度模板化时', '风险段落清单、依据说明和可选修订稿'],
  imagegen: ['图像生成', '调用已配置的生图模型生成图片，并直接显示在当前会话中。', '绘图与展示', '需要真正生成图片而不只是生成提示词时', '工作区图片、生成参数和会话内预览'],
  'image-to-editable-ppt': ['图片转可编辑 PPT', '把截图、扫描页或图片型幻灯片重建为对象级可编辑的 PPTX 文件。', '绘图与展示', '只有图片版 PPT，想要可编辑源文件时', '对象级可编辑的 .pptx 文件'],
  'long-goal': ['长目标托管执行', '把长周期、多步骤任务交给规格驱动的目标模式持续执行并全程留痕。', '视觉与工具', '任务周期长、步骤多，需要持续跟踪推进时', '目标规格、任务状态和验收记录'],
  'math-paper-cn': ['中文数学建模论文', '从赛题和数据开始，持续完成建模、绘图、写作、检查和最终 PDF。', '论文与竞赛', '参加中文数学建模竞赛，需要完整论文工作流时', '可编辑工程、图表、论文源码和 PDF'],
  'math-paper-cn-drawio': ['论文绘图（Draw.io）', '为数学建模论文绘制规范的 Draw.io 流程图与技术路线图。', '绘图与展示', '论文需要流程图、技术路线图等示意图时', '可编辑的 .drawio 源文件与导出图片'],
  'math-paper-huashu': ['华数杯数学建模论文', '使用华数杯专用模板完成建模、绘图、论文写作和交付检查。', '论文与竞赛', '参加华数杯并需要符合比赛模板的完整论文时', '华数杯论文工程、图表和最终 PDF'],
  'math-paper-huawei': ['华为杯数学建模论文', '使用华为杯 GMCMthesis 模板完成建模、绘图、论文写作和交付检查。', '论文与竞赛', '参加华为杯（研究生数模竞赛）并需要符合官方模板的完整论文时', '华为杯论文工程、图表和最终 PDF'],
  'modelviz-skill': ['科研可视化绘图', '用内置模板库把你的 CSV/XLSX 数据绘制成出版级科研图表，只手动触发。', '绘图与展示', '明确点名要用 ModelViz 绘图时', '图表文件、可复现代码与质检报告'],
  'py-nature': ['Nature 风格数据图', '用 Python 把数据绘制成适合数学建模和科研论文的高质量图表。', '绘图与展示', '需要趋势图、敏感性分析、多面板图或空间分布图时', '可复现绘图代码和高清图片'],
  'research-writing-skill': ['论文润色与优化', '优化中文论文的表达、结构和论证，同时保护术语、公式和引用。', '写作与润色', '摘要、引言、方法、结果或讨论需要润色时', '修订稿、修改说明或写作方案'],
  'skill-installer': ['Skill 安装管理', '帮助安装、检查和管理 DeepSeek Harness 专用 Skill。', '视觉与工具', '需要从本地或仓库加入新的 Skill 时', '安装结果、目录说明和维护提示'],
  'yatai-cn': ['亚太杯数学建模论文', '按亚太杯中文赛道要求完成数据治理、建模、绘图和论文交付。', '论文与竞赛', '参加亚太杯中文赛道，需要完整论文工作流时', '亚太杯论文工程、图表和最终论文'],
});

function concise(value, fallback) {
  const text = String(value ?? fallback).replace(/\s+/g, ' ').trim();
  if (text.length <= 88) return text;
  return `${text.slice(0, 87).trimEnd()}…`;
}

export class SkillHelpCatalog {
  #root;

  constructor(skillRoot) {
    if (typeof skillRoot !== 'string' || skillRoot.trim() === '') throw new TypeError('skillRoot 必须是非空路径');
    this.#root = skillRoot;
  }

  async list() {
    const entries = await readdir(this.#root, { withFileTypes: true });
    const skills = [];
    for (const entry of entries.filter((item) => item.isDirectory()).sort((a, b) => a.name.localeCompare(b.name))) {
      const source = join(this.#root, entry.name, 'SKILL.md');
      let text;
      try {
        text = await readFile(source, 'utf8');
      } catch (error) {
        if (error?.code === 'ENOENT') continue;
        throw error;
      }
      let meta;
      try {
        meta = parseFrontmatter(text, source);
      } catch (error) {
        // 单个第三方或新建 Skill 的元数据损坏不应拖垮整个说明目录。
        if (error instanceof TypeError) continue;
        throw error;
      }
      const override = HELP[entry.name];
      skills.push(Object.freeze({
        skill: entry.name,
        title: override?.[0] ?? concise(meta.name, entry.name),
        summary: override?.[1] ?? concise(meta.description, '查看该 Skill 的说明与使用边界。'),
        category: override?.[2] ?? '其他工具',
        useWhen: override?.[3] ?? '需要使用这个 Skill 的专门能力时',
        output: override?.[4] ?? '按 Skill 说明生成的结果',
        manual: meta['disable-model-invocation'] === true,
        userInvocable: meta['user-invocable'] === true,
      }));
    }
    return Object.freeze(skills);
  }
}

export { HELP as SKILL_HELP_OVERRIDES };
