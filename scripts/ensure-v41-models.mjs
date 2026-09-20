#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const [dshRootArg, dshHomeArg] = process.argv.slice(2)
if (!dshRootArg || !dshHomeArg) {
  console.error('[FAIL] 用法：node ensure-v41-models.mjs <dsh-root> <dsh-home>')
  process.exit(1)
}

const dshRoot = path.resolve(dshRootArg)
const dshHome = path.resolve(dshHomeArg)
const dshPackage = path.join(dshRoot, 'package.json')
const requireFromDsh = createRequire(dshPackage)
const YAML = requireFromDsh('yaml')

const model = {
  id: 'deepseek-flash',
  name: 'DeepSeek V4.1 Flash',
  description: 'Fast, efficient, and economical; suited to focused, routine, or parallel tasks. Supports image input.',
  contextWindow: 1_000_000,
  inputModalities: ['text', 'image'],
}

function fail(message) {
  console.error(`[FAIL] ${message}`)
  process.exit(1)
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'))
  } catch (error) {
    fail(`无法读取 JSON：${file}：${error.message}`)
  }
}

function ensureOpenCodeGo() {
  const piRoot = path.join(dshRoot, 'node_modules', '@earendil-works', 'pi-ai')
  const catalogPath = path.join(piRoot, 'dist', 'providers', 'data', 'opencode-go.json')
  const catalog = readJson(catalogPath)
  const models = catalog['openai-completions']
  if (!models || typeof models !== 'object') fail('OpenCode Go 目录缺少 openai-completions')

  if (models['deepseek-flash']) {
    if (models['deepseek-flash'].name !== 'DeepSeek V4.1 Flash') fail('OpenCode Go 已有 deepseek-flash，但元数据不符合预期')
    console.log('[OK] OpenCode Go 已原生收录 DeepSeek V4.1 Flash')
    return
  }

  const version = readJson(path.join(piRoot, 'package.json')).version
  if (version !== '0.84.4') fail(`pi-ai ${version} 未经验证，拒绝写入临时目录补丁`)
  if (!models['deepseek-v4-flash'] || models['deepseek-v4-flash'].provider !== 'opencode-go') {
    fail('OpenCode Go 旧目录语义锚点失配')
  }

  const backup = `${catalogPath}.bak-before-deepseek-v41`
  if (!fs.existsSync(backup)) fs.copyFileSync(catalogPath, backup)
  models['deepseek-flash'] = {
    id: 'deepseek-flash',
    name: 'DeepSeek V4.1 Flash',
    api: 'openai-completions',
    provider: 'opencode-go',
    baseUrl: 'https://opencode.ai/zen/go/v1',
    reasoning: true,
    input: ['text', 'image'],
    cost: { input: 0.15, output: 0.6, cacheRead: 0.003, cacheWrite: 0 },
    compat: {
      supportsStore: false,
      supportsDeveloperRole: false,
      maxTokensField: 'max_tokens',
      requiresReasoningContentOnAssistantMessages: true,
      thinkingFormat: 'deepseek',
    },
    contextWindow: 1_000_000,
    maxTokens: 384_000,
    thinkingLevelMap: { minimal: null, low: 'low', medium: null, high: 'high', max: 'max' },
  }
  fs.writeFileSync(catalogPath, `${JSON.stringify(catalog)}\n`, 'utf8')
  console.log('[OK] OpenCode Go 已自动加入 DeepSeek V4.1 Flash')
}

function deepSeekAlreadyOfficial() {
  const entry = path.join(dshRoot, 'node_modules', '@deepseek-ai', 'dsh-llm-deepseek', 'lib', 'index.js')
  return /id:\s*["']deepseek-flash["']/.test(fs.readFileSync(entry, 'utf8'))
}

function ensureDeepSeekSettings() {
  if (deepSeekAlreadyOfficial()) {
    console.log('[OK] DeepSeek 官方插件已原生收录 DeepSeek V4.1 Flash')
    return
  }

  fs.mkdirSync(dshHome, { recursive: true })
  const settingsPath = path.join(dshHome, 'settings.yaml')
  const source = fs.existsSync(settingsPath) ? fs.readFileSync(settingsPath, 'utf8') : ''
  const document = source ? YAML.parseDocument(source) : new YAML.Document()
  if (document.errors.length) fail(`settings.yaml 无法解析：${document.errors[0].message}`)

  const existing = document.getIn(['llm-deepseek', 'models'], true)
  const models = existing?.toJSON?.() ?? []
  if (!Array.isArray(models)) fail('settings.yaml 中 llm-deepseek.models 不是数组')
  const current = models.find((item) => item?.id === model.id)
  if (current) {
    if (current.name !== model.name) fail('settings.yaml 已有 deepseek-flash，但名称不是 DeepSeek V4.1 Flash')
    console.log('[OK] DeepSeek 官方渠道已配置 DeepSeek V4.1 Flash')
    return
  }

  models.unshift(model)
  document.setIn(['llm-deepseek', 'models'], models)
  fs.writeFileSync(settingsPath, document.toString({ lineWidth: 0 }), 'utf8')
  console.log('[OK] DeepSeek 官方渠道已自动加入 DeepSeek V4.1 Flash')
}

ensureOpenCodeGo()
ensureDeepSeekSettings()
