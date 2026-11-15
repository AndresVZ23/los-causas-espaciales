import { redirect } from "next/navigation";

/** Dirección anterior del modo jugador: desde ADR-050 el juego es la portada. Se conserva para enlaces viejos. */
export default function JugarPage() {
  redirect("/");
}
