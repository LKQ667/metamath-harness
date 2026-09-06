export interface TraeObservedModelConfig {
  configName: string
  modelName: string
  promptSet?: string
  abVersion?: string
  rawChatFunction?: string
}

/**
 * Parse a secret-free CustomModel debug line emitted by Trae. Optional values
 * remain absent when Trae prints None; we must not invent defaults for them.
 */
export function parseObservedModelConfig(line: string): TraeObservedModelConfig | undefined {
  const match = /model_info: CustomModel \{([\s\S]*?)\}\s*(?:trace_id|$)/.exec(line)
  if (match === null) return undefined
  const body = match[1] ?? ''
  const stringField = (name: string): string | undefined => new RegExp(`${name}: "([^"]+)"`).exec(body)?.[1]
  const optionalField = (name: string): string | undefined => new RegExp(`${name}: Some\\("([^"]+)"\\)`).exec(body)?.[1]
  const configName = stringField('config_name')
  const modelName = stringField('model_name')
  if (configName === undefined || modelName === undefined) return undefined
  const promptSet = optionalField('prompt_set')
  const rawChatFunction = optionalField('raw_chat_function')
  const abVersion = optionalField('ab_versions')
  return {
    configName,
    modelName,
    ...promptSet === undefined ? {} : { promptSet },
    ...rawChatFunction === undefined ? {} : { rawChatFunction },
    ...abVersion === undefined ? {} : { abVersion },
  }
}
