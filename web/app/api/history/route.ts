import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:7071'

export async function GET(request: NextRequest) {
  try {
    const sessionId = request.headers.get('X-Session-ID') || ''

    const response = await fetch(`${BACKEND_URL}/api/history`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-ID': sessionId,
      },
    })

    if (!response.ok) {
      return NextResponse.json({ queries: [] })
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('History API error:', error)
    return NextResponse.json({ queries: [] })
  }
}
