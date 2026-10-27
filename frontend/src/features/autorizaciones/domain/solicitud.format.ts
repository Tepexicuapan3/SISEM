import type { EstatusSolicitud } from "@api/types/autorizaciones/solicitudes.types";

/** Rutas del frontend de la bandeja (area clinica). */
export const RUTA_BANDEJA = "/clinico/autorizaciones";
export const rutaDetalle = (uuid: string) => `${RUTA_BANDEJA}/${uuid}`;

type VarianteBadge = "stable" | "alert" | "critical" | "info" | "outline";

const ESTATUS: Record<EstatusSolicitud, { etiqueta: string; variante: VarianteBadge }> = {
  PENDIENTE: { etiqueta: "Pendiente", variante: "alert" },
  AUTORIZADA: { etiqueta: "Autorizada", variante: "stable" },
  RECHAZADA: { etiqueta: "Rechazada", variante: "critical" },
  VENCIDA: { etiqueta: "Vencida", variante: "outline" },
  CANCELADA: { etiqueta: "Cancelada", variante: "outline" },
};

export const describirEstatusSolicitud = (estatus: EstatusSolicitud) => ESTATUS[estatus];

export const ORIGENES: Record<string, string> = {
  RECETA: "Receta",
  PASE_LABORATORIO: "Pase de laboratorio",
  PASE_GABINETE: "Pase de gabinete",
  CANCELACION_NOTA: "Cancelación de nota",
};

export const MOTIVOS: Record<string, string> = {
  MEDICAMENTO_ESPECIAL: "Medicamento de cuadro especial",
  MEDICAMENTO_CONTROLADO: "Medicamento controlado",
  COSTO_RECETA: "Costo de la receta",
  ESTUDIO_MARCADO: "Estudio que requiere autorización",
  CANCELACION_NOTA: "Cancelación de nota",
};

/** Cuanto falta para que la solicitud venza (urgente: menos de 2 horas). */
export const tiempoRestante = (fechaLimite: string, ahora: Date = new Date()) => {
  const minutos = Math.round((new Date(fechaLimite).getTime() - ahora.getTime()) / 60000);
  if (minutos <= 0) return { texto: "Vencida", urgente: true };
  if (minutos < 60) return { texto: `Vence en ${minutos} min`, urgente: true };
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return { texto: `Vence en ${horas} h`, urgente: horas < 2 };
  return { texto: `Vence en ${Math.floor(horas / 24)} d`, urgente: false };
};

export const formatFechaHora = (valor: string | null) =>
  valor ? new Date(valor).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" }) : "—";
