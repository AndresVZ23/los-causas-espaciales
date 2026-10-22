import { NextResponse } from "next/server";

const BACKEND_API = process.env.BACKEND_API_URL || "http://localhost:8000";
// Un screening completo pesa decenas de KB; el límite evita reenviar cuerpos arbitrarios al backend.
const MAX_BODY_BYTES = 2_000_000;

export async function POST(request: Request) {
  const body = await request.text();
  if (body.length > MAX_BODY_BYTES) {
    return NextResponse.json({ detail: "El resultado excede el tamaño admitido para el reporte." }, { status: 413 });
  }
  try {
    const response = await fetch(`${BACKEND_API}/api/v1/reports/executive-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
    });
    if (!response.ok) {
      const payload = await response.text();
      return new NextResponse(payload, { status: response.status, headers: { "Content-Type": response.headers.get("content-type") || "application/json" } });
    }
    return new NextResponse(await response.arrayBuffer(), {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": response.headers.get("content-disposition") || 'attachment; filename="reporte-ejecutivo.pdf"',
      },
    });
  } catch {
    return NextResponse.json({ detail: "El frontend no pudo comunicarse con la API para generar el PDF. Verifique FastAPI en el puerto 8000." }, { status: 502 });
  }
}
