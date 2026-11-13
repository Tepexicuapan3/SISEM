import { http, HttpResponse } from "msw";
import {
  ARRIVAL_TYPE,
  VISIT_SERVICE,
  VISIT_STATUS,
  type VisitQueueItem,
} from "@api/types/visits.types";
import { getApiUrl } from "../urls";

type VisitStatus = VisitQueueItem["status"];

interface VisitsMockState {
  nextVisitId: number;
  visitsStore: VisitQueueItem[];
}

const buildVisit = (
  id: number,
  overrides: Partial<VisitQueueItem> = {},
): VisitQueueItem => ({
  id,
  folio:         `VST-${id.toString().padStart(6, "0")}`,
  noExp:         `9${String(id).padStart(5, "0")}`,
  pkNum:         0,
  nombrePaciente: null,
  arrivalType:   ARRIVAL_TYPE.APPOINTMENT,
  serviceType:   VISIT_SERVICE.MEDICINA_GENERAL,
  appointmentId: `APP-${id}`,
  doctorId:      121,
  doctorNombre:  null,
  consultorioId: null,
  consultorioNombre: null,
  tipoCitaId:    null,
  tipoCitaNombre: null,
  centroId:      null,
  centroNombre:  null,
  notes:         "mock visit",
  horaConsulta:  null,
  fechaConsulta: null,
  fechaCita:     null,
  numFicha:      null,
  turnoNombre:   "Matutino",
  status:        VISIT_STATUS.EN_ESPERA,
  fechaAlta:     null,
  enSomatometriaAt: null,
  createdById:   null,
  vitals:        null,
  ...overrides,
});

const VISITS_STATE_KEY = "__SISEM_VISITS_MSW_STATE__" as const;

const globalWithVisitsState = globalThis as typeof globalThis & {
  [VISITS_STATE_KEY]?: VisitsMockState;
};

const getVisitsState = (): VisitsMockState => {
  if (!globalWithVisitsState[VISITS_STATE_KEY]) {
    globalWithVisitsState[VISITS_STATE_KEY] = {
      nextVisitId: 3000,
      visitsStore: [buildVisit(2001)],
    };
  }

  return globalWithVisitsState[VISITS_STATE_KEY];
};

const updateVisitStatus = (
  visitId: number,
  status: VisitStatus,
): VisitQueueItem | null => {
  const state = getVisitsState();
  const visitIndex = state.visitsStore.findIndex(
    (visit) => visit.id === visitId,
  );
  if (visitIndex === -1) {
    return null;
  }

  const nextVisit = {
    ...state.visitsStore[visitIndex],
    status,
  };
  state.visitsStore[visitIndex] = nextVisit;
  return nextVisit;
};

export const visitsHandlers = [
  // Mi jornada: por defecto el medico no cerro consultas hoy.
  http.get(getApiUrl("doctor/attended-today"), () => {
    return HttpResponse.json({ items: [], total: 0 });
  }),

  http.get(getApiUrl("visits"), ({ request }) => {
    const state = getVisitsState();
    const url = new URL(request.url);
    const statusFilter = url.searchParams.get("status");
    const items = statusFilter
      ? state.visitsStore.filter((visit) => visit.status === statusFilter)
      : state.visitsStore;

    return HttpResponse.json({
      items,
      page: 1,
      pageSize: 50,
      total: items.length,
      totalPages: 1,
    });
  }),

  http.post(getApiUrl("visits"), async ({ request }) => {
    const state = getVisitsState();
    const payload = (await request.json()) as {
      noExp:          string;
      pkNum?:         number;
      appointmentId?: string;
      doctorId?:      number;
      notes?:         string;
    };

    const visit = buildVisit(state.nextVisitId++, {
      noExp:         payload.noExp,
      pkNum:         payload.pkNum ?? 0,
      appointmentId: payload.appointmentId ?? null,
      doctorId:      payload.doctorId ?? null,
      notes:         payload.notes ?? null,
    });

    state.visitsStore = [visit, ...state.visitsStore];

    return HttpResponse.json(visit, { status: 201 });
  }),

  http.patch(
    getApiUrl("visits/:visitId/status"),
    async ({ params, request }) => {
      const visitId = Number(params.visitId);
      const payload = (await request.json()) as { targetStatus: VisitStatus };
      const updated = updateVisitStatus(visitId, payload.targetStatus);

      if (!updated) {
        return HttpResponse.json(
          {
            code: "VISIT_NOT_FOUND",
            message: "Visita no encontrada",
            status: 404,
          },
          { status: 404 },
        );
      }

      return HttpResponse.json({ id: updated.id, status: updated.status });
    },
  ),

  http.post(
    getApiUrl("visits/:visitId/vitals"),
    async ({ params, request }) => {
      const state = getVisitsState();
      const visitId = Number(params.visitId);
      const visitIndex = state.visitsStore.findIndex(
        (visit) => visit.id === visitId,
      );
      if (visitIndex === -1) {
        return HttpResponse.json(
          {
            code: "VISIT_NOT_FOUND",
            message: "Visita no encontrada",
            status: 404,
          },
          { status: 404 },
        );
      }

      const payload = (await request.json()) as {
        weightKg: number;
        heightCm: number;
        temperatureC: number;
        oxygenSaturationPct: number;
        notes?: string;
      };

      const bmi = Number(
        (payload.weightKg / (payload.heightCm / 100) ** 2).toFixed(2),
      );
      const nextVisit = {
        ...state.visitsStore[visitIndex],
        status: VISIT_STATUS.LISTA_PARA_DOCTOR,
        vitals: {
          ...payload,
          bmi,
          capturedAt: new Date().toISOString(),
          reusedFromVisitId: null,
          reusedFrom: null,
        },
      };
      state.visitsStore[visitIndex] = nextVisit;

      return HttpResponse.json({
        visitId,
        status: nextVisit.status,
        vitals: nextVisit.vitals,
      });
    },
  ),

  http.post(getApiUrl("visits/:visitId/consultation/start"), ({ params }) => {
    const visitId = Number(params.visitId);
    const updated = updateVisitStatus(visitId, VISIT_STATUS.EN_CONSULTA);

    if (!updated) {
      return HttpResponse.json(
        {
          code: "VISIT_NOT_FOUND",
          message: "Visita no encontrada",
          status: 404,
        },
        { status: 404 },
      );
    }

    return HttpResponse.json(updated);
  }),

  http.post(getApiUrl("visits/:visitId/diagnosis"), ({ params }) => {
    const state = getVisitsState();
    const visitId = Number(params.visitId);
    const visit = state.visitsStore.find((entry) => entry.id === visitId);

    if (!visit) {
      return HttpResponse.json(
        {
          code: "VISIT_NOT_FOUND",
          message: "Visita no encontrada",
          status: 404,
        },
        { status: 404 },
      );
    }

    return HttpResponse.json({ visitId, status: visit.status });
  }),

  http.post(getApiUrl("visits/:visitId/prescriptions"), ({ params }) => {
    const state = getVisitsState();
    const visitId = Number(params.visitId);
    const visit = state.visitsStore.find((entry) => entry.id === visitId);

    if (!visit) {
      return HttpResponse.json(
        {
          code: "VISIT_NOT_FOUND",
          message: "Visita no encontrada",
          status: 404,
        },
        { status: 404 },
      );
    }

    return HttpResponse.json({ visitId, status: visit.status, items: [] });
  }),

  http.post(getApiUrl("visits/:visitId/consultation/close"), ({ params }) => {
    const visitId = Number(params.visitId);
    const updated = updateVisitStatus(visitId, VISIT_STATUS.CERRADA);

    if (!updated) {
      return HttpResponse.json(
        {
          code: "VISIT_NOT_FOUND",
          message: "Visita no encontrada",
          status: 404,
        },
        { status: 404 },
      );
    }

    return HttpResponse.json({
      visit: updated,
      consultation: {
        id: updated.id,
        visitId: updated.id,
        doctorId: updated.doctorId ?? 0,
        primaryDiagnosis: "",
        cieCode: null,
        finalNote: "",
        isActive: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      },
    });
  }),

  http.post(getApiUrl("visits/:visitId/close"), ({ params }) => {
    const visitId = Number(params.visitId);
    const updated = updateVisitStatus(visitId, VISIT_STATUS.CERRADA);

    if (!updated) {
      return HttpResponse.json(
        {
          code: "VISIT_NOT_FOUND",
          message: "Visita no encontrada",
          status: 404,
        },
        { status: 404 },
      );
    }

    return HttpResponse.json({ id: updated.id, status: updated.status });
  }),
];
