export interface MedicalLeaveReportParams {
  fechaInicio?: string;
  fechaFin?: string;
  leaveTypeId?: number;
  noExp?: string;
}

export interface MedicalLeaveReportItem {
  id: number;
  folio: string;
  noExp: string;
  pkNum: number;
  patientName: string | null;
  doctorName: string | null;
  leaveTypeId: number;
  leaveTypeName: string;
  isSubsequent: boolean;
  days: number;
  startDate: string;
  endDate: string;
}

export interface MedicalLeaveReportResponse {
  items: MedicalLeaveReportItem[];
  total: number;
  fechaInicio: string;
  fechaFin: string;
}
