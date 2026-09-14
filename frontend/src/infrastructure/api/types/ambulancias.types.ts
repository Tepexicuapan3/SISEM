export interface AmbulanceRequestScheduleItem {
  id: number;
  transferDate: string;
  transferTime: string;
  transferTypeId: number;
  transferTypeName: string;
  serviceTypeId: number;
  serviceTypeName: string;
}

export interface AmbulanceRequestItem {
  id: number;
  folio: string;
  noExp: string;
  pkNum: number;
  requestingClinicId: string;
  requestingClinicName: string | null;
  requestedByName: string;
  socialWorkNotes: string | null;
  reasonId: number;
  reasonName: string;
  reasonNotes: string | null;
  diagnosisText: string | null;
  originStreet: string | null;
  originZip: string | null;
  originNeighborhood: string | null;
  originBorough: string | null;
  originPhone: string | null;
  originReference: string | null;
  destinationId: number;
  destinationName: string;
  status: "activa" | "baja";
  authorizationStatus: "pendiente" | "autorizada" | "rechazada";
  authorizedById: number | null;
  authorizedAt: string | null;
  serviceNumber: string | null;
  rejectionNotes: string | null;
  schedules: AmbulanceRequestScheduleItem[];
  createdAt: string;
}

export interface AmbulanceRequestListParams {
  fechaInicio?: string;
  fechaFin?: string;
  authorizationStatus?: string;
  status?: string;
  noExp?: string;
}

export interface AmbulanceRequestListResponse {
  items: AmbulanceRequestItem[];
  total: number;
}

export interface CreateAmbulanceRequestScheduleItem {
  transferDate: string;
  transferTime: string;
  transferTypeId: number;
  serviceTypeId: number;
}

export interface CreateAmbulanceRequestRequest {
  noExp: string;
  pkNum?: number;
  requestingClinicId: string;
  requestedByName: string;
  requestedByRelationshipId?: string;
  socialWorkNotes?: string;
  reasonId: number;
  reasonNotes?: string;
  diagnosisText?: string;
  originStreet?: string;
  originZip?: string;
  originNeighborhood?: string;
  originBorough?: string;
  originPhone?: string;
  originReference?: string;
  destinationId: number;
  schedules: CreateAmbulanceRequestScheduleItem[];
}

export interface AuthorizeAmbulanceRequestRequest {
  serviceNumber: string;
}

export interface RejectAmbulanceRequestRequest {
  notes: string;
}
