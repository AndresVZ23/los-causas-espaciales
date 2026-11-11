import { NextResponse } from "next/server";

const BACKEND_API = process.env.BACKEND_API_URL || "http://localhost:8000";

export async function GET(request: Request) {
  const query = (new URL(request.url).searchParams.get("q") ?? "").trim().slice(0, 80);
  if (query.length < 2) return NextResponse.json({ detail: "Escriba al menos dos letras." }, { status: 422 });
  try {
    const response = await fetch(`${BACKEND_API}/api/v1/world/places?q=${encodeURIComponent(query)}`, { cache: "no-store", signal: AbortSignal.timeout(40_000) });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json" } });
  } catch {
    return NextResponse.json({ detail: "El buscador de lugares no respondió." }, { status: 502 });
  }
}
