export interface AmbulanceReportParams {
  fechaInicio?: string;
  fechaFin?: string;
  authorizationStatus?: string;
}

export interface AmbulanceReportItem {
  date: string;
  folio: string;
  noExp: string;
  pkNum: number;
  requestingClinicName: string | null;
  reasonName: string;
  destinationName: string;
  transferDate: string | null;
  status: string;
  authorizationStatus: string;
  serviceNumber: string | null;
}

export interface AmbulanceReportResponse {
  items: AmbulanceReportItem[];
  total: number;
  fechaInicio: string;
  fechaFin: string;
}
