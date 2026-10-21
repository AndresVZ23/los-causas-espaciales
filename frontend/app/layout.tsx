import type { Metadata } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles.css";
export const metadata: Metadata = {title: "Los Causas Espaciales", description: "Inteligencia terrestre trazable para decisiones de inversión"};
export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {return <html lang="es"><body>{children}</body></html>;}
