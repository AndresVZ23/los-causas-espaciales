import type { Metadata } from "next";
import GameEntry from "./game-entry";

export const metadata: Metadata = {
  title: "Detectives de la Tierra · Los Causas Espaciales",
  description: "Modo jugador: un superhéroe viaja de la Luna a la Tierra y resuelve misiones con datos reales de NASA.",
};

/** Modo jugador y espectador. La consola técnica sigue en «/». */
export default function JugarPage() {
  return <GameEntry />;
}
