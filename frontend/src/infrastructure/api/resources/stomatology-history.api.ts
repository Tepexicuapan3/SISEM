import apiClient from "@api/client";
import { rutaPaciente } from "@api/paciente-ids";
import type {
  StomatologyHistory,
  UpdateStomatologyHistoryRequest,
} from "@api/types/stomatology-history.types";

export const stomatologyHistoryAPI = {
  get: async (noExp: string, pkNum = 0): Promise<StomatologyHistory> => {
    const ruta = await rutaPaciente(noExp, pkNum, `stomatology-history`);
    const response = await apiClient.get<StomatologyHistory>(
      ruta.url,
      { params: ruta.params },
    );
    return response.data;
  },

  update: async (
    noExp: string,
    pkNum: number,
    data: UpdateStomatologyHistoryRequest,
  ): Promise<StomatologyHistory> => {
    const ruta = await rutaPaciente(noExp, pkNum, `stomatology-history`);
    const response = await apiClient.patch<StomatologyHistory>(
      ruta.url,
      data,
      { params: ruta.params },
    );
    return response.data;
  },
};
