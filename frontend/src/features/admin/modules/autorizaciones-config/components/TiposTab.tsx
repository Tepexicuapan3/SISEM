import { useState } from "react";
import { Pencil } from "lucide-react";
import type { TipoConfiguracion } from "@api/types/autorizaciones/configuracion.types";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { DataTable, type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { TipoEditDialog } from "@features/admin/modules/autorizaciones-config/components/TipoEditDialog";
import { ETIQUETA_MODALIDAD } from "@features/admin/modules/autorizaciones-config/domain/configuracion.format";
import { useTiposConfiguracion } from "@features/admin/modules/autorizaciones-config/queries/useConfiguracion";
import { getConfiguracionErrorMessage } from "@features/admin/modules/autorizaciones-config/utils/configuracion.feedback";

const siNo = (valor: boolean) => (
  <Badge variant={valor ? "stable" : "secondary"}>{valor ? "Sí" : "No"}</Badge>
);

export function TiposTab({ canEdit }: { canEdit: boolean }) {
  const { data, isLoading, error, refetch } = useTiposConfiguracion();
  const [editando, setEditando] = useState<TipoConfiguracion | null>(null);

  const columnas: DataTableColumn<TipoConfiguracion>[] = [
    { key: "nombre", header: "Tipo", render: (t) => <span className="font-medium text-txt-body">{t.nombre}</span> },
    { key: "modalidad", header: "Modalidad", render: (t) => ETIQUETA_MODALIDAD[t.modalidadPredeterminada] },
    { key: "aprobaciones", header: "Aprobaciones", align: "center", render: (t) => t.aprobacionesRequeridas },
    { key: "vence", header: "Vence (h)", align: "center", render: (t) => t.horasVigenciaSolicitud },
    { key: "escala", header: "Escala (h)", align: "center", render: (t) => t.horasEscalamiento },
    { key: "rechazo", header: "Permite rechazo", align: "center", render: (t) => siNo(t.permiteRechazo) },
    { key: "cedula", header: "Exige cédula", align: "center", render: (t) => siNo(t.requiereCedula) },
  ];
  if (canEdit) {
    columnas.push({
      key: "acciones",
      header: "",
      align: "right",
      render: (t) => (
        <Button
          variant="ghost"
          size="sm"
          aria-label={`Editar ${t.nombre}`}
          onClick={(event) => {
            event.stopPropagation();
            setEditando(t);
          }}
        >
          <Pencil className="size-4" />
        </Button>
      ),
    });
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-txt-muted">
        Regla general de cada tipo para todos los centros. Para un centro distinto, usa «Reglas por centro».
      </p>
      <DataTable
        columns={columnas}
        rows={data?.items ?? []}
        isLoading={isLoading}
        isError={Boolean(error)}
        errorTitle="No se pudo cargar los tipos"
        errorDescription={error ? getConfiguracionErrorMessage(error, "Intenta nuevamente.") : undefined}
        onRetry={() => void refetch()}
        getRowKey={(t) => t.id.toString()}
        emptyTitle="Sin tipos de autorización"
      />
      {editando ? <TipoEditDialog key={editando.id} tipo={editando} onClose={() => setEditando(null)} /> : null}
    </div>
  );
}
