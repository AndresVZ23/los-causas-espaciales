import type { Metadata } from "next";
import NeuralDop from "../_components/neural-dop";

export const metadata: Metadata = {
  title: "DOP neuronal | Los Causas Espaciales",
  description: "Red de dependencias y puertas verificables para completar la plataforma de inteligencia terrestre.",
};

export default function NeuralDopPage() {
  return <NeuralDop />;
}
