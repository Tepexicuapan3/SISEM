/**
 * Solicitudes de derechos ARCO (`/solicitudes-arco`, change
 * `solicitudes-arco`).
 */
/** Documento: A acceso, R rectificacion, C cancelacion, O oposicion. */
export type ArcoRequestType = "A" | "R" | "C" | "O";

export type ArcoRequestStatus = "recibida" | "en_proceso" | "procedente" | "improcedente";

export type ArcoRequesterRelation = "titular" | "representante";

export interface ArcoUserRef {
  id: number;
  username: string;
}

export interface ArcoRequestItem {
  id: number;
  folio: string;
  type: ArcoRequestType;
  status: ArcoRequestStatus;
  noExp: string;
  pkNum: number;
  requesterName: string;
  requesterRelation: ArcoRequesterRelation;
  requesterEmail: string | null;
  requesterPhone: string | null;
  description: string;
  transparencyFolio: string | null;
  receivedDate: string;
  dueDate: string;
  isOverdue: boolean;
  response: string | null;
  resolvedAt: string | null;
  /** SOLICITUD_ARCO.fe_respuesta (AAAA-MM-DD). */
  responseDate: string | null;
  registeredBy: ArcoUserRef | null;
  resolvedBy: ArcoUserRef | null;
  createdAt: string | null;
}

export interface ArcoRequestListParams {
  page: number;
  pageSize: number;
  estatus?: ArcoRequestStatus;
  tipo?: ArcoRequestType;
  noExp?: string;
  vencidas?: boolean;
}

export interface ArcoRequestListResponse {
  items: ArcoRequestItem[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface CreateArcoRequestPayload {
  type: ArcoRequestType;
  noExp: string;
  pkNum: number;
  requesterName: string;
  requesterRelation: ArcoRequesterRelation;
  requesterEmail?: string | null;
  requesterPhone?: string | null;
  description: string;
  receivedDate?: string;
  transparencyFolio?: string | null;
}

export interface ChangeArcoRequestStatusPayload {
  status: Exclude<ArcoRequestStatus, "recibida">;
  response?: string | null;
}
