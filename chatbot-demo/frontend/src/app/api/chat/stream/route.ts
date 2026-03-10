import { NextRequest } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    const backendRes = await fetch(`${BACKEND_URL}/api/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })

    if (!backendRes.ok) {
      return new Response(
        JSON.stringify({ error: `Backend error: ${backendRes.status}` }),
        { status: backendRes.status, headers: { 'Content-Type': 'application/json' } }
      )
    }

    // SSE 스트림을 그대로 프록시
    return new Response(backendRes.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Session-Id': backendRes.headers.get('X-Session-Id') || '',
      },
    })
  } catch (error) {
    console.error('Proxy error:', error)
    return new Response(
      JSON.stringify({ error: 'Failed to connect to backend' }),
      { status: 502, headers: { 'Content-Type': 'application/json' } }
    )
  }
}
