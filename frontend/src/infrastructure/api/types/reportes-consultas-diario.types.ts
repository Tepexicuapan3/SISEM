export interface DailyConsultationReportParams {
  fechaInicio?: string;
  fechaFin?: string;
  doctorId?: number;
  consultorioId?: number;
}

export interface DailyConsultationReportItem {
  visitId: number;
  folio: string;
  date: string;
  time: string | null;
  noExp: string | null;
  pkNum: number;
  patientName: string | null;
  serviceType: string;
  consultorio: string | null;
  doctorId: number;
  doctorName: string | null;
  primaryDiagnosis: string;
  cieCode: string | null;
  cieDescription: string | null;
}

export interface DailyConsultationReportResponse {
  items: DailyConsultationReportItem[];
  total: number;
  fechaInicio: string;
  fechaFin: string;
}
