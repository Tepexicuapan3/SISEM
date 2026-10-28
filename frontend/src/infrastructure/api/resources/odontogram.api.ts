import apiClient from "@api/client";
import { rutaPaciente } from "@api/paciente-ids";
import type {
  OdontogramDentition,
  OdontogramVersionsResponse,
  PatientOdontogramResponse,
  UpdateOdontogramToothRequest,
  UpdateOdontogramToothResponse,
} from "@api/types/odontogram.types";

export const odontogramAPI = {
  get: async (
    noExp: string,
    pkNum = 0,
    dentition: OdontogramDentition = "permanent",
    versionId?: number | null,
  ): Promise<PatientOdontogramResponse> => {
    const ruta = await rutaPaciente(noExp, pkNum, `odontogram`);
    const response = await apiClient.get<PatientOdontogramResponse>(
      ruta.url,
      { params: { ...ruta.params, dentition, versionId: versionId ?? undefined } },
    );
    return response.data;
  },

  listVersions: async (noExp: string, pkNum = 0): Promise<OdontogramVersionsResponse> => {
    const ruta = await rutaPaciente(noExp, pkNum, `odontogram/versions`);
    const response = await apiClient.get<OdontogramVersionsResponse>(
      ruta.url,
      { params: ruta.params },
    );
    return response.data;
  },

  updateTooth: async (
    noExp: string,
    pkNum: number,
    toothFdi: string,
    data: UpdateOdontogramToothRequest,
  ): Promise<UpdateOdontogramToothResponse> => {
    const ruta = await rutaPaciente(noExp, pkNum, `odontogram/${toothFdi}`);
    const response = await apiClient.patch<UpdateOdontogramToothResponse>(
      ruta.url,
      data,
      { params: ruta.params },
    );
    return response.data;
  },
};
