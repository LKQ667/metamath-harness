/**
 * Qoder protocol wire types and definitions.
 *
 * @module dsh-provider-qoder/qoder/transport/wire/wire-types
 */

export interface QoderWireToolCall {
  id: string
  type: 'function'
  function: {
    name: string
    arguments: string
  }
}

export interface QoderWireTool {
  type: 'function'
  function: {
    name: string
    description: string
    parameters: Record<string, unknown>
  }
}

export interface QoderWireTextPart {
  type: 'text'
  text: string
}

export interface QoderWireImagePart {
  type: 'image_url'
  image_url: { url: string }
}

export type QoderWireContent = string | Array<QoderWireTextPart | QoderWireImagePart>

export interface QoderWireMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: QoderWireContent | null
  tool_calls?: QoderWireToolCall[]
  tool_call_id?: string
  reasoning_content?: string
}

export interface QoderModelConfig {
  key: string
  is_reasoning: boolean
  max_output_tokens: number
  source: string
  context_config?: Record<string, { token_count?: number; is_default?: boolean }>
}

export interface QoderChatContext {
  chatPrompt: string
  imageUrls: null | string[]
  extra: {
    context: unknown[]
    modelConfig: {
      key: string
      is_reasoning: boolean
    }
    originalContent: string
  }
  features: unknown[]
  text: string
}

export interface QoderBusiness {
  product: string
  version: string
  type: string
  stage: string
  id: string
  name: string
  begin_at: number
}

export interface QoderWireRequest {
  request_id: string
  request_set_id: string
  chat_record_id: string
  session_id: string
  stream: true
  chat_task: string
  is_reply: boolean
  is_retry: boolean
  source: number
  version: string
  session_type: string
  agent_id: string
  task_id: string
  code_language: string
  chat_prompt: string
  image_urls: null
  aliyun_user_type: string
  system: string
  messages: QoderWireMessage[]
  tools: QoderWireTool[]
  parameters: {
    max_tokens: number
    reasoning_effort?: string
  }
  chat_context: QoderChatContext
  model_config: QoderModelConfig
  business: QoderBusiness
}

export interface QoderSseEnvelope {
  statusCodeValue?: number
  body?: string
}

export interface QoderInnerChunk {
  id?: string
  model?: string
  choices?: Array<{
    index?: number
    delta?: {
      content?: string
      role?: string
      reasoning_content?: string
      tool_calls?: Array<{
        index?: number
        id?: string
        type?: string
        function?: {
          name?: string
          arguments?: string
        }
      }>
    } | null
    finish_reason?: string | null
  }>
  usage?: {
    prompt_tokens?: number
    completion_tokens?: number
    total_tokens?: number
    prompt_tokens_details?: {
      cached_tokens?: number
      cache_write_tokens?: number
    }
    completion_tokens_details?: {
      reasoning_tokens?: number
    }
  }
}
