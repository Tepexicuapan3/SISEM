import apiClient from "@api/client";
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
    const response = await apiClient.get<PatientOdontogramResponse>(
      `/patients/${noExp}/odontogram`,
      { params: { pkNum, dentition, versionId: versionId ?? undefined } },
    );
    return response.data;
  },

  listVersions: async (noExp: string, pkNum = 0): Promise<OdontogramVersionsResponse> => {
    const response = await apiClient.get<OdontogramVersionsResponse>(
      `/patients/${noExp}/odontogram/versions`,
      { params: { pkNum } },
    );
    return response.data;
  },

  updateTooth: async (
    noExp: string,
    pkNum: number,
    toothFdi: string,
    data: UpdateOdontogramToothRequest,
  ): Promise<UpdateOdontogramToothResponse> => {
    const response = await apiClient.patch<UpdateOdontogramToothResponse>(
      `/patients/${noExp}/odontogram/${toothFdi}`,
      data,
      { params: { pkNum } },
    );
    return response.data;
  },
};
