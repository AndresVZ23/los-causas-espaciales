import { NextResponse } from "next/server";

const BACKEND_API = process.env.BACKEND_API_URL || "http://localhost:8000";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[a-z0-9-]{1,40}$/.test(id)) return NextResponse.json({ detail: "Identificador de misión inválido." }, { status: 404 });
  try {
    const response = await fetch(`${BACKEND_API}/api/v1/world/missions/${id}/terrain`, { cache: "no-store", signal: AbortSignal.timeout(20_000) });
    // Solo se guarda un día el terreno que llegó bien. Un 404 o un 5xx del backend (terreno aún no construido, API
    // reiniciando) no se guarda: si no, el navegador seguiría sin terreno 24 horas después de que el problema se arregle.
    const cacheControl = response.ok ? "public, max-age=86400" : "no-store";
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json", "Cache-Control": cacheControl } });
  } catch {
    return NextResponse.json({ detail: "No se pudo leer el terreno de la misión." }, { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
