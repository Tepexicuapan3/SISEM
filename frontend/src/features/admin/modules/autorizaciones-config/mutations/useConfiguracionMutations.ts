import { useMutation, useQueryClient } from "@tanstack/react-query";
import { configuracionAutorizacionesAPI } from "@api/resources/autorizaciones/configuracion.api";
import type {
  MotivoAltaRequest,
  MotivoEdicionRequest,
  ReglaCentroAltaRequest,
  ReglaCentroEdicionRequest,
  TipoEdicionRequest,
} from "@api/types/autorizaciones/configuracion.types";
import { configuracionKeys } from "@features/admin/modules/autorizaciones-config/queries/configuracion.keys";
import { autorizadorKeys } from "@features/admin/modules/autorizadores/queries/autorizador.keys";

/** Toda mutacion refresca la configuracion y los catalogos que usa la pantalla de autorizadores. */
const useInvalidar = () => {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: configuracionKeys.all }),
      queryClient.invalidateQueries({ queryKey: autorizadorKeys.catalogos() }),
    ]);
};

export const useUpdateTipo = () => {
  const invalidar = useInvalidar();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TipoEdicionRequest }) =>
      configuracionAutorizacionesAPI.updateTipo(id, data),
    onSuccess: () => void invalidar(),
  });
};

export const useCreateRegla = () => {
  const invalidar = useInvalidar();
  return useMutation({
    mutationFn: (data: ReglaCentroAltaRequest) => configuracionAutorizacionesAPI.createRegla(data),
    onSuccess: () => void invalidar(),
  });
};

export const useUpdateRegla = () => {
  const invalidar = useInvalidar();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ReglaCentroEdicionRequest }) =>
      configuracionAutorizacionesAPI.updateRegla(id, data),
    onSuccess: () => void invalidar(),
  });
};

export const useBajaRegla = () => {
  const invalidar = useInvalidar();
  return useMutation({
    mutationFn: ({ id, version }: { id: number; version: number }) =>
      configuracionAutorizacionesAPI.bajaRegla(id, version),
    onSuccess: () => void invalidar(),
  });
};

export const useCreateMotivo = () => {
  const invalidar = useInvalidar();
  return useMutation({
    mutationFn: (data: MotivoAltaRequest) => configuracionAutorizacionesAPI.createMotivo(data),
    onSuccess: () => void invalidar(),
  });
};

export const useUpdateMotivo = () => {
  const invalidar = useInvalidar();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: MotivoEdicionRequest }) =>
      configuracionAutorizacionesAPI.updateMotivo(id, data),
    onSuccess: () => void invalidar(),
  });
};
