import { useQuery } from "@tanstack/react-query";
import { autorizadoresAPI } from "@api/resources/autorizaciones/autorizadores.api";
import type {
  AutorizadoresListParams,
  AutorizadoresListResponse,
} from "@api/types/autorizaciones/autorizadores.types";
import { autorizadorKeys } from "@features/admin/modules/autorizadores/queries/autorizador.keys";
import { createCatalogListHook } from "@features/admin/modules/catalogos/shared/queries/createCatalogListHook";

export const useAutorizadoresList = createCatalogListHook<
  AutorizadoresListParams,
  AutorizadoresListResponse
>({
  keys: autorizadorKeys,
  getAll: autorizadoresAPI.getAll,
});

export const useAutorizadorDetail = (id?: number, enabled = true) =>
  useQuery({
    queryKey: autorizadorKeys.detail(id ?? 0),
    queryFn: () => autorizadoresAPI.getById(id as number),
    enabled: enabled && Boolean(id),
    staleTime: 30 * 1000,
  });

export const useAutorizadorHistorial = (id?: number, enabled = true) =>
  useQuery({
    queryKey: autorizadorKeys.historial(id ?? 0),
    queryFn: () => autorizadoresAPI.getHistorial(id as number),
    enabled: enabled && Boolean(id),
  });

export const useUsuariosElegibles = (search: string, enabled = true) =>
  useQuery({
    queryKey: autorizadorKeys.usuariosElegibles(search),
    queryFn: () => autorizadoresAPI.getUsuariosElegibles(search || undefined),
    enabled,
    staleTime: 30 * 1000,
  });

/** Tipos de autorizacion y motivos: cambian poco, se cachean mas tiempo. */
export const useCatalogosAutorizacion = (enabled = true) =>
  useQuery({
    queryKey: autorizadorKeys.catalogos(),
    queryFn: autorizadoresAPI.getCatalogos,
    enabled,
    staleTime: 10 * 60 * 1000,
  });
