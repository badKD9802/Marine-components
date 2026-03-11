import { NextRequest } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

console.log(`[route.ts] BACKEND_URL = "${BACKEND_URL}" (env: "${process.env.BACKEND_URL ?? 'undefined'}")`)

export async function POST(request: NextRequest) {
  const targetUrl = `${BACKEND_URL}/api/agent/chat`
  console.log(`[route.ts] POST /api/chat/stream → ${targetUrl}`)

  try {
    const body = await request.json()
    console.log(`[route.ts] 요청 body:`, JSON.stringify(body).slice(0, 200))

    const backendRes = await fetch(targetUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    console.log(`[route.ts] 백엔드 응답: ${backendRes.status} ${backendRes.statusText}`)

    if (!backendRes.ok) {
      const errText = await backendRes.text()
      console.error(`[route.ts] 백엔드 에러 본문:`, errText.slice(0, 500))
      return new Response(
        JSON.stringify({ error: `Backend error: ${backendRes.status}`, detail: errText.slice(0, 200) }),
        { status: backendRes.status, headers: { 'Content-Type': 'application/json' } }
      )
    }

    // SSE 스트림을 실시간으로 파이핑 (버퍼링 방지)
    const { readable, writable } = new TransformStream()

    const pipe = async () => {
      const reader = backendRes.body!.getReader()
      const writer = writable.getWriter()
      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          await writer.write(value)
        }
      } finally {
        writer.close()
      }
    }
    pipe()

    return new Response(readable, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
        'X-Session-Id': backendRes.headers.get('X-Session-Id') || '',
      },
    })
  } catch (error) {
    console.error(`[route.ts] Proxy error (target: ${targetUrl}):`, error)
    return new Response(
      JSON.stringify({ error: 'Failed to connect to backend', target: targetUrl }),
      { status: 502, headers: { 'Content-Type': 'application/json' } }
    )
  }
}
