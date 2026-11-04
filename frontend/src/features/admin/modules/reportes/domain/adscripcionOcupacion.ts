/** P-03 · Qué tan lleno está un consultorio familiar respecto a su tope. */

export type NivelOcupacion = "normal" | "alto" | "lleno";

export interface OcupacionConsultorio {
  porcentaje: number;
  nivel: NivelOcupacion;
}

/** Desde este porcentaje se avisa que el consultorio se está llenando. */
const UMBRAL_ALTO = 80;

/** Sin tope (null o 0) no hay ocupación que medir. */
export function ocupacionConsultorio(total: number, tope: number | null): OcupacionConsultorio | null {
  if (!tope) return null;
  const porcentaje = Math.round((total / tope) * 100);
  const nivel: NivelOcupacion = porcentaje >= 100 ? "lleno" : porcentaje >= UMBRAL_ALTO ? "alto" : "normal";
  return { porcentaje, nivel };
}
