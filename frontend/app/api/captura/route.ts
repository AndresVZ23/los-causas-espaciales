// Solo en desarrollo (npm run dev): recibe un video grabado en el navegador con canvas.captureStream y lo guarda en
// videos/captura/<nombre>.webm, para montar el tráiler con imágenes reales del juego (ADR-050). Fuera de desarrollo
// responde 404. videos/ está ignorado por Git.
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  if (process.env.NODE_ENV !== "development") return new Response("No disponible", { status: 404 });
  const name = (new URL(request.url).searchParams.get("nombre") ?? "").replace(/[^a-z0-9_-]/gi, "").slice(0, 40);
  if (!name) return new Response("Falta el nombre", { status: 400 });
  const folder = path.join(process.cwd(), "..", "videos", "captura");
  await mkdir(folder, { recursive: true });
  const body = Buffer.from(await request.arrayBuffer());
  await writeFile(path.join(folder, `${name}.webm`), body);
  return Response.json({ ok: true, bytes: body.length });
}
