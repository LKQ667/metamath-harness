import { renderCardPrompt } from './prompt.js';

/** Host Remote 的业务内核；DSH Typert 外壳在 Profile 接线阶段挂载。 */
export class MathModelCardsRemote {
  constructor(registry, helpCatalog) {
    this.registry = registry;
    this.helpCatalog = helpCatalog;
  }

  async list() {
    return { schema: 'dsh.mathmodel.cards/v1', cards: await this.registry.list() };
  }

  async help() {
    if (!this.helpCatalog) throw new TypeError('Skill 说明目录尚未配置');
    return { schema: 'dsh.mathmodel.skill-help/v1', skills: await this.helpCatalog.list() };
  }

  async render(skill, values) {
    const card = await this.registry.get(skill);
    if (!card) throw new TypeError(`未知或不可调用的卡片 Skill：${skill}`);
    return { schema: 'dsh.mathmodel.draft/v1', skill, text: renderCardPrompt(card, values) };
  }
}
