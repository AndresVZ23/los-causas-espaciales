import ZoneEntry from "./zone-entry";

/** Enlace directo a una zona para recorrer: /zona/moquegua o /zona/taal. Al salir se vuelve a la consola. */
export default async function ZonePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ZoneEntry zoneId={id} />;
}
