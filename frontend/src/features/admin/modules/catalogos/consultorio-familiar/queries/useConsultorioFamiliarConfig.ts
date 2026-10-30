import { useQuery } from "@tanstack/react-query";
import { adscripcionAPI } from "@api/resources/adscripcion.api";

export const CONSULTORIO_FAMILIAR_CONFIG_KEYS = {
  all: ["adscripcion-config"] as const,
  equivalencias: () => [...CONSULTORIO_FAMILIAR_CONFIG_KEYS.all, "equivalencias"] as const,
  consultorios: (centroId: number | null) => [...CONSULTORIO_FAMILIAR_CONFIG_KEYS.all, "consultorios", centroId] as const,
};

/** P-03 · Clave de clínica SERMED → centro de atención de SIRES. */
export const useEquivalenciasClinica = (enabled: boolean) =>
  useQuery({
    queryKey: CONSULTORIO_FAMILIAR_CONFIG_KEYS.equivalencias(),
    queryFn: () => adscripcionAPI.getEquivalencias(),
    enabled,
  });

/** P-03 · Consultorios de medicina general habilitados como familiares en un centro, con su carga. */
export const useConsultoriosFamiliaresConfig = (centroId: number | null, enabled: boolean) =>
  useQuery({
    queryKey: CONSULTORIO_FAMILIAR_CONFIG_KEYS.consultorios(centroId),
    queryFn: () => adscripcionAPI.getConsultoriosFamiliares(centroId ?? undefined),
    enabled: enabled && centroId != null,
  });
