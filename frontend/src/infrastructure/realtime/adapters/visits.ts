import type { QueryClient } from "@tanstack/react-query";

import { visitsAPI } from "@api/resources/visits.api";
import {
  VISIT_STATUS,
  type VisitStatus,
  type VisitsListParams,
} from "@api/types";
import { visitFlowKeys } from "@realtime/streams/visits/query-keys";
import type { RealtimeSequenceGap } from "@realtime/core/client";
import type { RealtimeEventEnvelope } from "@realtime/core/protocol";
import type { RealtimeFeatureSubscriptions } from "@realtime/core/subscriptions";

export const VISITS_REALTIME_ADAPTER = {
  FEATURE: "visits",
} as const;

export const VISITS_REALTIME_EVENT_TYPE = {
  VISIT_CREATED: "visit.created",
  VISIT_STATUS_CHANGED: "visit.status.changed",
  VISIT_CANCELLED: "visit.cancelled",
  VISIT_NO_SHOW: "visit.no_show",
  VISIT_CLOSED: "visit.closed",
} as const;

const VISIT_STATUS_SET = new Set<VisitStatus>(Object.values(VISIT_STATUS));

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null;
};

const isVisitStatus = (value: unknown): value is VisitStatus => {
  return (
    typeof value === "string" && VISIT_STATUS_SET.has(value as VisitStatus)
  );
};

const addUniqueStatus = (
  statuses: Array<VisitStatus | undefined>,
  status: VisitStatus | undefined,
): void => {
  if (statuses.some((candidate) => candidate === status)) {
    return;
  }

  statuses.push(status);
};

const resolveEventStatuses = (
  event: RealtimeEventEnvelope,
): Array<VisitStatus | undefined> => {
  const affected: Array<VisitStatus | undefined> = [];
  const payload = isRecord(event.payload) ? event.payload : {};

  const status = isVisitStatus(payload.status) ? payload.status : undefined;
  const previousStatus = isVisitStatus(payload.previousStatus)
    ? payload.previousStatus
    : undefined;

  addUniqueStatus(affected, undefined);

  switch (event.eventType) {
    case VISITS_REALTIME_EVENT_TYPE.VISIT_CREATED:
      addUniqueStatus(affected, status ?? VISIT_STATUS.EN_ESPERA);
      return affected;

    case VISITS_REALTIME_EVENT_TYPE.VISIT_STATUS_CHANGED:
    case VISITS_REALTIME_EVENT_TYPE.VISIT_CANCELLED:
    case VISITS_REALTIME_EVENT_TYPE.VISIT_NO_SHOW:
      addUniqueStatus(affected, status);
      addUniqueStatus(affected, previousStatus);
      return affected;

    case VISITS_REALTIME_EVENT_TYPE.VISIT_CLOSED:
      addUniqueStatus(affected, status ?? VISIT_STATUS.CERRADA);
      addUniqueStatus(affected, VISIT_STATUS.EN_CONSULTA);
      return affected;

    default:
      return [];
  }
};

interface CreateVisitsRealtimeAdapterOptions {
  queryClient: QueryClient;
  resyncParams?: VisitsListParams;
}

export interface VisitsRealtimeAdapter {
  subscriptions: RealtimeFeatureSubscriptions;
  handleEvent: (event: RealtimeEventEnvelope) => Promise<void>;
  handleGap: (gap: RealtimeSequenceGap) => Promise<void>;
  resync: () => Promise<void>;
}

export const createVisitsRealtimeAdapter = (
  options: CreateVisitsRealtimeAdapterOptions,
): VisitsRealtimeAdapter => {
  const { queryClient, resyncParams } = options;
  let resyncInFlight: Promise<void> | null = null;

  const invalidateStatusQueues = async (
    statuses: Array<VisitStatus | undefined>,
  ): Promise<void> => {
    const normalizedStatuses: Array<VisitStatus | undefined> = [];

    for (const status of statuses) {
      addUniqueStatus(normalizedStatuses, status);
    }

    await Promise.all(
      normalizedStatuses.map(async (status) => {
        await queryClient.invalidateQueries({
          queryKey: visitFlowKeys.list({ status }),
          exact: false,
        });
      }),
    );
  };

  const resync = async (): Promise<void> => {
    if (resyncInFlight) {
      return resyncInFlight;
    }

    resyncInFlight = (async () => {
      await visitsAPI.getAll(resyncParams);
      await invalidateStatusQueues([resyncParams?.status, undefined]);
    })().finally(() => {
      resyncInFlight = null;
    });

    return resyncInFlight;
  };

  const handleEvent = async (event: RealtimeEventEnvelope): Promise<void> => {
    if (event.entity !== "visit") {
      return;
    }

    const statusesToInvalidate = resolveEventStatuses(event);
    if (statusesToInvalidate.length === 0) {
      return;
    }

    await invalidateStatusQueues(statusesToInvalidate);
  };

  const subscriptions: RealtimeFeatureSubscriptions = {
    feature: VISITS_REALTIME_ADAPTER.FEATURE,
    eventHandlers: {
      [VISITS_REALTIME_EVENT_TYPE.VISIT_CREATED]: (event) => {
        void handleEvent(event);
      },
      [VISITS_REALTIME_EVENT_TYPE.VISIT_STATUS_CHANGED]: (event) => {
        void handleEvent(event);
      },
      [VISITS_REALTIME_EVENT_TYPE.VISIT_CANCELLED]: (event) => {
        void handleEvent(event);
      },
      [VISITS_REALTIME_EVENT_TYPE.VISIT_NO_SHOW]: (event) => {
        void handleEvent(event);
      },
      [VISITS_REALTIME_EVENT_TYPE.VISIT_CLOSED]: (event) => {
        void handleEvent(event);
      },
    },
  };

  const handleGap = async (): Promise<void> => {
    await resync();
  };

  return {
    subscriptions,
    handleEvent,
    handleGap,
    resync,
  };
};
