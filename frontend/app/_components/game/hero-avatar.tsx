import type { Gender } from "./game-types";

/** Superhéroe en 2D, de colores planos. Solo cambian el peinado y la silueta entre las dos figuras. */
export function HeroAvatar({ gender, size = 120, title }: { gender: Gender; size?: number; title?: string }) {
  const woman = gender === "mujer";
  return (
    <svg viewBox="0 0 100 140" width={size} height={size * 1.4} role={title ? "img" : undefined} aria-hidden={title ? undefined : true} aria-label={title}>
      {/* capa */}
      <path d="M30 52 Q50 46 70 52 L80 124 Q50 132 20 124 Z" fill="#c8323f" />
      {/* piernas y botas */}
      <rect x="38" y="96" width="10" height="28" rx="4" fill="#1f4f8f" />
      <rect x="52" y="96" width="10" height="28" rx="4" fill="#1f4f8f" />
      <rect x="36" y="118" width="13" height="10" rx="3" fill="#f1c84b" />
      <rect x="51" y="118" width="13" height="10" rx="3" fill="#f1c84b" />
      {/* cuerpo */}
      {woman
        ? <path d="M36 54 Q50 50 64 54 L66 100 L34 100 Z" fill="#2c6fd1" />
        : <path d="M33 54 Q50 49 67 54 L64 100 L36 100 Z" fill="#2c6fd1" />}
      <rect x="35" y="88" width="30" height="6" fill="#f1c84b" />
      {/* emblema: la Tierra */}
      <circle cx="50" cy="70" r="8" fill="#38d9c3" stroke="#f1c84b" strokeWidth="2" />
      <path d="M45 67 q3 -2 5 1 q2 3 5 1 M46 74 q3 1 6 -1" stroke="#1f4f8f" strokeWidth="1.6" fill="none" />
      {/* brazos */}
      <rect x="24" y="56" width="9" height="30" rx="4" fill="#2c6fd1" transform="rotate(12 28 56)" />
      <rect x="67" y="56" width="9" height="30" rx="4" fill="#2c6fd1" transform="rotate(-12 72 56)" />
      <circle cx="24" cy="86" r="5" fill="#e0a77a" />
      <circle cx="76" cy="86" r="5" fill="#e0a77a" />
      {/* cabeza */}
      {woman && <path d="M33 36 Q32 14 50 13 Q68 14 67 36 L69 58 Q60 52 58 40 L42 40 Q40 52 31 58 Z" fill="#3a2418" />}
      <circle cx="50" cy="34" r="15" fill="#e0a77a" />
      {woman
        ? <path d="M35 32 Q36 17 50 17 Q64 17 65 32 Q57 24 50 26 Q43 24 35 32 Z" fill="#3a2418" />
        : <path d="M35 30 Q35 17 50 17 Q65 17 65 30 Q58 22 50 24 Q42 22 35 30 Z" fill="#2a1a10" />}
      {/* antifaz y ojos */}
      <path d="M36 32 Q50 27 64 32 L62 38 Q50 35 38 38 Z" fill="#c8323f" />
      <circle cx="44" cy="34" r="2" fill="#fff" />
      <circle cx="56" cy="34" r="2" fill="#fff" />
      <path d="M45 42 Q50 45 55 42" stroke="#7a3b2b" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  );
}
