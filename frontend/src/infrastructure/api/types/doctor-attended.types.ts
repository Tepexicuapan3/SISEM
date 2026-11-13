// Mi jornada: consultas que el medico cerro hoy (GET /doctor/attended-today).

export interface DoctorAttendedPrescription {
  folio: string;
  medicationsCount: number;
  hasControlled: boolean;
  authorization: {
    status: "pendiente" | "autorizada" | "rechazada" | "cancelada";
    rejectionReason: string | null;
  } | null;
  /** Misma regla que la impresion: con medicamentos y sin autorizacion pendiente o rechazada. */
  printable: boolean;
}

/** Lo demas que salio de la consulta. */
export interface DoctorAttendedDocuments {
  /** La nota cerrada se puede reimprimir. */
  notePrintable: boolean;
  medicalLeave: { folio: string; days: number } | null;
  referrals: { folio: string; type: string; label: string | null }[];
  /** Fecha de seguimiento indicada en la nota (YYYY-MM-DD). */
  followUpDate: string | null;
}

export interface DoctorAttendedItem {
  visitId: number;
  folio: string;
  nombrePaciente: string;
  noExp: string;
  pkNum: number | null;
  attendedAt: string | null;
  prescription: DoctorAttendedPrescription | null;
  documents: DoctorAttendedDocuments;
}

export interface DoctorAttendedTodayResponse {
  items: DoctorAttendedItem[];
  total: number;
}
