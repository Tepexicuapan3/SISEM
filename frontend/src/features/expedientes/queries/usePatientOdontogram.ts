import { useQuery } from "@tanstack/react-query";
import { odontogramAPI } from "@api/resources/odontogram.api";
import type { OdontogramDentition } from "@api/types";

export const odontogramKeys = {
  /** Prefijo comun: invalidarlo refresca todas las vistas del paciente. */
  patient: (noExp: string, pkNum: number) => ["expedientes", "odontogram", noExp, pkNum] as const,
  detail: (noExp: string, pkNum: number, dentition: OdontogramDentition, versionId: number | null) =>
    ["expedientes", "odontogram", noExp, pkNum, dentition, versionId ?? "latest"] as const,
  versions: (noExp: string, pkNum: number) =>
    ["expedientes", "odontogram", noExp, pkNum, "versions"] as const,
};

/** `versionId` null = version vigente (la ultima). */
export const usePatientOdontogram = (
  noExp: string,
  pkNum = 0,
  dentition: OdontogramDentition = "permanent",
  versionId: number | null = null,
) => {
  return useQuery({
    queryKey: odontogramKeys.detail(noExp, pkNum, dentition, versionId),
    queryFn: () => odontogramAPI.get(noExp, pkNum, dentition, versionId),
    enabled: Boolean(noExp),
    staleTime: 30 * 1000,
  });
};

export const useOdontogramVersions = (noExp: string, pkNum = 0) =>
  useQuery({
    queryKey: odontogramKeys.versions(noExp, pkNum),
    queryFn: () => odontogramAPI.listVersions(noExp, pkNum),
    enabled: Boolean(noExp),
    staleTime: 30 * 1000,
  });
