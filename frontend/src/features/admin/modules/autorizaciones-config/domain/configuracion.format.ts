import type { AmbitoMotivo, Modalidad } from "@api/types/autorizaciones/configuracion.types";

export const ETIQUETA_MODALIDAD: Record<Modalidad, string> = {
  PRIMERO_VALIDO: "Primero válido",
  MULTIPLE: "Múltiple",
};

export const DESCRIPCION_MODALIDAD: Record<Modalidad, string> = {
  PRIMERO_VALIDO: "La primera aprobación válida resuelve la solicitud.",
  MULTIPLE: "Se necesitan varias aprobaciones de autorizadores distintos.",
};

export const ETIQUETA_AMBITO: Record<AmbitoMotivo, string> = {
  RECHAZO: "Rechazo de solicitud",
  SUSPENSION: "Suspensión de autorizador",
  BAJA: "Baja de autorizador",
  CANCELACION: "Cancelación de solicitud",
};

/** Valor propio de la regla, o el del tipo marcado como heredado. */
export const valorOHereda = (valor: string | number | null, heredado: string | number) =>
  valor === null ? `${heredado} (del tipo)` : String(valor);
