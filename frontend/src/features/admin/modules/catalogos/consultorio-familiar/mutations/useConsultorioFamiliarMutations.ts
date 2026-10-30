import { useMutation, useQueryClient } from "@tanstack/react-query";
import { adscripcionAPI } from "@api/resources/adscripcion.api";
import type {
  ConsultorioFamiliarCreateRequest,
  ConsultorioFamiliarUpdateRequest,
  EquivalenciaClinicaCreateRequest,
  EquivalenciaClinicaUpdateRequest,
} from "@api/types";
import { CONSULTORIO_FAMILIAR_CONFIG_KEYS } from "@features/admin/modules/catalogos/consultorio-familiar/queries/useConsultorioFamiliarConfig";

const useInvalidarConfig = () => {
  const queryClient = useQueryClient();
  return () => void queryClient.invalidateQueries({ queryKey: CONSULTORIO_FAMILIAR_CONFIG_KEYS.all });
};

export const useCrearEquivalencia = () => {
  const invalidar = useInvalidarConfig();
  return useMutation({
    mutationFn: (data: EquivalenciaClinicaCreateRequest) => adscripcionAPI.crearEquivalencia(data),
    onSuccess: invalidar,
  });
};

export const useActualizarEquivalencia = () => {
  const invalidar = useInvalidarConfig();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: EquivalenciaClinicaUpdateRequest }) =>
      adscripcionAPI.actualizarEquivalencia(id, data),
    onSuccess: invalidar,
  });
};

export const useCrearConsultorioFamiliar = () => {
  const invalidar = useInvalidarConfig();
  return useMutation({
    mutationFn: (data: ConsultorioFamiliarCreateRequest) => adscripcionAPI.crearConsultorioFamiliar(data),
    onSuccess: invalidar,
  });
};

export const useActualizarConsultorioFamiliar = () => {
  const invalidar = useInvalidarConfig();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ConsultorioFamiliarUpdateRequest }) =>
      adscripcionAPI.actualizarConsultorioFamiliar(id, data),
    onSuccess: invalidar,
  });
};
