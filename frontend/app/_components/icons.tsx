import type { ReactNode, SVGProps } from "react";

export type IconName =
  | "climate"
  | "solar"
  | "hazard"
  | "environment"
  | "social"
  | "infrastructure"
  | "investment"
  | "map"
  | "download"
  | "layers"
  | "settings"
  | "info"
  | "menu";

const paths: Record<IconName, ReactNode> = {
  climate: <><path d="M4 15.5A4.5 4.5 0 0 1 8.5 11a6 6 0 0 1 11.3 2.8A3.5 3.5 0 0 1 19.5 21H8a4 4 0 0 1-4-5.5Z"/><path d="M12 3v3M4.2 6.2l2.1 2.1M19.8 6.2l-2.1 2.1"/></>,
  solar: <><circle cx="12" cy="12" r="3.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/></>,
  hazard: <><path d="M12 3 2.8 20h18.4L12 3Z"/><path d="M12 9v5M12 17.2v.1"/></>,
  environment: <><path d="M19.5 4.5C12 4.5 6 8 6 14c0 3 2 5.5 5 5.5 6 0 8.5-6 8.5-15Z"/><path d="M4 21c2-5 6-8 11-10"/></>,
  social: <><circle cx="8" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M2.5 20c.3-4 2.2-6 5.5-6s5.2 2 5.5 6M14 15c3.8-.8 6.5 1 7 5"/></>,
  infrastructure: <><path d="M3 20h18M5 20V9l7-5 7 5v11M9 20v-6h6v6M8 10h.1M16 10h.1"/></>,
  investment: <><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/><path d="m4 7 6-4 6 6 5-5"/></>,
  map: <><path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z"/><path d="M9 3v15M15 6v15"/></>,
  download: <><path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 19h16"/></>,
  layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
  settings: <path d="M4 6h10M18 6h2M14 4v4M4 12h2M10 12h10M6 10v4M4 18h8M16 18h4M12 16v4"/>,
  info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
};

export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: IconName }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      {paths[name]}
    </svg>
  );
}
