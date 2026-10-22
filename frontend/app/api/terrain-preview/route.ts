import { NextResponse } from "next/server";

const ALLOWED_HOST = "data.lpdaac.earthdatacloud.nasa.gov";
const ALLOWED_PREFIX = "/lp-prod-public/NASADEM_";

export async function GET(request: Request) {
  const value = new URL(request.url).searchParams.get("url");
  if (!value) return NextResponse.json({ detail: "Falta la URL de vista previa." }, { status: 400 });
  let source: URL;
  try {
    source = new URL(value);
  } catch {
    return NextResponse.json({ detail: "URL de vista previa inválida." }, { status: 400 });
  }
  if (source.protocol !== "https:" || source.hostname !== ALLOWED_HOST || !source.pathname.startsWith(ALLOWED_PREFIX)) {
    return NextResponse.json({ detail: "La vista previa no pertenece al repositorio público NASADEM permitido." }, { status: 403 });
  }
  try {
    const response = await fetch(source, { cache: "force-cache" });
    if (!response.ok) return NextResponse.json({ detail: "NASA no devolvió la vista previa solicitada." }, { status: response.status });
    return new NextResponse(response.body, {
      headers: {
        "Content-Type": response.headers.get("content-type")?.startsWith("image/") ? response.headers.get("content-type")! : "image/jpeg",
        "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
      },
    });
  } catch {
    return NextResponse.json({ detail: "No fue posible recuperar la vista previa oficial NASADEM." }, { status: 502 });
  }
}
