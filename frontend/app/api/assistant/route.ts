import { NextResponse } from "next/server";

const BACKEND_API = process.env.BACKEND_API_URL || "http://localhost:8000";
const MAX_BODY_BYTES = 3_000_000;

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_API}/api/v1/assistant/status`, { cache: "no-store", signal: AbortSignal.timeout(5_000) });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json" } });
  } catch {
    return NextResponse.json({ gemini_available: false });
  }
}

export async function POST(request: Request) {
  const body = await request.text();
  if (body.length > MAX_BODY_BYTES) return NextResponse.json({ detail: "El análisis es demasiado grande para el asistente." }, { status: 413 });
  try {
    const response = await fetch(`${BACKEND_API}/api/v1/assistant/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(45_000),
    });
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") || "application/json" },
    });
  } catch {
    return NextResponse.json({ detail: "El frontend no pudo comunicarse con la API. Verifique que FastAPI esté disponible en el puerto 8000." }, { status: 502 });
  }
}
