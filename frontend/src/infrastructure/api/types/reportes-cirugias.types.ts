export interface SurgeryReportParams {
  fechaInicio?: string;
  fechaFin?: string;
  status?: string;
}

export interface SurgeryReportItem {
  date: string;
  time: string;
  folio: string;
  noExp: string;
  pkNum: number;
  surgeonName: string | null;
  surgeryTypeName: string;
  classificationName: string;
  status: string;
  performedStatus: string;
}

export interface SurgeryReportResponse {
  items: SurgeryReportItem[];
  total: number;
  fechaInicio: string;
  fechaFin: string;
}
