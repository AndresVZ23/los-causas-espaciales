import { NextResponse } from "next/server";

const BACKEND_API = process.env.BACKEND_API_URL || "http://localhost:8000";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[a-z0-9-]{1,40}$/.test(id)) return NextResponse.json({ detail: "Esa zona no existe." }, { status: 404 });
  try {
    const response = await fetch(`${BACKEND_API}/api/v1/world/zones/${id}`, { cache: "no-store", signal: AbortSignal.timeout(30_000) });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json" } });
  } catch {
    return NextResponse.json({ detail: "No se pudo leer la maqueta de la zona." }, { status: 502 });
  }
}
