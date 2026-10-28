import type { ReferralAuthorizationStatus } from "@api/types/referral.types";

/** Estatus del pase en el motor de autorizaciones (laboratorio y gabinete). */
export const ETIQUETA_AUTORIZACION_PASE: Record<ReferralAuthorizationStatus, string> = {
  NO_REQUIERE: "No requiere",
  PENDIENTE: "Pendiente",
  AUTORIZADO: "Autorizado",
  RECHAZADO: "Rechazado",
  VENCIDO: "Vencido",
};

export const VARIANTE_AUTORIZACION_PASE: Record<
  ReferralAuthorizationStatus,
  "secondary" | "alert" | "stable" | "critical" | "outline"
> = {
  NO_REQUIERE: "outline",
  PENDIENTE: "alert",
  AUTORIZADO: "stable",
  RECHAZADO: "critical",
  VENCIDO: "secondary",
};

/** Texto extra del aviso «Pase emitido»: solo si quedo pendiente de autorizar. */
export const avisoAutorizacionPaseEmitido = (estatus: ReferralAuthorizationStatus | undefined) =>
  estatus === "PENDIENTE" ? " Requiere autorización: ya se envió a los autorizadores." : "";
