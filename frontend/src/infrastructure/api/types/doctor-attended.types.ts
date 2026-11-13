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

export interface DoctorAttendedItem {
  visitId: number;
  folio: string;
  nombrePaciente: string;
  noExp: string;
  pkNum: number | null;
  attendedAt: string | null;
  prescription: DoctorAttendedPrescription | null;
}

export interface DoctorAttendedTodayResponse {
  items: DoctorAttendedItem[];
  total: number;
}
