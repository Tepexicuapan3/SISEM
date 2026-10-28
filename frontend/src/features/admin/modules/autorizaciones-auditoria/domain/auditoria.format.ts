const EVENTOS: Record<string, string> = {
  CREADA: "Creada",
  RECALCULADA: "Recalculada (cambió el contenido)",
  NOTIFICADA: "Enviada a autorizadores",
  ESCALADA: "Escalada sin respuesta",
  APROBACION_PARCIAL: "Aprobación parcial",
  AUTORIZADA: "Autorizada",
  RECHAZADA: "Rechazada",
  VENCIDA: "Vencida sin resolverse",
  CANCELADA_ORIGEN: "Cancelada por el documento de origen",
};

export const etiquetaEvento = (evento: string) => EVENTOS[evento] ?? evento;

export const SELECCION: Record<string, string> = {
  ELEGIBLES: "Elegibles al crear",
  MANUAL: "Envío manual",
  ESPECIFICO: "Autorizador específico",
  ESCALAMIENTO: "Por escalamiento",
  DIRECTO: "Decidió sin notificación",
};

export const ESTATUS_DESTINATARIO: Record<string, string> = {
  NOTIFICADO: "Notificado",
  VISTO: "Visto",
  DECIDIO: "Decidió",
  ATENDIDA_POR_OTRO: "Atendida por otro",
  INHABILITADO: "Inhabilitado",
  RETIRADO: "Retirado",
};

/** Hash corto para leer en pantalla; el completo va en el title. */
export const hashCorto = (hash: string) => (hash.length > 16 ? `${hash.slice(0, 8)}…${hash.slice(-8)}` : hash);
