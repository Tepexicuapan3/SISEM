import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { visitsAPI } from "@api/resources/visits.api";
import { VISIT_STATUS, type VisitStatus } from "@api/types";
import { visitFlowKeys } from "@features/recepcion/shared/queries/visit-flow.keys";
import { createVisitsRealtimeAdapter } from "@realtime/adapters/visits";
import type { RealtimeEventEnvelope } from "@realtime/protocol";

const buildEvent = (
  eventType: string,
  sequence: number,
  payload: Record<string, unknown> = { status: VISIT_STATUS.EN_CONSULTA },
): RealtimeEventEnvelope => ({
  eventId: `evt-${sequence}`,
  eventType,
  entity: "visit",
  entityId: "VIS-9001",
  version: 1,
  occurredAt: "2026-02-19T14:00:00Z",
  requestId: "req-9001",
  correlationId: "corr-9001",
  sequence,
  payload,
});

const createListResponse = () => ({
  items: [],
  page: 1,
  pageSize: 20,
  total: 0,
  totalPages: 0,
});

interface Deferred<T> {
  promise: Promise<T>;
  resolve: (value: T) => void;
}

const createDeferred = <T>(): Deferred<T> => {
  let resolve!: (value: T) => void;

  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });

  return { promise, resolve };
};

describe("createVisitsRealtimeAdapter", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const expectInvalidationForStatuses = (
    invalidateSpy: ReturnType<typeof vi.spyOn>,
    statuses: Array<VisitStatus | undefined>,
  ) => {
    for (const status of statuses) {
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: visitFlowKeys.list({ status }),
        exact: false,
      });
    }
  };

  it("status changed invalida colas origen, destino y cola general", async () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue();
    const adapter = createVisitsRealtimeAdapter({ queryClient });

    await adapter.handleEvent(
      buildEvent("visit.status.changed", 10, {
        status: VISIT_STATUS.EN_SOMATOMETRIA,
        previousStatus: VISIT_STATUS.EN_ESPERA,
      }),
    );

    expect(invalidateSpy).toHaveBeenCalledTimes(3);
    expectInvalidationForStatuses(invalidateSpy, [
      VISIT_STATUS.EN_SOMATOMETRIA,
      VISIT_STATUS.EN_ESPERA,
      undefined,
    ]);
  });

  it("transicion somatometria -> doctor invalida ambos modulos sin refresh", async () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue();
    const adapter = createVisitsRealtimeAdapter({ queryClient });

    await adapter.handleEvent(
      buildEvent("visit.status.changed", 11, {
        status: VISIT_STATUS.LISTA_PARA_DOCTOR,
        previousStatus: VISIT_STATUS.EN_SOMATOMETRIA,
      }),
    );

    expect(invalidateSpy).toHaveBeenCalledTimes(3);
    expectInvalidationForStatuses(invalidateSpy, [
      VISIT_STATUS.LISTA_PARA_DOCTOR,
      VISIT_STATUS.EN_SOMATOMETRIA,
      undefined,
    ]);
  });

  it("evento visit.created invalida cola de espera y cola general", async () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue();
    const adapter = createVisitsRealtimeAdapter({ queryClient });

    await adapter.handleEvent(
      buildEvent("visit.created", 20, {
        status: VISIT_STATUS.EN_ESPERA,
      }),
    );

    expect(invalidateSpy).toHaveBeenCalledTimes(2);
    expectInvalidationForStatuses(invalidateSpy, [
      VISIT_STATUS.EN_ESPERA,
      undefined,
    ]);
  });

  it("evento visit.no_show invalida origen, destino y cola general", async () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue();
    const adapter = createVisitsRealtimeAdapter({ queryClient });

    await adapter.handleEvent(
      buildEvent("visit.no_show", 21, {
        status: VISIT_STATUS.NO_SHOW,
        previousStatus: VISIT_STATUS.EN_ESPERA,
      }),
    );

    expect(invalidateSpy).toHaveBeenCalledTimes(3);
    expectInvalidationForStatuses(invalidateSpy, [
      VISIT_STATUS.NO_SHOW,
      VISIT_STATUS.EN_ESPERA,
      undefined,
    ]);
  });

  it("visit.cancelled desde cerrada invalida historial clinico del paciente y colas", async () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue();
    const adapter = createVisitsRealtimeAdapter({ queryClient });

    await adapter.handleEvent(
      buildEvent("visit.cancelled", 22, {
        status: VISIT_STATUS.CANCELADA,
        previousStatus: VISIT_STATUS.CERRADA,
        noteCancellationId: 9,
      }),
    );

    for (const key of [
      ["expedientes", "consultations-history"],
      ["expedientes", "medical-leaves"],
      ["expedientes", "study-results"],
    ]) {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: key });
    }
    expectInvalidationForStatuses(invalidateSpy, [
      VISIT_STATUS.CANCELADA,
      VISIT_STATUS.CERRADA,
      undefined,
    ]);
  });

  it("visit.cancelled desde otro estado NO toca el historial clinico", async () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue();
    const adapter = createVisitsRealtimeAdapter({ queryClient });

    await adapter.handleEvent(
      buildEvent("visit.cancelled", 23, {
        status: VISIT_STATUS.CANCELADA,
        previousStatus: VISIT_STATUS.EN_ESPERA,
      }),
    );

    expect(invalidateSpy).toHaveBeenCalledTimes(3);
    expect(invalidateSpy).not.toHaveBeenCalledWith({
      queryKey: ["expedientes", "consultations-history"],
    });
  });

  it("gap detection dispara resync esperado por API", async () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue();
    const getAllSpy = vi
      .spyOn(visitsAPI, "getAll")
      .mockResolvedValue(createListResponse());

    const adapter = createVisitsRealtimeAdapter({
      queryClient,
      resyncParams: {
        page: 1,
        pageSize: 20,
        status: VISIT_STATUS.EN_ESPERA,
      },
    });

    await adapter.handleGap({ expectedSequence: 21, receivedSequence: 25 });

    expect(getAllSpy).toHaveBeenCalledWith({
      page: 1,
      pageSize: 20,
      status: VISIT_STATUS.EN_ESPERA,
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
    expectInvalidationForStatuses(invalidateSpy, [
      VISIT_STATUS.EN_ESPERA,
      undefined,
    ]);
  });

  it("coalesce resync cuando gap llega con resync en vuelo", async () => {
    const queryClient = new QueryClient();
    const deferred = createDeferred<ReturnType<typeof createListResponse>>();
    const getAllSpy = vi
      .spyOn(visitsAPI, "getAll")
      .mockImplementation(() => deferred.promise);

    const adapter = createVisitsRealtimeAdapter({
      queryClient,
      resyncParams: {
        page: 1,
        pageSize: 20,
        status: VISIT_STATUS.EN_ESPERA,
      },
    });

    const firstResyncPromise = adapter.resync();
    const gapResyncPromise = adapter.handleGap({
      expectedSequence: 31,
      receivedSequence: 34,
    });

    expect(getAllSpy).toHaveBeenCalledTimes(1);

    deferred.resolve(createListResponse());
    await Promise.all([firstResyncPromise, gapResyncPromise]);

    expect(getAllSpy).toHaveBeenCalledTimes(1);
  });

  it("eventos desconocidos no rompen el flujo", async () => {
    const queryClient = new QueryClient();
    const invalidateSpy = vi
      .spyOn(queryClient, "invalidateQueries")
      .mockResolvedValue();
    const adapter = createVisitsRealtimeAdapter({ queryClient });

    await expect(
      adapter.handleEvent(buildEvent("visit.unknown", 99)),
    ).resolves.toBeUndefined();
    expect(invalidateSpy).not.toHaveBeenCalled();
  });
});
