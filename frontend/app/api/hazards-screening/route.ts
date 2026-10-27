import { NextResponse } from "next/server";

const BACKEND_API = process.env.BACKEND_API_URL || "http://localhost:8000";

// Módulo 3 · amenazas naturales: lluvia y extremos con contrastes IMERG y CHIRPS, relieve, capas de riesgo y deslizamientos de NASA.
export async function POST(request: Request) {
  try {
    const body = await request.text();
    const response = await fetch(`${BACKEND_API}/api/v1/projects/hazards-screening`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
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
