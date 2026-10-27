import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  autorizadoresAPI,
  type AccionEstatus,
} from "@api/resources/autorizaciones/autorizadores.api";
import type {
  AutorizadorAltaRequest,
  AutorizadorDetailResponse,
  AutorizadorEdicionRequest,
  CambioEstatusRequest,
  RenovacionRequest,
} from "@api/types/autorizaciones/autorizadores.types";
import { autorizadorKeys } from "@features/admin/modules/autorizadores/queries/autorizador.keys";

/** Toda mutacion refresca listado, detalle e historial (el historial crece con cada cambio). */
const useInvalidarAutorizadores = () => {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: autorizadorKeys.all });
};

export const useCreateAutorizador = () => {
  const invalidar = useInvalidarAutorizadores();
  return useMutation<AutorizadorDetailResponse, Error, AutorizadorAltaRequest>({
    mutationFn: (data) => autorizadoresAPI.create(data),
    onSuccess: () => void invalidar(),
  });
};

export const useUpdateAutorizador = () => {
  const invalidar = useInvalidarAutorizadores();
  return useMutation<AutorizadorDetailResponse, Error, { id: number; data: AutorizadorEdicionRequest }>({
    mutationFn: ({ id, data }) => autorizadoresAPI.update(id, data),
    onSuccess: () => void invalidar(),
  });
};

export const useCambiarEstatusAutorizador = () => {
  const invalidar = useInvalidarAutorizadores();
  return useMutation<
    AutorizadorDetailResponse,
    Error,
    { id: number; accion: AccionEstatus; data: CambioEstatusRequest | { version: number } }
  >({
    mutationFn: ({ id, accion, data }) => autorizadoresAPI.cambiarEstatus(id, accion, data),
    onSuccess: () => void invalidar(),
  });
};

export const useRenovarAutorizador = () => {
  const invalidar = useInvalidarAutorizadores();
  return useMutation<AutorizadorDetailResponse, Error, { id: number; data: RenovacionRequest }>({
    mutationFn: ({ id, data }) => autorizadoresAPI.renovar(id, data),
    onSuccess: () => void invalidar(),
  });
};
