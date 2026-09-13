import type { ReferralType, ReferralStatus, ReferralVisitType } from "@api/types/referral.types";

export interface ReferralReportParams {
  fechaInicio?: string;
  fechaFin?: string;
  tipoPase?: ReferralType;
  status?: ReferralStatus;
  noExp?: string;
}

export interface ReferralReportItem {
  id: number;
  date: string;
  folio: string;
  referralType: ReferralType;
  noExp: string;
  pkNum: number;
  patientName: string | null;
  doctorName: string | null;
  destinationCenterName: string | null;
  specialtyName: string | null;
  visitType: ReferralVisitType | null;
  status: ReferralStatus;
}

export interface ReferralReportResponse {
  items: ReferralReportItem[];
  total: number;
  fechaInicio: string;
  fechaFin: string;
}
