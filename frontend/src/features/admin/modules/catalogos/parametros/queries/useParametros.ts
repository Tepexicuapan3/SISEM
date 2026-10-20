import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { parametersAPI } from "@api/resources/catalogos/parameters.api";
import type { ParametroDetailResponse } from "@api/types/catalogos/parameters.types";
import { createCatalogKeys } from "@features/admin/modules/catalogos/shared/queries/createCatalogKeys";

// Lista completa sin paginar: son pocos parametros y se agregan por codigo.
export const parametroKeys = createCatalogKeys<undefined, string>(["admin", "parametros"]);

export const useParametrosList = (options: { enabled?: boolean } = {}) =>
  useQuery({
    queryKey: parametroKeys.list(),
    queryFn: parametersAPI.getAll,
    enabled: options.enabled ?? true,
  });

interface GeneralPayload {
  key: string;
  value: string;
}

interface CenterPayload extends GeneralPayload {
  centerId: number;
}

const useInvalidatingMutation = <TPayload>(
  mutationFn: (payload: TPayload) => Promise<ParametroDetailResponse>,
) => {
  const queryClient = useQueryClient();
  return useMutation<ParametroDetailResponse, Error, TPayload>({
    mutationFn,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: parametroKeys.all });
    },
  });
};

export const useUpdateParametroGeneral = () =>
  useInvalidatingMutation<GeneralPayload>(({ key, value }) =>
    parametersAPI.updateGeneral(key, value),
  );

export const useSetParametroCentro = () =>
  useInvalidatingMutation<CenterPayload>(({ key, centerId, value }) =>
    parametersAPI.setCenterValue(key, centerId, value),
  );

export const useDeleteParametroCentro = () =>
  useInvalidatingMutation<Omit<CenterPayload, "value">>(({ key, centerId }) =>
    parametersAPI.deleteCenterValue(key, centerId),
  );
