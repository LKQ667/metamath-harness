import { readFile } from 'node:fs/promises';
import { basename, extname, relative } from 'node:path';

export const name = 'dsh-mathmodel-tools';
export const inject = ['tools', 'mathmodelRuntime', 'attachments'];

const jsonOutput = {
  schema: { type: 'object', additionalProperties: true },
  render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
};

const IMAGE_MIME = Object.freeze({
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
});

export const imageOutput = {
  schema: { type: 'object', additionalProperties: true },
  render: (_args, value) => [{
    type: 'text',
    text: value?.ok === true
      ? JSON.stringify({
        ok: true,
        provider: value.provider,
        model: value.model,
        count: value.attachments?.length ?? value.files?.length ?? 0,
        files: value.displayFiles ?? [],
      }, null, 2)
      : JSON.stringify(value, null, 2),
  }],
  presentationMeta: (_args, value) => ({
    schema: 'dsh.mathmodel.image-presentation/v1',
    images: value?.ok === true && Array.isArray(value.attachments) ? value.attachments : [],
  }),
};

export async function attachGeneratedImages(result, { attachments, workspace }) {
  if (result?.ok !== true) return result;
  const refs = [];
  for (const file of result.files ?? []) {
    const mediaType = IMAGE_MIME[extname(file).toLowerCase()];
    if (!mediaType) throw new TypeError(`生成文件格式不受附件存储支持：${basename(file)}`);
    refs.push(await attachments.saveImage({
      data: await readFile(file),
      mediaType,
      name: basename(file),
    }));
  }
  return {
    ...result,
    displayFiles: (result.files ?? []).map((file) => relative(workspace, file)),
    attachments: refs,
  };
}

export function presentImageResult(_args, result) {
  const meta = result?.meta;
  if (result?.isError || meta?.schema !== 'dsh.mathmodel.image-presentation/v1' || !Array.isArray(meta.images) || meta.images.length === 0) {
    return undefined;
  }
  return {
    card: 'generic',
    title: `已生成 ${meta.images.length} 张图片`,
    content: [
      ...result.content,
      ...meta.images.map((attachment) => ({ type: 'image', attachment })),
    ],
  };
}

export function workspaceOf(exec) {
  const cwd = exec.agent?.session?.header?.cwd;
  if (typeof cwd !== 'string' || cwd === '') throw new Error('mathmodel 工具需要绑定带工作区的 Agent 会话');
  return cwd;
}

export function apply(ctx) {
  ctx.tools.register({
    name: 'vision_analyze',
    description: '分析工作区内的本地图片或 HTTPS 图片 URL；主模型失败时自动回退，结果不含凭据。',
    parameters: {
      type: 'object',
      additionalProperties: false,
      required: ['image'],
      properties: {
        image: { type: 'string', minLength: 1, description: '工作区相对图片路径或 HTTPS URL' },
        prompt: { type: 'string', description: '希望提取的信息' },
      },
    },
    output: jsonOutput,
    timeoutMs: 120000,
    async execute(args, exec) {
      return await ctx.mathmodelRuntime.vision.analyze({ ...args, workspace: workspaceOf(exec), signal: exec.signal });
    },
  });
  ctx.tools.register({
    name: 'image_generate',
    description: '经用户本次明确付费授权后使用当前生图连接生成 1–4 张图片并保存到工作区；失败时返回提示词回退。',
    parameters: {
      type: 'object',
      additionalProperties: false,
      required: ['prompt', 'authorizePaid'],
      properties: {
        prompt: { type: 'string', minLength: 1 },
        connectionId: { type: 'string', minLength: 8, maxLength: 64, description: '可选；明确指定已验证连接，留空使用当前连接' },
        provider: { type: 'string', enum: ['dashscope', 'openai', 'gemini', 'custom'], description: '旧版兼容参数；多条连接请使用 connectionId' },
        referenceImages: { type: 'array', maxItems: 4, items: { type: 'string', minLength: 1 } },
        aspectRatio: { type: 'string' },
        size: { type: 'string' },
        count: { type: 'integer', minimum: 1, maximum: 4 },
        outputDir: { type: 'string' },
        authorizePaid: { type: 'boolean', description: '必须来自用户本次明确授权' },
        budgetRemaining: { type: 'integer', minimum: 0 },
      },
    },
    output: imageOutput,
    timeoutMs: 300000,
    async execute(args, exec) {
      const workspace = workspaceOf(exec);
      const result = await ctx.mathmodelRuntime.image.generate(args, { workspace, signal: exec.signal });
      return await attachGeneratedImages(result, { attachments: ctx.attachments, workspace });
    },
    presentCall: (args) => ({
      card: 'generic',
      title: '正在生成图片',
      kind: 'execute',
      rawInput: { connection: args?.connectionId ?? args?.provider ?? '当前连接', count: args?.count ?? 1, aspectRatio: args?.aspectRatio ?? '默认' },
    }),
    presentResult: presentImageResult,
  });
  ctx.tools.register({
    name: 'editable_ppt_image',
    description: '图片转可编辑 PPT 专用生图：status 读取并锁定当前生图连接（非敏感）；generate/edit 必须显式携带锁定的 connectionId，单次一张、确定性输出、失败即页面失败，禁止 Codex 与任何回退。',
    parameters: {
      type: 'object',
      additionalProperties: false,
      required: ['action'],
      properties: {
        action: { type: 'string', enum: ['status', 'generate', 'edit'] },
        connectionId: { type: 'string', minLength: 8, maxLength: 64, description: 'generate/edit 必填：status 返回并锁定的连接 ID' },
        prompt: { type: 'string', minLength: 1 },
        referenceImages: { type: 'array', minItems: 1, maxItems: 4, items: { type: 'string', minLength: 1 } },
        maskImage: { type: 'string', minLength: 1 },
        size: { type: 'string', enum: ['auto', '1024x1024', '1536x1024', '1024x1536'] },
        quality: { type: 'string', enum: ['auto', 'low', 'medium', 'high'] },
        outputPath: { type: 'string', minLength: 1 },
        authorizePaid: { type: 'boolean' },
        budgetRemaining: { type: 'integer', minimum: 0 },
      },
    },
    output: jsonOutput,
    timeoutMs: 300000,
    async execute(args, exec) {
      return await ctx.mathmodelRuntime.image.editablePptImage(args, { workspace: workspaceOf(exec), signal: exec.signal });
    },
    presentCall: (args) => ({
      card: 'generic',
      title: args?.action === 'status' ? '读取当前生图连接' : '可编辑 PPT 生图',
      kind: 'execute',
      rawInput: { action: args?.action ?? 'status', connection: args?.connectionId ?? '当前连接' },
    }),
  });
}
