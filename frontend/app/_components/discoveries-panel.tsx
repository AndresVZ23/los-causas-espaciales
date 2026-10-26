import type { Discovery, DiscoveryKind } from "./types";

const KIND: Record<DiscoveryKind, string> = {
  artefacto_probable: "Artefacto probable",
  confirmado: "Confirmado",
  sin_respaldo: "Sin respaldo",
  coincidencia: "Coincidencia",
  contradiccion: "Contradicción",
};

/** Lo que aparece solo al cruzar fuentes independientes; no es una conclusión, es lo que conviene mirar. */
export default function DiscoveriesPanel({ discoveries }: { discoveries?: Discovery[] }) {
  if (!discoveries?.length) return null;
  return (
    <section className="discoveriesPanel" aria-labelledby="discoveries-title">
      <div className="questionsHead">
        <h3 id="discoveries-title">Descubrimientos al cruzar fuentes</h3>
        <p>Cada dato se comprueba con fuentes independientes. Aquí queda lo que confirman, lo que contradicen y lo que solo una de ellas ve.</p>
      </div>
      <ul>
        {discoveries.map((item) => (
          <li key={`${item.kind}-${item.title}`} className={`discovery kind-${item.kind}`}>
            <span className="discoveryKind"><i aria-hidden="true" />{KIND[item.kind]}</span>
            <div>
              <h4>{item.title}</h4>
              <p>{item.detail}</p>
            </div>
            <span className="questionProvenance">{item.sources.join(" · ")}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
