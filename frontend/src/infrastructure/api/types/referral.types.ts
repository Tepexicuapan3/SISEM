export type ReferralType =
  | "laboratorio"
  | "gabinete"
  | "especialidad"
  | "hospitalizacion"
  | "tercer_nivel";

export type ReferralVisitType = "primera_vez" | "subsecuente";

export type ReferralStatus = "activo" | "cancelado";

/** Motor de autorizaciones (solo laboratorio y gabinete con estudios marcados). */
export type ReferralAuthorizationStatus = "NO_REQUIERE" | "PENDIENTE" | "AUTORIZADO" | "RECHAZADO" | "VENCIDO";

export interface ReferralStudyItem {
  id: number;
  studyTypeId: number;
  studyTypeName: string;
  costApproved: boolean;
  validUntil: string | null;
  status: ReferralStatus;
}

export interface ReferralItem {
  id: number;
  visitId: number;
  noExp: string;
  pkNum: number;
  referralType: ReferralType;
  destinationCenterId: number | null;
  destinationCenterName: string | null;
  specialtyId: number | null;
  specialtyName: string | null;
  requestedCare: string | null;
  visitType: ReferralVisitType | null;
  folio: string;
  status: ReferralStatus;
  cancellationReasonId: number | null;
  authorizationStatus: ReferralAuthorizationStatus;
  studies: ReferralStudyItem[];
  isActive: boolean;
  createdAt: string;
}

export interface PatientReferralsResponse {
  items: ReferralItem[];
  total: number;
}

export interface CreateReferralStudyRequest {
  studyTypeId: number;
}

export interface CreateReferralRequest {
  referralType: ReferralType;
  destinationCenterId?: number;
  specialtyId?: number;
  requestedCare?: string;
  visitType?: ReferralVisitType;
  studies?: CreateReferralStudyRequest[];
}

export interface CancelReferralRequest {
  cancellationReasonId: number;
}
