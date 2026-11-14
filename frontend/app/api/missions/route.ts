import { NextResponse } from "next/server";

const BACKEND_API = process.env.BACKEND_API_URL || "http://localhost:8000";

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_API}/api/v1/world/missions`, { cache: "no-store", signal: AbortSignal.timeout(20_000) });
    // Mismo criterio que el terreno: un error del backend (503 si las misiones no están construidas) nunca se guarda.
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (!response.ok) headers["Cache-Control"] = "no-store";
    return new NextResponse(await response.text(), { status: response.status, headers });
  } catch {
    return NextResponse.json({ detail: "No se pudo leer la lista de misiones." }, { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
