import Workspace from "./_components/workspace";

// La dirección pública de la API se lee al atender cada visita, no al compilar: así el pie enlaza la documentación
// correcta también cuando la aplicación corre en puertos temporales (variable API_PUBLIC_URL).
export const dynamic = "force-dynamic";

export default function Home() {
  const api = (process.env.API_PUBLIC_URL || "http://localhost:8000").replace(/\/+$/, "");
  return <Workspace apiDocsUrl={`${api}/docs`} />;
}
