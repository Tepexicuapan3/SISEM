import { Stethoscope } from "lucide-react";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { EquivalenciasSection } from "@features/admin/modules/catalogos/consultorio-familiar/components/EquivalenciasSection";
import { ConsultoriosFamiliaresSection } from "@features/admin/modules/catalogos/consultorio-familiar/components/ConsultoriosFamiliaresSection";
import {
  ADSCRIPCION_CAPABILITY,
  ADSCRIPCION_REQUIREMENT,
} from "@features/recepcion/modules/adscripcion/domain/adscripcion.permissions";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";

/** P-03 · Configuración de la asignación de consultorio familiar. */
export function ConsultorioFamiliarConfigPage() {
  const { hasCapability } = usePermissionDependencies();
  const puedeConfigurar = hasCapability(ADSCRIPCION_CAPABILITY.CONFIG, ADSCRIPCION_REQUIREMENT.CONFIG);

  const { data: centrosData } = useCentrosAtencionList(
    { isActive: true, pageSize: 500, sortBy: "name", sortOrder: "asc" },
    { enabled: puedeConfigurar },
  );
  const centros = centrosData?.items ?? [];

  return (
    <CatalogModuleLayout
      title="Consultorio familiar"
      description="Equivalencias entre la clínica de SERMED y los centros de SIRES, y consultorios que reciben pacientes adscritos."
      icon={<Stethoscope className="size-12" />}
    >
      {!puedeConfigurar ? (
        <AdminReadOnlyNotice message="No tienes acceso para configurar el consultorio familiar." />
      ) : (
        <>
          <EquivalenciasSection centros={centros} />
          <ConsultoriosFamiliaresSection centros={centros} />
        </>
      )}
    </CatalogModuleLayout>
  );
}

export default ConsultorioFamiliarConfigPage;
