// Cancelacion de nota cerrada en cascada (change `cancelacion-nota-cascada`).
// Contrato: backend/apps/consulta_medica/views_note_cancellation.py

export const NOTE_CANCELLATION_BLOCKER_CODE = {
  PRESCRIPTION_ITEM_DISPENSED: "PRESCRIPTION_ITEM_DISPENSED",
  LEAVE_SENT_TO_RH: "LEAVE_SENT_TO_RH",
  STUDY_RESULT_ACTIVE: "STUDY_RESULT_ACTIVE",
} as const;

export type NoteCancellationBlockerCode =
  (typeof NOTE_CANCELLATION_BLOCKER_CODE)[keyof typeof NOTE_CANCELLATION_BLOCKER_CODE];

export interface NoteCancellationBlocker {
  code: NoteCancellationBlockerCode | string;
  message: string;
  ids: number[];
}

export interface NoteCancellationCascadeCounts {
  prescriptionItems: number;
  prescriptionAuthorizations: number;
  diagnoses: number;
  referrals: number;
  referralStudies: number;
  medicalLeaves: number;
}

export interface NoteCancellationPreview {
  cancelable: boolean;
  visitStatus: string;
  alreadyCancelled: boolean;
  blockers: NoteCancellationBlocker[];
  cascade: NoteCancellationCascadeCounts;
  puedeAutorizar: boolean;
  // AUTHORIZER_NOT_DESIGNATED | NOTE_CENTER_UNRESOLVED | null
  puedeAutorizarMotivo: string | null;
  autoCancelacion: boolean;
  fueraAdscripcion: boolean;
  centroId: number | null;
}

export interface CancelConsultationNoteRequest {
  motivoId: number;
  motivoDetalle?: string | null;
  password: string;
}

export interface CancelConsultationNoteResponse {
  cancellationId: number;
  visit: { id: number; status: string };
  hashContenido: string;
  metodoFirma: string;
  fueraAdscripcion: boolean;
  cascade: NoteCancellationCascadeCounts;
}
