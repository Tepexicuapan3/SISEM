import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { auditoriaAutorizacionesAPI } from "@api/resources/autorizaciones/auditoria.api";
import type { AuditoriaParams } from "@api/types/autorizaciones/auditoria.types";

export const auditoriaKeys = {
  all: ["admin", "autorizaciones-auditoria"] as const,
  lista: (params: AuditoriaParams) => [...auditoriaKeys.all, "lista", params] as const,
  linea: (uuid: string) => [...auditoriaKeys.all, "linea", uuid] as const,
};

export const useAuditoriaSolicitudes = (params: AuditoriaParams, enabled = true) =>
  useQuery({
    queryKey: auditoriaKeys.lista(params),
    queryFn: () => auditoriaAutorizacionesAPI.getAll(params),
    enabled,
    placeholderData: keepPreviousData,
  });

export const useLineaDeTiempo = (uuid?: string) =>
  useQuery({
    queryKey: auditoriaKeys.linea(uuid ?? ""),
    queryFn: () => auditoriaAutorizacionesAPI.getLineaDeTiempo(uuid as string),
    enabled: Boolean(uuid),
  });
