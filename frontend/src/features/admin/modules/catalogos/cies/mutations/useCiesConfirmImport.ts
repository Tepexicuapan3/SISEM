import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ciesAPI, type CiesUploadRow } from "@api/resources/catalogos/cies.api";
import { ciesKeys } from "@features/admin/modules/catalogos/cies/queries/cies.keys";

export const useCiesConfirmImport = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (rows: CiesUploadRow[]) => ciesAPI.confirm(rows),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ciesKeys.all });
    },
  });
};
