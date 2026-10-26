import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { expedientesAPI } from "@api/resources/expedientes.api";
import type { RegistrarRecienNacidoRequest } from "@api/types/expedientes.types";
import { expedientesKeys } from "./expedientes.keys";

/** Recien nacidos provisionales del titular y sus candidatos de SERMED. */
export const useRecienNacidos = (noExp: string) =>
  useQuery({
    queryKey: expedientesKeys.recienNacidos(noExp),
    queryFn: () => expedientesAPI.recienNacidos(noExp),
    enabled: noExp.trim().length > 0,
    staleTime: 30 * 1000,
  });

const useInvalidar = (noExp: string) => {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: expedientesKeys.recienNacidos(noExp) });
    queryClient.invalidateQueries({ queryKey: expedientesKeys.detail(noExp) });
  };
};

export const useRegistrarRecienNacido = (noExp: string) => {
  const invalidar = useInvalidar(noExp);
  return useMutation({
    mutationFn: (data: RegistrarRecienNacidoRequest) => expedientesAPI.registrarRecienNacido(noExp, data),
    onSuccess: invalidar,
  });
};

export const useVincularRecienNacido = (noExp: string) => {
  const invalidar = useInvalidar(noExp);
  return useMutation({
    mutationFn: ({ idPaciente, pkNum }: { idPaciente: number; pkNum: number }) =>
      expedientesAPI.vincularRecienNacido(idPaciente, pkNum),
    onSuccess: invalidar,
  });
};

export const useDescartarCoincidencia = (noExp: string) => {
  const invalidar = useInvalidar(noExp);
  return useMutation({
    mutationFn: ({ idPaciente, pkNum, motivo }: { idPaciente: number; pkNum: number; motivo?: string }) =>
      expedientesAPI.descartarCoincidencia(idPaciente, pkNum, motivo),
    onSuccess: invalidar,
  });
};

export const useExtenderVigenciaRecienNacido = (noExp: string) => {
  const invalidar = useInvalidar(noExp);
  return useMutation({
    mutationFn: ({ idPaciente, motivo }: { idPaciente: number; motivo?: string }) =>
      expedientesAPI.extenderVigenciaRecienNacido(idPaciente, motivo),
    onSuccess: invalidar,
  });
};
