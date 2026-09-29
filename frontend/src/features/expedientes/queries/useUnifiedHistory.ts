import { useQuery } from "@tanstack/react-query";
import {
  clinicalCatalogsAPI,
  historicalNotesAPI,
  patientRecordsAPI,
} from "@api/resources/unified-history.api";
import type { PatientRecordResource } from "@api/types";

export const unifiedHistoryKeys = {
  catalogs: ["expedientes", "clinical-catalogs"] as const,
  records: (resource: PatientRecordResource, noExp: string, pkNum: number) =>
    ["expedientes", "records", resource, noExp, pkNum] as const,
  historicalNotes: (noExp: string, pkNum: number, specialty?: string) =>
    ["expedientes", "historical-notes", noExp, pkNum, specialty ?? "all"] as const,
};

/** Catalogos clinicos (habitos, regiones, estados de pieza, piezas FDI,
 * parentescos): cambian muy poco, se cachean largo. */
export const useClinicalCatalogs = () =>
  useQuery({
    queryKey: unifiedHistoryKeys.catalogs,
    queryFn: () => clinicalCatalogsAPI.get(),
    staleTime: 30 * 60 * 1000,
  });

export const usePatientRecords = <T>(resource: PatientRecordResource, noExp: string, pkNum = 0) =>
  useQuery({
    queryKey: unifiedHistoryKeys.records(resource, noExp, pkNum),
    queryFn: () => patientRecordsAPI.list<T>(resource, noExp, pkNum),
    enabled: Boolean(noExp),
    staleTime: 60 * 1000,
  });

export const useHistoricalNotes = (noExp: string, pkNum = 0, specialty?: "general" | "stomatology") =>
  useQuery({
    queryKey: unifiedHistoryKeys.historicalNotes(noExp, pkNum, specialty),
    queryFn: () => historicalNotesAPI.list(noExp, pkNum, specialty ? { specialty } : {}),
    enabled: Boolean(noExp),
    staleTime: 5 * 60 * 1000,
  });
