import type { Metadata } from "next";
import Workspace from "../_components/workspace";

export const metadata: Metadata = {
  title: "Plataforma · Los Causas Espaciales",
  description: "Inteligencia terrestre trazable para decisiones de inversión: clima, energía, amenazas, ambiente, territorio, infraestructura e inversión.",
};

// La dirección pública de la API se lee al atender cada visita, no al compilar: así el pie enlaza la documentación
// correcta también cuando la aplicación corre en puertos temporales (variable API_PUBLIC_URL).
export const dynamic = "force-dynamic";

/** La consola técnica de la plataforma. Desde ADR-050 la portada («/») es el juego TERRA 2045. */
export default function PlataformaPage() {
  const api = (process.env.API_PUBLIC_URL || "http://localhost:8000").replace(/\/+$/, "");
  return <Workspace apiDocsUrl={`${api}/docs`} />;
}
