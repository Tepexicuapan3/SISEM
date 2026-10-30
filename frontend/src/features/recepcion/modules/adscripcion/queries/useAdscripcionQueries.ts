import { useQuery } from "@tanstack/react-query";
import { adscripcionAPI } from "@api/resources/adscripcion.api";
import { citasAPI } from "@api/resources/citas.api";
import type { CitasPorReagendarParams } from "@api/types";

export const ADSCRIPCION_KEYS = {
  all: ["adscripcion"] as const,
  opciones: (idPaciente: number | null, turnoId?: number) =>
    ["adscripcion", "opciones", idPaciente, turnoId ?? null] as const,
  citasPorReagendar: (params: CitasPorReagendarParams) =>
    ["adscripcion", "citas-por-reagendar", params.idPaciente ?? null, params.centroId ?? null] as const,
  equivalencias: ["adscripcion", "config", "clinicas"] as const,
  consultorios: (centroId?: number) => ["adscripcion", "config", "consultorios", centroId ?? null] as const,
};

/** Consultorios elegibles para la persona, con la sugerida marcada (S0 a S6). */
export const useOpcionesAdscripcion = (idPaciente: number | null, turnoId?: number) =>
  useQuery({
    queryKey: ADSCRIPCION_KEYS.opciones(idPaciente, turnoId),
    queryFn: () => adscripcionAPI.getOpciones(idPaciente as number, turnoId),
    enabled: idPaciente != null,
    staleTime: 0,
  });

/**
 * Citas canceladas por un cambio de consultorio, pendientes de reagendar.
 * Sin filtros: las del centro de quien opera.
 */
export const useCitasPorReagendar = (params: CitasPorReagendarParams = {}, enabled = true) =>
  useQuery({
    queryKey: ADSCRIPCION_KEYS.citasPorReagendar(params),
    queryFn: () => adscripcionAPI.getCitasPorReagendar(params),
    enabled,
    staleTime: 30_000,
  });

/** Horarios libres de un médico en una fecha (para reagendar). */
export const useSlotsMedico = (medicoId: number | null, fecha: string) =>
  useQuery({
    queryKey: ["adscripcion", "slots", medicoId, fecha] as const,
    queryFn: () => citasAPI.getSlots({ medicoId: medicoId as number, fecha }),
    enabled: medicoId != null && fecha.length > 0,
    staleTime: 0,
  });
