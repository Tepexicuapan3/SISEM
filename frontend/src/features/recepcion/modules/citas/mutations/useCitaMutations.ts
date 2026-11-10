import { useMutation, useQueryClient } from "@tanstack/react-query";
import { citasAPI } from "@api/resources/citas.api";
import type { CreateCitaRequest, ReprogramarCitaRequest, UpdateEstatusCitaRequest } from "@api/types";
import { CITAS_KEYS } from "@features/recepcion/modules/citas/queries/useCitasList";

const AGENDA_KEY = ["agenda-semanal"] as const;

export const useUpdateEstatusCita = (id: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateEstatusCitaRequest) => citasAPI.updateEstatus(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CITAS_KEYS.all });
      qc.invalidateQueries({ queryKey: AGENDA_KEY });
    },
  });
};

/** Cita del seguimiento que indicó el médico: al crearse sale de la lista (CITAS_KEYS la incluye). */
export const useAgendarSeguimiento = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateCitaRequest) => citasAPI.create(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CITAS_KEYS.all });
      qc.invalidateQueries({ queryKey: AGENDA_KEY });
    },
  });
};

export const useReprogramarCita = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: ReprogramarCitaRequest & { id: number }) => citasAPI.reprogramar(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CITAS_KEYS.all });
      qc.invalidateQueries({ queryKey: AGENDA_KEY });
    },
  });
};
