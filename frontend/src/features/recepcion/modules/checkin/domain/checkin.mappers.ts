import {
  ARRIVAL_TYPE,
  type CreateVisitRequest,
  type VisitQueueItem,
} from "@api/types";
import type {
  CheckinFormInput,
  CheckinFormValues,
} from "@features/recepcion/modules/checkin/domain/checkin.schemas";
import {
  RECEPCION_SERVICE,
  resolveRecepcionService,
  stripRecepcionServiceTag,
} from "@features/recepcion/shared/domain/recepcion.services";

export const mapCheckinFormToCreateVisitRequest = (
  values: CheckinFormValues,
  nombrePaciente?: string,
  idPaciente?: number,
): CreateVisitRequest => ({
  // Con idPaciente no viaja la llave vieja: el backend la toma de cns_paciente.
  ...(idPaciente ? { idPaciente } : { noExp: values.noExp, pkNum: values.pkNum }),
  nombrePaciente:  nombrePaciente || undefined,
  arrivalType:     values.arrivalType,
  serviceType:     values.serviceType,
  appointmentId:
    values.arrivalType === ARRIVAL_TYPE.APPOINTMENT
      ? values.appointmentId?.trim()
      : undefined,
  doctorId:      values.doctorId,
  consultorioId: values.consultorioId,
  tipoCitaId:    values.tipoCitaId,
  notes:          values.notes?.trim() || undefined,
  horaConsulta:   values.horaConsulta?.trim() || undefined,
  fechaConsulta:  values.fechaConsulta || undefined,
});

export const mapVisitToCheckinDefaults = (
  visit: Pick<
    VisitQueueItem,
    | "noExp"
    | "pkNum"
    | "serviceType"
    | "arrivalType"
    | "appointmentId"
    | "doctorId"
    | "tipoCitaId"
    | "notes"
  >,
): Partial<CheckinFormInput> => {
  const resolvedService = resolveRecepcionService(visit);
  const serviceType =
    resolvedService === RECEPCION_SERVICE.SIN_CLASIFICAR
      ? RECEPCION_SERVICE.MEDICINA_GENERAL
      : resolvedService;

  return {
    noExp:         visit.noExp,
    pkNum:         visit.pkNum,
    serviceType,
    arrivalType:   visit.arrivalType,
    appointmentId: visit.appointmentId ?? "",
    doctorId:      visit.doctorId ?? undefined,
    tipoCitaId:    visit.tipoCitaId ?? undefined,
    notes:         stripRecepcionServiceTag(visit.notes),
  };
};
