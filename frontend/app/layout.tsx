import type { Metadata } from "next";
import { IBM_Plex_Mono, Public_Sans } from "next/font/google";
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles.css";

const publicSans = Public_Sans({
  variable: "--font-public-sans",
  subsets: ["latin"],
  display: "swap",
});

const dataMono = IBM_Plex_Mono({
  variable: "--font-data-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Los Causas Espaciales",
  description: "Inteligencia terrestre trazable para decisiones de inversión",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="es" className={`${publicSans.variable} ${dataMono.variable}`}><body suppressHydrationWarning>{children}</body></html>;
}
