"use client";

import dynamic from "next/dynamic";

const Game = dynamic(() => import("../_components/game/game"), { ssr: false, loading: () => <div className="gameOpening" role="status">Preparando el viaje…</div> });

export default function GameEntry() {
  return <Game />;
}
