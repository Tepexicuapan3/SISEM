import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import {
  ADSCRIPCION_CAPABILITY,
  ADSCRIPCION_REQUIREMENT,
} from "@features/recepcion/modules/adscripcion/domain/adscripcion.permissions";

/** Qué puede hacer quien opera en P-03 (UX; el backend vuelve a validar). */
export const useAdscripcionPermisos = () => {
  const { hasCapability } = usePermissionDependencies();
  return {
    puedeLeer: hasCapability(ADSCRIPCION_CAPABILITY.READ, ADSCRIPCION_REQUIREMENT.READ),
    puedeAsignar: hasCapability(ADSCRIPCION_CAPABILITY.WRITE, ADSCRIPCION_REQUIREMENT.WRITE),
    puedeExcepcion: hasCapability(ADSCRIPCION_CAPABILITY.EXCEPCION, ADSCRIPCION_REQUIREMENT.EXCEPCION),
    puedeConfigurar: hasCapability(ADSCRIPCION_CAPABILITY.CONFIG, ADSCRIPCION_REQUIREMENT.CONFIG),
  };
};
