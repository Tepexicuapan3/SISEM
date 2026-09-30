import { VISIT_STATUS, type VisitStatus } from "@api/types";

export const canRunRecepcionStatusAction = (status: VisitStatus): boolean => {
  return status === VISIT_STATUS.EN_ESPERA;
};

export const canCaptureVitals = (status: VisitStatus): boolean => {
  return status === VISIT_STATUS.EN_SOMATOMETRIA;
};

export const canStartConsultation = (status: VisitStatus): boolean => {
  return status === VISIT_STATUS.LISTA_PARA_DOCTOR;
};

export const canCloseConsultation = (status: VisitStatus): boolean => {
  return status === VISIT_STATUS.EN_CONSULTA;
};
