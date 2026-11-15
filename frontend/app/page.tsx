import type { Metadata } from "next";
import GameEntry from "./jugar/game-entry";

export const metadata: Metadata = {
  title: "TERRA 2045 · El último viaje · Los Causas Espaciales",
  description: "Videojuego educativo: desde la colonia lunar de 2045, una persona viaja a 2026 para cambiar el futuro con datos reales de observación de la Tierra de NASA.",
};

/** Portada: el juego TERRA 2045 (ADR-050). La consola técnica de la plataforma está en «/plataforma». */
export default function Home() {
  return <GameEntry />;
}
