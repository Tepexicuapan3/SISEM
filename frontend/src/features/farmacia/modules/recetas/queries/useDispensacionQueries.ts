import { useQuery } from "@tanstack/react-query";
import { dispensacionFarmaciaAPI } from "@api/resources/farmacia/dispensacion.api";
import type { DispensationQueueParams } from "@api/types";
import { dispensacionKeys } from "./dispensacion.keys";

interface Options { enabled?: boolean }

export function useDispensationQueue(params?: DispensationQueueParams, opts: Options = {}) {
  return useQuery({
    queryKey: dispensacionKeys.queueList(params),
    queryFn: () => dispensacionFarmaciaAPI.getPendingQueue(params),
    enabled: opts.enabled ?? true,
    staleTime: 15_000,
  });
}

export function useDispensationPreview(prescriptionId: number | null, opts: Options = {}) {
  return useQuery({
    queryKey: dispensacionKeys.preview(prescriptionId ?? 0),
    queryFn: () => dispensacionFarmaciaAPI.getPreview(prescriptionId as number),
    enabled: (opts.enabled ?? true) && prescriptionId !== null,
  });
}
