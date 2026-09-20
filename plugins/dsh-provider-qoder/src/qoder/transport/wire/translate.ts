/** Translate provider-neutral DSH messages and tools into Qoder wire values. */

import type { ContentBlock, ImageBlock, Message, ToolResultBlock, ToolSchema } from '@deepseek-ai/dsh-llm'
import type { AttachmentStore, RequestImageAttachment } from '@deepseek-ai/dsh-attachment'
import { QoderLlmError } from '../../errors.ts'
import type { CosyCredentials } from './cosy.ts'
import type {
  QoderWireImagePart,
  QoderWireMessage,
  QoderWireTextPart,
  QoderWireTool,
  QoderWireToolCall,
} from './wire-types.ts'

export type QoderImageAttachments = Pick<AttachmentStore, 'imageLimits' | 'readImageRequest'>

/** Publishes a request image and returns the URL the wire message should carry. */
export interface QoderImageResolver {
  resolveImageUrl(
    image: RequestImageAttachment,
    credentials: CosyCredentials,
    signal?: AbortSignal,
  ): Promise<string>
}

export interface QoderTranslateContext {
  attachments?: QoderImageAttachments
  uploader?: QoderImageResolver
  credentials?: CosyCredentials
  signal?: AbortSignal
}

function unsupported(message: string): QoderLlmError {
  return new QoderLlmError(message, 'UNSUPPORTED_CONTENT')
}

function toolResultText(block: ToolResultBlock): string {
  let text = ''
  for (const nested of block.content) {
    if (nested.type === 'image') continue
    if (nested.type !== 'text') {
      throw unsupported(`Qoder tool results support text only; received nested ${String(nested.type)} content.`)
    }
    text += nested.text
  }
  return text
}

/**
 * Check message shapes without performing any provider I/O.
 *
 * Callers run this before resolving credentials so an invalid request never
 * consumes a Qoder subscription.
 */
export function validateMessageShapes(messages: readonly Message[]): void {
  for (const message of messages) {
    const toolResults = message.content.filter((block): block is ToolResultBlock => block.type === 'tool-result')
    if (toolResults.length > 0) {
      if (message.role !== 'user' || toolResults.length !== message.content.length) {
        throw unsupported('Qoder tool-result messages cannot contain sibling content or use a non-user role.')
      }
      for (const result of toolResults) toolResultText(result)
      continue
    }

    for (const block of message.content) {
      if (block.type === 'text') continue
      if (block.type === 'image') {
        if (message.role !== 'user') throw unsupported('Qoder image content is valid only in user messages.')
        continue
      }
      if (block.type === 'tool-call') {
        if (message.role !== 'assistant') {
          throw unsupported('Qoder tool calls are valid only in assistant messages.')
        }
        continue
      }
      if (block.type === 'reasoning') {
        continue
      }
      throw unsupported(`Qoder transport encountered unsupported block type: ${String((block as ContentBlock).type)}`)
    }
  }
}

/** Reject a batch that exceeds the deployment image policy before any upload work starts. */
function enforceImageLimits(
  images: readonly ImageBlock[],
  attachments: QoderImageAttachments,
): void {
  const limits = attachments.imageLimits
  if (images.length > limits.maxImagesPerMessage) {
    throw unsupported(
      `Qoder accepts at most ${limits.maxImagesPerMessage} images per message; received ${images.length}.`,
    )
  }
  let total = 0
  for (const image of images) total += image.attachment.bytes
  if (total > limits.maxMessageImageBytes) {
    throw unsupported('Qoder message image content exceeds the configured total byte limit.')
  }
}

async function resolveImagePart(
  block: ImageBlock,
  context: QoderTranslateContext,
): Promise<QoderWireImagePart> {
  const { attachments, uploader, credentials, signal } = context
  if (attachments === undefined) {
    throw new QoderLlmError('Qoder image input requires the DSH attachment service.', 'ATTACHMENT')
  }
  let image: RequestImageAttachment
  try {
    const limits = attachments.imageLimits
    image = await attachments.readImageRequest(block.attachment, {
      maxPixels: limits.maxImagePixels,
      maxBytes: limits.maxImageBytes,
    }, signal)
  } catch (error) {
    if (signal?.aborted) throw new QoderLlmError('Qoder image preparation was aborted.', 'ABORTED', { cause: error })
    if (error instanceof QoderLlmError) throw error
    throw new QoderLlmError('Qoder could not prepare an image attachment.', 'ATTACHMENT', { cause: error })
  }

  // Publication degrades to an inline data URL on its own; only a missing
  // uploader or missing credentials skips the center exchange entirely.
  if (uploader !== undefined && credentials !== undefined) {
    const url = await uploader.resolveImageUrl(image, credentials, signal)
    return { type: 'image_url', image_url: { url } }
  }
  return {
    type: 'image_url',
    image_url: { url: `data:${image.mediaType};base64,${Buffer.from(image.data).toString('base64')}` },
  }
}

export function translateTools(tools: readonly ToolSchema[] | undefined): QoderWireTool[] {
  return (tools ?? []).map(tool => ({
    type: 'function',
    function: {
      name: tool.name,
      description: tool.description,
      parameters: tool.parameters,
    },
  }))
}

export async function validateAndTranslateMessages(
  messages: readonly Message[],
  systemPrompt?: string,
  attachments?: QoderImageAttachments,
  signal?: AbortSignal,
  pipeline?: Pick<QoderTranslateContext, 'uploader' | 'credentials'> & { preserveThinking?: boolean },
): Promise<QoderWireMessage[]> {
  validateMessageShapes(messages)
  const context: QoderTranslateContext = {
    attachments,
    signal,
    uploader: pipeline?.uploader,
    credentials: pipeline?.credentials,
  }
  const preserveThinking = pipeline?.preserveThinking ?? true
  const output: QoderWireMessage[] = []

  if (typeof systemPrompt === 'string' && systemPrompt.trim().length > 0) {
    output.push({ role: 'system', content: systemPrompt })
  }

  for (const message of messages) {
    const toolResults = message.content.filter((block): block is ToolResultBlock => block.type === 'tool-result')
    if (toolResults.length > 0) {
      if (message.role !== 'user' || toolResults.length !== message.content.length) {
        throw unsupported('Qoder tool-result messages cannot contain sibling content or use a non-user role.')
      }
      for (const result of toolResults) {
        output.push({
          role: 'tool',
          tool_call_id: String(result.toolCallId),
          content: toolResultText(result),
        })
        const images = result.content.filter((block): block is ImageBlock => block.type === 'image')
        if (images.length > 0) {
          if (attachments !== undefined) enforceImageLimits(images, attachments)
          output.push({
            role: 'user',
            content: [
              {
                type: 'text',
                text: `[${images.length} image${images.length === 1 ? '' : 's'} returned by the previous tool call]`,
              },
              ...await Promise.all(images.map(image => resolveImagePart(image, context))),
            ],
          })
        }
      }
      continue
    }

    let text = ''
    let reasoningText = ''
    const userContent: Array<QoderWireTextPart | QoderWireImagePart | undefined> = []
    const pendingImages: Array<{ slot: number; block: ImageBlock }> = []
    let hasImage = false
    const toolCalls: QoderWireToolCall[] = []
    for (const block of message.content) {
      if (block.type === 'text') {
        text += block.text
        if (message.role === 'user') userContent.push({ type: 'text', text: block.text })
        continue
      }
      if (block.type === 'image') {
        hasImage = true
        // Reserve the slot now so publication can proceed concurrently
        // without disturbing the author's content order.
        pendingImages.push({ slot: userContent.length, block })
        userContent.push(undefined)
        continue
      }
      if (block.type === 'tool-call') {
        toolCalls.push({
          id: String(block.id),
          type: 'function',
          function: { name: block.name, arguments: block.arguments },
        })
        continue
      }
      if (block.type === 'reasoning') {
        if (message.role === 'assistant') reasoningText += block.text
        continue
      }
    }

    if (message.role === 'assistant') {
      const hasReasoning = preserveThinking && reasoningText.length > 0
      if (!text && toolCalls.length === 0 && !hasReasoning) continue
      output.push({
        role: 'assistant',
        content: text || ' ',
        ...toolCalls.length === 0 ? {} : { tool_calls: toolCalls },
        ...hasReasoning ? { reasoning_content: reasoningText } : {},
      })
      continue
    }

    if (pendingImages.length > 0) {
      if (attachments !== undefined) {
        enforceImageLimits(pendingImages.map(pending => pending.block), attachments)
      }
      await Promise.all(pendingImages.map(async (pending) => {
        userContent[pending.slot] = await resolveImagePart(pending.block, context)
      }))
    }
    output.push({
      role: message.role,
      content: hasImage
        ? userContent.filter((part): part is QoderWireTextPart | QoderWireImagePart => part !== undefined)
        : text,
    })
  }

  return output
}
