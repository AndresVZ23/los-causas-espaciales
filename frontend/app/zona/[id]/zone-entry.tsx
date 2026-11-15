"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";

const ZoneExplorer = dynamic(() => import("../../_components/zone/zone-explorer"), { ssr: false, loading: () => <div className="zoneOpening" role="status">Abriendo la zona…</div> });

export default function ZoneEntry({ zoneId }: { zoneId: string }) {
  const router = useRouter();
  return <ZoneExplorer zoneId={zoneId} onExit={() => router.push("/plataforma")} />;
}
