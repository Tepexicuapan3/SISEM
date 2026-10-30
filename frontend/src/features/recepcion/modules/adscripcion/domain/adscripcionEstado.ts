import { ApiError } from "@api/utils/errors";
import type { AdscripcionResumen, EstadoAdscripcion } from "@api/types";

/**
 * P-03 · Cómo se presenta a recepción el estado del consultorio familiar.
 * Solo presentación: la regla la decide el backend (estado de la evaluación).
 */

export type AccionAdscripcion = "asignar" | "reasignar" | null;
export type VarianteAdscripcion = "stable" | "alert" | "critical" | "info";

export interface PresentacionAdscripcion {
  estado: EstadoAdscripcion;
  etiqueta: string;
  variante: VarianteAdscripcion;
  /** Qué puede hacer recepción desde la búsqueda; null = nada que hacer. */
  accion: AccionAdscripcion;
  /** Texto del aviso al elegir a la persona; null = sin aviso. */
  aviso: string | null;
}

export const etiquetaConsultorio = (consultorio: { numero: number | null; turno: string | null }) =>
  `Cons. ${consultorio.numero ?? "?"} · ${consultorio.turno ?? "Sin turno"}`;

const citas = (n: number) => (n === 1 ? "1 cita futura" : `${n} citas futuras`);

/** null cuando P-03 no aplica a la persona (no se muestra nada nuevo). */
export function presentarEstadoAdscripcion(
  resumen: AdscripcionResumen | null | undefined,
): PresentacionAdscripcion | null {
  if (!resumen) return null;
  switch (resumen.estado) {
    case "VIGENTE":
      return {
        estado: resumen.estado,
        etiqueta: etiquetaConsultorio({ numero: resumen.numeroConsultorio, turno: resumen.turno }),
        variante: "stable",
        accion: null,
        aviso: resumen.sinMedicoActivo
          ? "Su consultorio familiar no tiene médico activo hoy. Puede atenderse con excepción."
          : null,
      };
    case "SIN_ADSCRIPCION":
      return {
        estado: resumen.estado,
        etiqueta: "Sin consultorio",
        variante: "alert",
        accion: "asignar",
        aviso: "No tiene consultorio familiar. Asígnele uno antes de la ficha de medicina general.",
      };
    case "NO_COINCIDE":
      return {
        estado: resumen.estado,
        etiqueta: "No coincide",
        variante: "critical",
        accion: "reasignar",
        aviso:
          "SERMED lo tiene en otra clínica. Hay que reasignarle consultorio" +
          (resumen.citasFuturas > 0 ? `; se cancelarán ${citas(resumen.citasFuturas)} del consultorio anterior.` : "."),
      };
    case "CONSULTORIO_INACTIVO":
      return {
        estado: resumen.estado,
        etiqueta: "Consultorio inactivo",
        variante: "alert",
        accion: "reasignar",
        aviso:
          "Su consultorio familiar ya no está activo. Hay que asignarle otro" +
          (resumen.citasFuturas > 0 ? `; se cancelarán ${citas(resumen.citasFuturas)}.` : "."),
      };
    case "CLINICA_SIN_CENTRO":
      return {
        estado: resumen.estado,
        etiqueta: "Clínica no registrada",
        variante: "alert",
        accion: null,
        aviso: "La clínica de SERMED de esta persona no está registrada en SIRES. Avise al administrador.",
      };
    default:
      // P03_INACTIVO, SIN_DATO_EXPEDIENTE, NO_VIGENTE: se trabaja como hoy.
      return null;
  }
}

export interface ConflictoConsultorioFamiliar {
  estado: EstadoAdscripcion;
  idConsultorioFamiliar: number | null;
  idConsultorioSolicitado: number | null;
  mensaje: string;
}

/** Reconoce el 409 CONSULTORIO_FAMILIAR_DIFERENTE de fichas, citas y check-in. */
export function conflictoConsultorioFamiliar(error: unknown): ConflictoConsultorioFamiliar | null {
  if (!(error instanceof ApiError) || error.code !== "CONSULTORIO_FAMILIAR_DIFERENTE") return null;
  const details = (error.details ?? {}) as Record<string, unknown>;
  return {
    estado: details.estado as EstadoAdscripcion,
    idConsultorioFamiliar: (details.idConsultorioFamiliar as number | null) ?? null,
    idConsultorioSolicitado: (details.idConsultorioSolicitado as number | null) ?? null,
    mensaje: error.message,
  };
}
