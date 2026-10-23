import { NextResponse } from "next/server";

const BACKEND_API = process.env.BACKEND_API_URL || "http://localhost:8000";
// Solo las tres rutas de lectura del catálogo territorial: búsqueda, jerarquía y geometría por ubigeo.
const ALLOWED = [/^search$/, /^hierarchy$/, /^(department|province|district)\/\d{2,6}\/geometry$/];

export async function GET(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const path = (await params).path.join("/");
  if (!ALLOWED.some((pattern) => pattern.test(path))) return NextResponse.json({ detail: "Ruta territorial no válida." }, { status: 404 });
  const query = new URL(request.url).search;
  try {
    const response = await fetch(`${BACKEND_API}/api/v1/territories/${path}${query}`, { cache: "no-store", signal: AbortSignal.timeout(15_000) });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json" } });
  } catch {
    return NextResponse.json({ detail: "No se pudo consultar el catálogo territorial." }, { status: 502 });
  }
}
