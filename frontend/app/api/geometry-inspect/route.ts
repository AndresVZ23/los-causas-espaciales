import { NextResponse } from "next/server";

const BACKEND_API = process.env.BACKEND_API_URL || "http://localhost:8000";
const MAX_BODY_BYTES = 2_500_000;

export async function POST(request: Request) {
  const body = await request.text();
  if (body.length > MAX_BODY_BYTES) {
    return NextResponse.json({ detail: "La geometría supera el tamaño máximo admitido (2 MB)." }, { status: 413 });
  }
  try {
    const response = await fetch(`${BACKEND_API}/api/v1/geospatial/inspect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });
    const payload = await response.text();
    return new NextResponse(payload, {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") || "application/json" },
    });
  } catch {
    return NextResponse.json(
      { detail: "El frontend no pudo comunicarse con la API. Verifique que FastAPI esté disponible en el puerto 8000." },
      { status: 502 },
    );
  }
}
