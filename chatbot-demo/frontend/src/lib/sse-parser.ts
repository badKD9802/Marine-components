/**
 * SSE 라인 파서 — fetch ReadableStream에서 SSE 이벤트 추출.
 */
export interface SSEEvent {
  event: string
  data: string
}

export async function* parseSSE(
  reader: ReadableStreamDefaultReader<Uint8Array>
): AsyncGenerator<SSEEvent> {
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      // 스트림 종료 시 버퍼에 남은 데이터 처리 (flush)
      buffer += decoder.decode(new Uint8Array(), { stream: false })
      if (buffer.trim()) {
        const lines = buffer.split('\n')
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (currentEvent) {
              yield { event: currentEvent, data }
              currentEvent = ''
            }
          }
        }
      }
      break
    }

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        const data = line.slice(6)
        if (currentEvent) {
          yield { event: currentEvent, data }
          currentEvent = ''
        }
      }
    }
  }
}
