import { useQuery } from "@tanstack/react-query";
import { clinicalHistoryAPI, patientProfileAPI } from "@api/resources/clinical-history.api";

export const clinicalHistoryKeys = {
  detail: (noExp: string, pkNum: number) =>
    ["expedientes", "clinical-history", noExp, pkNum] as const,
  profile: (noExp: string, pkNum: number) =>
    ["expedientes", "patient-profile", noExp, pkNum] as const,
};

/** HISTORIA_CLINICA: cabecera (fecha/clinica/medico de apertura). */
export const useClinicalHistory = (noExp: string, pkNum = 0) => {
  return useQuery({
    queryKey: clinicalHistoryKeys.detail(noExp, pkNum),
    queryFn: () => clinicalHistoryAPI.get(noExp, pkNum),
    enabled: Boolean(noExp),
    staleTime: 60 * 1000,
  });
};

/** PACIENTE: ficha (identidad + datos sociodemograficos). */
export const usePatientProfile = (noExp: string, pkNum = 0) => {
  return useQuery({
    queryKey: clinicalHistoryKeys.profile(noExp, pkNum),
    queryFn: () => patientProfileAPI.get(noExp, pkNum),
    enabled: Boolean(noExp),
    staleTime: 60 * 1000,
  });
};
