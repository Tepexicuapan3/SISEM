import type { ListResponse, PaginationParams } from "@api/types/common.types";

/**
 * Notificaciones del usuario autenticado (apps/notificaciones):
 * - GET   /notificaciones/?soloNoLeidas=true
 * - GET   /notificaciones/contador/
 * - PATCH /notificaciones/:id/leida/
 * - POST  /notificaciones/marcar-todas-leidas/
 * Tiempo real: WS /ws/v1/notificaciones/stream, evento "notification.created".
 * El cuerpo nunca trae datos clinicos; `urlAccion` es una ruta interna que solo navega.
 */

export interface Notificacion {
  id: number;
  categoria: string;
  titulo: string;
  cuerpo: string;
  tipoRecurso: string;
  referenciaRecurso: string;
  urlAccion: string;
  prioridad: "NORMAL" | "URGENTE";
  fechaCreacion: string;
  fechaLectura: string | null;
}

export interface NotificacionesListParams extends PaginationParams {
  soloNoLeidas?: boolean;
}

export type NotificacionesListResponse = ListResponse<Notificacion>;

export interface ContadorNotificacionesResponse {
  noLeidas: number;
}

export interface NotificacionResponse {
  notificacion: Notificacion;
}

export interface MarcarTodasResponse {
  actualizadas: number;
}
