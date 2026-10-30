import { useMutation, useQueryClient } from "@tanstack/react-query";
import { adscripcionAPI } from "@api/resources/adscripcion.api";
import { visitsAPI } from "@api/resources/visits.api";
import { citasAPI } from "@api/resources/citas.api";
import type { AdscribirRequest, CreateCitaRequest, PrevisualizarAdscripcionRequest } from "@api/types";
import { ADSCRIPCION_KEYS } from "@features/recepcion/modules/adscripcion/queries/useAdscripcionQueries";

const PATIENT_LOOKUP_KEY = "patient-lookup";

/** El miembro que nunca se atendió no tiene idPaciente: se abre su registro. */
export const useAbrirPaciente = () =>
  useMutation({
    mutationFn: ({ noExp, pkNum }: { noExp: string; pkNum: number }) => visitsAPI.openPatient(noExp, pkNum),
  });

/** Qué pasaría al adscribir (citas que se cancelarían); no escribe nada. */
export const usePrevisualizarAdscripcion = () =>
  useMutation({
    mutationFn: (data: PrevisualizarAdscripcionRequest) => adscripcionAPI.previsualizar(data),
  });

/** Adscribe o reasigna; refresca la búsqueda del expediente y lo de P-03. */
export const useAdscribir = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AdscribirRequest) => adscripcionAPI.adscribir(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [PATIENT_LOOKUP_KEY] });
      void queryClient.invalidateQueries({ queryKey: ADSCRIPCION_KEYS.all });
    },
  });
};

/** Crea la cita nueva y marca la afectada como reagendada (misma transacción). */
export const useReagendarCita = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateCitaRequest) => citasAPI.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ADSCRIPCION_KEYS.all });
      void queryClient.invalidateQueries({ queryKey: ["agenda-semanal"] });
    },
  });
};

export const useDescartarCitaAfectada = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ idCitaAfectada, motivo }: { idCitaAfectada: number; motivo: string }) =>
      adscripcionAPI.descartarCitaAfectada(idCitaAfectada, motivo),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ADSCRIPCION_KEYS.all });
    },
  });
};
