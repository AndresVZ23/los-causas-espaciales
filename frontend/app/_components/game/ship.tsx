/** Nave del héroe vista desde atrás: casco en cuña, alas plegadas y dos motores encendidos. Colores planos, diseño propio. */
export function Ship({ width = 150 }: { width?: number }) {
  return (
    <svg viewBox="0 0 200 110" width={width} height={width * 0.55} aria-hidden>
      <defs>
        <linearGradient id="hull" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#5d6b8f" />
          <stop offset="1" stopColor="#232a40" />
        </linearGradient>
        <radialGradient id="engine" cx=".5" cy=".5" r=".5">
          <stop offset="0" stopColor="#e9fdff" />
          <stop offset=".45" stopColor="#5fe3ff" />
          <stop offset="1" stopColor="#5fe3ff" stopOpacity="0" />
        </radialGradient>
      </defs>
      {/* alas */}
      <path d="M100 30 L8 78 L20 86 L100 62 L180 86 L192 78 Z" fill="#2c3550" stroke="#c9a54a" strokeWidth="2" />
      <path d="M14 76 L4 52 L22 72 Z M186 76 L196 52 L178 72 Z" fill="#c9a54a" />
      {/* casco */}
      <path d="M100 12 L132 70 L118 90 L82 90 L68 70 Z" fill="url(#hull)" stroke="#c9a54a" strokeWidth="2" />
      <path d="M100 22 L114 52 L86 52 Z" fill="#7fd6ff" opacity=".55" />
      <rect x="88" y="62" width="24" height="16" rx="3" fill="#1a2033" stroke="#c9a54a" strokeWidth="1.5" />
      {/* motores */}
      <circle className="shipEngine" cx="84" cy="92" r="11" fill="url(#engine)" />
      <circle className="shipEngine" cx="116" cy="92" r="11" fill="url(#engine)" />
      <circle cx="84" cy="88" r="5" fill="#1a2033" stroke="#c9a54a" strokeWidth="1.5" />
      <circle cx="116" cy="88" r="5" fill="#1a2033" stroke="#c9a54a" strokeWidth="1.5" />
      {/* luces de posición */}
      <circle cx="10" cy="80" r="2.5" fill="#ff5a4f" />
      <circle cx="190" cy="80" r="2.5" fill="#48e08a" />
    </svg>
  );
}
