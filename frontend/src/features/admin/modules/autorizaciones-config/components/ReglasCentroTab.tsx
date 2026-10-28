import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import type { ReglaCentro, TipoConfiguracion } from "@api/types/autorizaciones/configuracion.types";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@shared/ui/alert-dialog";
import { Button } from "@shared/ui/button";
import { DataTable, type DataTableColumn } from "@features/admin/shared/components/DataTable";
import { ReglaCentroDialog } from "@features/admin/modules/autorizaciones-config/components/ReglaCentroDialog";
import {
  ETIQUETA_MODALIDAD,
  valorOHereda,
} from "@features/admin/modules/autorizaciones-config/domain/configuracion.format";
import { useBajaRegla } from "@features/admin/modules/autorizaciones-config/mutations/useConfiguracionMutations";
import { useReglasCentro } from "@features/admin/modules/autorizaciones-config/queries/useConfiguracion";
import { getConfiguracionErrorMessage } from "@features/admin/modules/autorizaciones-config/utils/configuracion.feedback";

interface ReglasCentroTabProps {
  canEdit: boolean;
  tipos: TipoConfiguracion[];
  centros: { id: number; name: string }[];
}

export function ReglasCentroTab({ canEdit, tipos, centros }: ReglasCentroTabProps) {
  const { data, isLoading, error, refetch } = useReglasCentro();
  const baja = useBajaRegla();
  // undefined = cerrado; null = alta; regla = edicion.
  const [editando, setEditando] = useState<ReglaCentro | null | undefined>(undefined);
  const [porBorrar, setPorBorrar] = useState<ReglaCentro | null>(null);
  const tipoDe = (regla: ReglaCentro) => tipos.find((t) => t.id === regla.tipoId);

  const columnas: DataTableColumn<ReglaCentro>[] = [
    { key: "tipo", header: "Tipo", render: (r) => tipoDe(r)?.nombre ?? r.claveTipo },
    { key: "centro", header: "Centro", render: (r) => <span className="font-medium text-txt-body">{r.centroNombre}</span> },
    {
      key: "modalidad",
      header: "Modalidad",
      render: (r) => {
        const tipo = tipoDe(r);
        return r.modalidad
          ? ETIQUETA_MODALIDAD[r.modalidad]
          : valorOHereda(null, tipo ? ETIQUETA_MODALIDAD[tipo.modalidadPredeterminada] : "—");
      },
    },
    {
      key: "aprobaciones",
      header: "Aprobaciones",
      align: "center",
      render: (r) => valorOHereda(r.aprobacionesRequeridas, tipoDe(r)?.aprobacionesRequeridas ?? "—"),
    },
    {
      key: "vence",
      header: "Vence (h)",
      align: "center",
      render: (r) => valorOHereda(r.horasVigenciaSolicitud, tipoDe(r)?.horasVigenciaSolicitud ?? "—"),
    },
  ];
  if (canEdit) {
    columnas.push({
      key: "acciones",
      header: "",
      align: "right",
      render: (r) => (
        <div className="flex justify-end gap-1">
          <Button variant="ghost" size="sm" aria-label={`Editar regla de ${r.centroNombre}`} onClick={() => setEditando(r)}>
            <Pencil className="size-4" />
          </Button>
          <Button variant="ghost" size="sm" aria-label={`Dar de baja regla de ${r.centroNombre}`} onClick={() => setPorBorrar(r)}>
            <Trash2 className="size-4" />
          </Button>
        </div>
      ),
    });
  }

  const confirmarBaja = async () => {
    if (!porBorrar) return;
    try {
      await baja.mutateAsync({ id: porBorrar.id, version: porBorrar.version });
      toast.success("Regla dada de baja", { description: `${porBorrar.centroNombre}: vuelve a la regla general.` });
    } catch (err) {
      toast.error("No se pudo dar de baja", { description: getConfiguracionErrorMessage(err, "Intenta nuevamente.") });
    } finally {
      setPorBorrar(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-txt-muted">
          Excepciones por centro. Lo que una regla no define se toma de la regla general del tipo.
        </p>
        {canEdit ? (
          <Button size="sm" onClick={() => setEditando(null)}>
            <Plus className="size-4" /> Nueva regla
          </Button>
        ) : null}
      </div>
      <DataTable
        columns={columnas}
        rows={data?.items ?? []}
        isLoading={isLoading}
        isError={Boolean(error)}
        errorTitle="No se pudo cargar las reglas"
        errorDescription={error ? getConfiguracionErrorMessage(error, "Intenta nuevamente.") : undefined}
        onRetry={() => void refetch()}
        getRowKey={(r) => r.id.toString()}
        emptyTitle="Sin reglas por centro"
        emptyDescription="Todos los centros usan la regla general de cada tipo."
      />

      {editando !== undefined ? (
        <ReglaCentroDialog
          key={editando?.id ?? "nueva"}
          regla={editando}
          tipos={tipos}
          centros={centros}
          onClose={() => setEditando(undefined)}
        />
      ) : null}

      <AlertDialog open={Boolean(porBorrar)} onOpenChange={(abierto) => !abierto && setPorBorrar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Dar de baja la regla?</AlertDialogTitle>
            <AlertDialogDescription>
              {porBorrar?.centroNombre} volverá a usar la regla general del tipo en las solicitudes nuevas. La regla
              queda en el historial.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={baja.isPending}>Cancelar</AlertDialogCancel>
            <AlertDialogAction disabled={baja.isPending} onClick={() => void confirmarBaja()}>
              Dar de baja
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
