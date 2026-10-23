import { NextResponse } from "next/server";

const BACKEND_API = process.env.BACKEND_API_URL || "http://localhost:8000";

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_API}/api/v1/map/layers`, { cache: "no-store", signal: AbortSignal.timeout(70_000) });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json" } });
  } catch {
    return NextResponse.json({ detail: "No se pudo leer el catálogo de capas." }, { status: 502 });
  }
}
