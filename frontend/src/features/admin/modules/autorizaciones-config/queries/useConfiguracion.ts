import { useQuery } from "@tanstack/react-query";
import { configuracionAutorizacionesAPI } from "@api/resources/autorizaciones/configuracion.api";
import type { AmbitoMotivo } from "@api/types/autorizaciones/configuracion.types";
import { configuracionKeys } from "@features/admin/modules/autorizaciones-config/queries/configuracion.keys";

export const useTiposConfiguracion = (enabled = true) =>
  useQuery({ queryKey: configuracionKeys.tipos(), queryFn: configuracionAutorizacionesAPI.getTipos, enabled });

export const useReglasCentro = (enabled = true) =>
  useQuery({ queryKey: configuracionKeys.reglas(), queryFn: configuracionAutorizacionesAPI.getReglas, enabled });

export const useMotivosConfiguracion = (ambito?: AmbitoMotivo, enabled = true) =>
  useQuery({
    queryKey: configuracionKeys.motivos(ambito),
    queryFn: () => configuracionAutorizacionesAPI.getMotivos(ambito),
    enabled,
  });
