import { Settings } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@shared/ui/tabs";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { CatalogModuleLayout } from "@features/admin/modules/catalogos/shared/components/CatalogModuleLayout";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { MotivosTab } from "@features/admin/modules/autorizaciones-config/components/MotivosTab";
import { ReglasCentroTab } from "@features/admin/modules/autorizaciones-config/components/ReglasCentroTab";
import { TiposTab } from "@features/admin/modules/autorizaciones-config/components/TiposTab";
import { useTiposConfiguracion } from "@features/admin/modules/autorizaciones-config/queries/useConfiguracion";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";

export function ConfiguracionAutorizacionesPage() {
  // Permisos atomicos evaluados directo (respeta "*"): ver AutorizadoresPage.
  const { hasEffectiveRequirement } = usePermissionDependencies();
  const canRead = hasEffectiveRequirement({ allOf: ["admin:autorizaciones-config:read"] });
  const canEdit = hasEffectiveRequirement({ allOf: ["admin:autorizaciones-config:update"] });

  const { data: tipos } = useTiposConfiguracion(canRead);
  const { data: centrosData } = useCentrosAtencionList({ pageSize: 200, isActive: true }, { enabled: canRead && canEdit });

  return (
    <CatalogModuleLayout
      title="Configuración de autorizaciones"
      description="Cómo se autoriza cada tipo: modalidad, aprobaciones, vencimiento y escalamiento, excepciones por centro y motivos. Los cambios aplican a las solicitudes nuevas."
      icon={<Settings className="size-12" />}
    >
      {!canRead ? (
        <AdminReadOnlyNotice message="No tienes acceso a la configuración de autorizaciones." />
      ) : (
        <Tabs defaultValue="tipos" className="space-y-4">
          <TabsList>
            <TabsTrigger value="tipos">Tipos de autorización</TabsTrigger>
            <TabsTrigger value="reglas">Reglas por centro</TabsTrigger>
            <TabsTrigger value="motivos">Motivos</TabsTrigger>
          </TabsList>
          <TabsContent value="tipos">
            <TiposTab canEdit={canEdit} />
          </TabsContent>
          <TabsContent value="reglas">
            <ReglasCentroTab
              canEdit={canEdit}
              tipos={tipos?.items ?? []}
              centros={(centrosData?.items ?? []).map((c) => ({ id: c.id, name: c.name }))}
            />
          </TabsContent>
          <TabsContent value="motivos">
            <MotivosTab canEdit={canEdit} />
          </TabsContent>
        </Tabs>
      )}
    </CatalogModuleLayout>
  );
}

export default ConfiguracionAutorizacionesPage;
