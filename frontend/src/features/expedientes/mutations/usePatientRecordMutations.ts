import { useMutation, useQueryClient } from "@tanstack/react-query";
import { patientRecordsAPI } from "@api/resources/unified-history.api";
import type { PatientRecordResource } from "@api/types";
import { unifiedHistoryKeys } from "@features/expedientes/queries/useUnifiedHistory";

interface Target {
  resource: PatientRecordResource;
  noExp: string;
  pkNum: number;
}

/** Alta / edicion / baja (con motivo) de un registro permanente. */
export const usePatientRecordMutations = ({ resource, noExp, pkNum }: Target) => {
  const queryClient = useQueryClient();
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: unifiedHistoryKeys.records(resource, noExp, pkNum) });

  const create = useMutation({
    mutationFn: (data: object) => patientRecordsAPI.create(resource, noExp, pkNum, data),
    onSuccess: invalidate,
  });
  const update = useMutation({
    mutationFn: ({ recordId, data }: { recordId: number; data: object }) =>
      patientRecordsAPI.update(resource, noExp, pkNum, recordId, data),
    onSuccess: invalidate,
  });
  const deactivate = useMutation({
    mutationFn: ({ recordId, reason }: { recordId: number; reason: string }) =>
      patientRecordsAPI.deactivate(resource, noExp, pkNum, recordId, reason),
    onSuccess: invalidate,
  });

  return { create, update, deactivate };
};
