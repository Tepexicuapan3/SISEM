/**
 * Bitacora de acceso al expediente clinico (`GET /bitacora-acceso`,
 * change `bitacora-acceso-expediente`). Solo lectura.
 */
export type AccessLogEventType = "acceso" | "diagnostico_restringido";

/** BITACORA_ACCESO.accion del documento. */
export type AccessLogAction = "ver" | "imprimir" | "exportar" | "modificar";

export type AccessLogSection =
  | "historia_clinica"
  | "estomatologia"
  | "alergias"
  | "consultas"
  | "consultas_legado"
  | "odontograma"
  | "incapacidades"
  | "estudios"
  | "antecedentes_personales"
  | "antecedentes_familiares"
  | "antecedentes_quirurgicos"
  | "habitos"
  | "tratamientos_dentales"
  | "notas_historicas"
  | "ficha_paciente"
  | "reporte_consultas_diario"
  | "reporte_incapacidades"
  | "reporte_pases"
  | "reporte_ambulancias";

export interface AccessLogItem {
  id: number;
  occurredAt: string | null;
  eventType: AccessLogEventType;
  action: AccessLogAction;
  actorId: number | null;
  actorUsername: string | null;
  actorName: string | null;
  noExp: string | null;
  pkNum: number | null;
  section: AccessLogSection | null;
  redactedCount: number | null;
  ipAddress: string | null;
  endpoint: string | null;
}

export interface AccessLogListParams {
  page: number;
  pageSize: number;
  tipo?: AccessLogEventType;
  accion?: AccessLogAction;
  seccion?: AccessLogSection;
  noExp?: string;
  pkNum?: number;
  usuario?: string;
  fechaInicio?: string;
  fechaFin?: string;
}

export interface AccessLogListResponse {
  items: AccessLogItem[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}
