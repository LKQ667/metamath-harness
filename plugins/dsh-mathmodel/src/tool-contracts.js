export const VISION_ANALYZE_TOOL = Object.freeze({
  name: 'vision_analyze',
  description: '分析当前工作区内的本地图片或 HTTPS 图片 URL，优先使用 qwen3.7-plus，失败时自动回退。',
  parameters: Object.freeze({
    type: 'object',
    additionalProperties: false,
    required: ['image'],
    properties: {
      image: { type: 'string', minLength: 1, description: '工作区相对图片路径或 HTTPS URL' },
      prompt: { type: 'string', description: '希望从图片中提取的信息' },
    },
  }),
});

export const IMAGE_GENERATE_TOOL = Object.freeze({
  name: 'image_generate',
  description: '经用户付费授权后使用设置页当前生图连接生成 1–4 张图片并立即保存到当前工作区；失败时返回 ai-draw-skills 提示词回退。',
  parameters: Object.freeze({
    type: 'object',
    additionalProperties: false,
    required: ['prompt', 'authorizePaid'],
    properties: {
      prompt: { type: 'string', minLength: 1 },
      connectionId: { type: 'string', minLength: 8, maxLength: 64, description: '可选；明确指定已验证的生图连接，留空使用当前连接' },
      provider: { type: 'string', enum: ['dashscope', 'openai', 'gemini', 'custom'], description: '旧版兼容参数；多条连接时请改用 connectionId' },
      referenceImages: { type: 'array', maxItems: 4, items: { type: 'string', minLength: 1 } },
      aspectRatio: { type: 'string' },
      size: { type: 'string' },
      count: { type: 'integer', minimum: 1, maximum: 4, default: 1 },
      outputDir: { type: 'string', default: '.' },
      authorizePaid: { type: 'boolean', description: '必须来自用户本次明确授权' },
      budgetRemaining: { type: 'integer', minimum: 0 },
    },
  }),
});

export function createToolExecutors({ vision, image, workspace }) {
  return Object.freeze({
    vision_analyze: async (args, signal) => await vision.analyze({ ...args, workspace, signal }),
    image_generate: async (args, signal) => await image.generate(args, { workspace, signal }),
  });
}
