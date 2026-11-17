import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { padronesAPI } from "@api/resources/padrones.api";
import type {
  ChronicControlRegisterRequest,
  ChronicVisitEnrollRequest,
  PadronCorrectionRequest,
  PadronDischargeRequest,
  PadronEnrollRequest,
  PadronListParams,
  PadronRegistry,
} from "@api/types/padrones.types";

export const padronesKeys = {
  all: ["padrones"] as const,
  list: (registry: PadronRegistry, params: PadronListParams) =>
    [...padronesKeys.all, registry, "list", params] as const,
  options: (registry: PadronRegistry, search: string) =>
    [...padronesKeys.all, registry, "options", search] as const,
  chronicVisitNotice: (visitId: number, cie: string) =>
    [...padronesKeys.all, "cronicos", "visit-notice", visitId, cie] as const,
  chronicControlPanel: (visitId: number) =>
    [...padronesKeys.all, "cronicos", "visit-control", visitId] as const,
  family: (noExp: string) => [...padronesKeys.all, "family", noExp] as const,
  programs: () => [...padronesKeys.all, "cronicos", "programs"] as const,
  patient: (noExp: string, pkNum: number) => [...padronesKeys.all, "patient", noExp, pkNum] as const,
};

/** Padrones activos del paciente para la alerta del expediente. Sin permiso (403) la alerta no se muestra. */
export const usePatientRegistries = (noExp: string, pkNum: number) =>
  useQuery({
    queryKey: padronesKeys.patient(noExp, pkNum),
    queryFn: () => padronesAPI.patientRegistries(noExp, pkNum),
    enabled: Boolean(noExp),
    staleTime: 60 * 1000,
    retry: false,
  });

/** Programas de cronicos activos (selector del listado). */
export const usePadronPrograms = (enabled = true) =>
  useQuery({
    queryKey: padronesKeys.programs(),
    queryFn: () => padronesAPI.chronicPrograms(),
    enabled,
    staleTime: 5 * 60 * 1000,
  });

/** Miembros vigentes del expediente para elegir a quien se inscribe. Se busca al confirmar el expediente. */
export const usePadronFamily = (noExp: string) =>
  useQuery({
    queryKey: padronesKeys.family(noExp),
    queryFn: () => padronesAPI.family(noExp),
    enabled: noExp.trim().length > 0,
    retry: false,
    staleTime: 60 * 1000,
  });

/**
 * Panel de control de cronicos de la consulta (vitales de hoy contra metas).
 * `visitStatus` en la llave: al iniciar la consulta el panel se vuelve a pedir.
 */
export const useChronicControlPanel = (visitId: number, visitStatus?: string) =>
  useQuery({
    queryKey: [...padronesKeys.chronicControlPanel(visitId), visitStatus ?? null],
    queryFn: () => padronesAPI.chronicControlPanel(visitId),
    retry: false,
  });

export const useRegisterChronicControl = (visitId: number) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChronicControlRegisterRequest) => padronesAPI.registerChronicControl(visitId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: padronesKeys.chronicControlPanel(visitId) });
    },
  });
};

/** Aviso de cronicos de la consulta; `cie` es el diagnostico elegido (para la sugerencia). */
export const useChronicVisitNotice = (visitId: number, cie: string) =>
  useQuery({
    queryKey: padronesKeys.chronicVisitNotice(visitId, cie),
    queryFn: () => padronesAPI.chronicVisitNotice(visitId, cie),
    staleTime: 60 * 1000,
    // Sin permiso o sin padron el aviso simplemente no aparece: no reintentar.
    retry: false,
  });

export const useEnrollChronicFromVisit = (visitId: number) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ChronicVisitEnrollRequest) => padronesAPI.enrollChronicFromVisit(visitId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...padronesKeys.all, "cronicos"] });
    },
  });
};

export const usePadronList = (
  registry: PadronRegistry,
  params: PadronListParams,
  options: { enabled?: boolean } = {},
) =>
  useQuery({
    queryKey: padronesKeys.list(registry, params),
    queryFn: () => padronesAPI.list(registry, params),
    enabled: options.enabled ?? true,
  });

export const usePadronOptions = (registry: PadronRegistry, search: string, enabled: boolean) =>
  useQuery({
    queryKey: padronesKeys.options(registry, search),
    queryFn: () => padronesAPI.options(registry, search),
    enabled: enabled && search.trim().length >= 2,
    staleTime: 60 * 1000,
  });

export const useEnrollPadron = (registry: PadronRegistry) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PadronEnrollRequest) => padronesAPI.enroll(registry, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...padronesKeys.all, registry] });
    },
  });
};

export const useCorrectPadron = (registry: PadronRegistry) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: PadronCorrectionRequest }) =>
      padronesAPI.correct(registry, id, data),
    onSuccess: () => {
      // Tambien la alerta del expediente: cambia el padecimiento activo.
      void queryClient.invalidateQueries({ queryKey: padronesKeys.all });
    },
  });
};

export const useDischargePadron = (registry: PadronRegistry) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: PadronDischargeRequest }) =>
      padronesAPI.discharge(registry, id, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...padronesKeys.all, registry] });
    },
  });
};
