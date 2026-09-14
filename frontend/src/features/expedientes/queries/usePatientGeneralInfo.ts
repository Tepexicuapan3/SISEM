import { useQuery } from "@tanstack/react-query";
import { visitsAPI } from "@api/resources/visits.api";

export const patientGeneralInfoKeys = {
  detail: (noExp: string) => ["expedientes", "patient-general-info", noExp] as const,
};

/**
 * Datos generales reales del paciente (nombre, edad, fecha de nacimiento,
 * estatus) via el mismo lookup ya usado en Recepcion (`/visits/patient-lookup`,
 * historico=true para incluir pacientes de baja). No trae CURP/sexo/tipo de
 * sangre/telefono/email/direccion -- esos campos no tienen fuente real en el
 * backend todavia (ver ExpedienteDetailPage.tsx).
 */
export const usePatientGeneralInfo = (noExp: string) => {
  return useQuery({
    queryKey: patientGeneralInfoKeys.detail(noExp),
    queryFn: () => visitsAPI.patientLookup(noExp, true),
    enabled: Boolean(noExp),
    staleTime: 60 * 1000,
  });
};
