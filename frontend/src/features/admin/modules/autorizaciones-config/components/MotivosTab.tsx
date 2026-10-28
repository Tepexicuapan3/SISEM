import { useState } from "react";
import { Pencil, Plus } from "lucide-react";
import { toast } from "sonner";
import type { AmbitoMotivo, MotivoConfiguracion } from "@api/types/autorizaciones/configuracion.types";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { Switch } from "@shared/ui/switch";
import { DataTable, type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { MotivoDialog } from "@features/admin/modules/autorizaciones-config/components/MotivoDialog";
import { ETIQUETA_AMBITO } from "@features/admin/modules/autorizaciones-config/domain/configuracion.format";
import { AMBITOS } from "@features/admin/modules/autorizaciones-config/domain/configuracion.schemas";
import { useUpdateMotivo } from "@features/admin/modules/autorizaciones-config/mutations/useConfiguracionMutations";
import { useMotivosConfiguracion } from "@features/admin/modules/autorizaciones-config/queries/useConfiguracion";
import { getConfiguracionErrorMessage } from "@features/admin/modules/autorizaciones-config/utils/configuracion.feedback";

export function MotivosTab({ canEdit }: { canEdit: boolean }) {
  const [ambito, setAmbito] = useState<AmbitoMotivo>("RECHAZO");
  const { data, isLoading, error, refetch } = useMotivosConfiguracion(ambito);
  const actualizar = useUpdateMotivo();
  // undefined = cerrado; null = alta; motivo = edicion.
  const [editando, setEditando] = useState<MotivoConfiguracion | null | undefined>(undefined);

  const cambiarActivo = async (motivo: MotivoConfiguracion, activo: boolean) => {
    try {
      await actualizar.mutateAsync({ id: motivo.id, data: { version: motivo.version, activo } });
      toast.success(activo ? "Motivo activado" : "Motivo desactivado", { description: motivo.descripcion });
    } catch (err) {
      toast.error("No se pudo cambiar el motivo", { description: getConfiguracionErrorMessage(err, "Intenta nuevamente.") });
    }
  };

  const columnas: DataTableColumn<MotivoConfiguracion>[] = [
    { key: "descripcion", header: "Motivo", render: (m) => <span className="font-medium text-txt-body">{m.descripcion}</span> },
    { key: "clave", header: "Clave", render: (m) => <code className="text-xs text-txt-muted">{m.clave}</code> },
    {
      key: "libre",
      header: "Pide explicación",
      align: "center",
      render: (m) => (m.requiereDescripcionLibre ? <Badge variant="info">Sí</Badge> : <Badge variant="secondary">No</Badge>),
    },
    {
      key: "activo",
      header: "Activo",
      align: "center",
      render: (m) =>
        canEdit ? (
          <Switch
            checked={m.activo}
            aria-label={`${m.activo ? "Desactivar" : "Activar"} ${m.descripcion}`}
            disabled={actualizar.isPending}
            onCheckedChange={(valor) => void cambiarActivo(m, valor)}
          />
        ) : (
          <Badge variant={m.activo ? "stable" : "secondary"}>{m.activo ? "Activo" : "Inactivo"}</Badge>
        ),
    },
  ];
  if (canEdit) {
    columnas.push({
      key: "acciones",
      header: "",
      align: "right",
      render: (m) => (
        <Button variant="ghost" size="sm" aria-label={`Editar ${m.descripcion}`} onClick={() => setEditando(m)}>
          <Pencil className="size-4" />
        </Button>
      ),
    });
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Select value={ambito} onValueChange={(valor) => setAmbito(valor as AmbitoMotivo)}>
          <SelectTrigger className="w-64" aria-label="Ámbito del motivo">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {AMBITOS.map((a) => (
              <SelectItem key={a} value={a}>
                {ETIQUETA_AMBITO[a]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {canEdit ? (
          <Button size="sm" onClick={() => setEditando(null)}>
            <Plus className="size-4" /> Nuevo motivo
          </Button>
        ) : null}
      </div>
      <DataTable
        columns={columnas}
        rows={data?.items ?? []}
        isLoading={isLoading}
        isError={Boolean(error)}
        errorTitle="No se pudo cargar los motivos"
        errorDescription={error ? getConfiguracionErrorMessage(error, "Intenta nuevamente.") : undefined}
        onRetry={() => void refetch()}
        getRowKey={(m) => m.id.toString()}
        emptyTitle="Sin motivos en este ámbito"
      />
      {editando !== undefined ? (
        <MotivoDialog
          key={editando?.id ?? `nuevo-${ambito}`}
          motivo={editando}
          ambitoInicial={ambito}
          onClose={() => setEditando(undefined)}
        />
      ) : null}
    </div>
  );
}
