/** Split Qoder wire content into visible text and reasoning while removing tag artifacts. */

export interface QoderContentSegment {
  type: 'text' | 'reasoning'
  text: string
}

const thinkingTags = [
  { open: '<thinking>', close: '</thinking>' },
  { open: '<think>', close: '</think>' },
] as const

const allTags = thinkingTags.flatMap(tag => [tag.open, tag.close])

function trailingPrefixLength(text: string, candidates: readonly string[]): number {
  let best = 0
  for (const candidate of candidates) {
    const limit = Math.min(text.length, candidate.length - 1)
    for (let length = limit; length > best; length--) {
      if (text.endsWith(candidate.slice(0, length))) {
        best = length
        break
      }
    }
  }
  return best
}

function earliestTag(
  text: string,
  kind: 'open' | 'close',
): { position: number; tag: (typeof thinkingTags)[number] } | undefined {
  let found: { position: number; tag: (typeof thinkingTags)[number] } | undefined
  for (const tag of thinkingTags) {
    const position = text.indexOf(tag[kind])
    if (position !== -1 && (found === undefined || position < found.position)) found = { position, tag }
  }
  return found
}

function trimSeparator(text: string): string {
  if (text.startsWith('\n\n')) return text.slice(2)
  if (text.startsWith('\n')) return text.slice(1)
  return text
}

class NativeReasoningStripper {
  private buffer = ''

  push(chunk: string): string {
    this.buffer += chunk
    let output = ''
    while (this.buffer) {
      let firstPosition = -1
      let firstTag = ''
      for (const tag of allTags) {
        const position = this.buffer.indexOf(tag)
        if (position !== -1 && (firstPosition === -1 || position < firstPosition)) {
          firstPosition = position
          firstTag = tag
        }
      }
      if (firstPosition !== -1) {
        output += this.buffer.slice(0, firstPosition)
        this.buffer = this.buffer.slice(firstPosition + firstTag.length)
        continue
      }
      const held = trailingPrefixLength(this.buffer, allTags)
      output += this.buffer.slice(0, this.buffer.length - held)
      this.buffer = this.buffer.slice(this.buffer.length - held)
      break
    }
    return output
  }

  finish(): string {
    const output = allTags.some(tag => tag.startsWith(this.buffer)) ? '' : this.buffer
    this.buffer = ''
    return output
  }
}

export class QoderThinkingParser {
  private buffer = ''
  private mode: 'text' | 'reasoning' = 'text'
  private closingTag: string = thinkingTags[0].close
  private readonly native = new NativeReasoningStripper()

  pushReasoning(chunk: string): QoderContentSegment[] {
    const text = this.native.push(chunk)
    return text ? [{ type: 'reasoning', text }] : []
  }

  pushContent(chunk: string): QoderContentSegment[] {
    const output: QoderContentSegment[] = []
    const pendingReasoning = this.native.finish()
    if (pendingReasoning) output.push({ type: 'reasoning', text: pendingReasoning })
    this.buffer += chunk

    while (this.buffer) {
      if (this.mode === 'reasoning') {
        const closeAt = this.buffer.indexOf(this.closingTag)
        if (closeAt !== -1) {
          if (closeAt > 0) output.push({ type: 'reasoning', text: this.buffer.slice(0, closeAt) })
          this.buffer = trimSeparator(this.buffer.slice(closeAt + this.closingTag.length))
          this.mode = 'text'
          continue
        }
        const held = trailingPrefixLength(this.buffer, [this.closingTag])
        const safeLength = this.buffer.length - held
        if (safeLength > 0) output.push({ type: 'reasoning', text: this.buffer.slice(0, safeLength) })
        this.buffer = this.buffer.slice(safeLength)
        break
      }

      const opener = earliestTag(this.buffer, 'open')
      const closer = earliestTag(this.buffer, 'close')
      if (opener !== undefined && (closer === undefined || opener.position < closer.position)) {
        if (opener.position > 0) output.push({ type: 'text', text: this.buffer.slice(0, opener.position) })
        this.buffer = this.buffer.slice(opener.position + opener.tag.open.length)
        this.closingTag = opener.tag.close
        this.mode = 'reasoning'
        continue
      }
      if (closer !== undefined) {
        if (closer.position > 0) output.push({ type: 'text', text: this.buffer.slice(0, closer.position) })
        this.buffer = trimSeparator(this.buffer.slice(closer.position + closer.tag.close.length))
        continue
      }

      const held = trailingPrefixLength(this.buffer, allTags)
      const safeLength = this.buffer.length - held
      if (safeLength > 0) output.push({ type: 'text', text: this.buffer.slice(0, safeLength) })
      this.buffer = this.buffer.slice(safeLength)
      break
    }
    return output
  }

  finish(): QoderContentSegment[] {
    const output: QoderContentSegment[] = []
    const pendingReasoning = this.native.finish()
    if (pendingReasoning) output.push({ type: 'reasoning', text: pendingReasoning })
    if (this.buffer) output.push({ type: this.mode, text: this.buffer })
    this.buffer = ''
    return output
  }
}
