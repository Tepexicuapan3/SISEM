import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, CalendarClock, Pause, Play, UserCheck, UserX } from "lucide-react";
import { toast } from "sonner";
import type { AutorizadorItem, TipoAutorizacionCatalogo } from "@api/types/autorizaciones/autorizadores.types";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Separator } from "@shared/ui/separator";
import { Skeleton } from "@shared/ui/skeleton";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import { AutorizadorFormFields } from "@features/admin/modules/autorizadores/components/AutorizadorFormFields";
import { AutorizadorHistorial } from "@features/admin/modules/autorizadores/components/AutorizadorHistorial";
import type { AccionAutorizador } from "@features/admin/modules/autorizadores/components/AutorizadorEstatusDialog";
import { accionesDisponibles } from "@features/admin/modules/autorizadores/domain/autorizador.estatus";
import {
  buildAutorizadorSchema,
  type AutorizadorFormValues,
} from "@features/admin/modules/autorizadores/domain/autorizador.schemas";
import { useUpdateAutorizador } from "@features/admin/modules/autorizadores/mutations/useAutorizadorMutations";
import { useAutorizadorDetail } from "@features/admin/modules/autorizadores/queries/useAutorizadores";
import { getAutorizadorErrorMessage } from "@features/admin/modules/autorizadores/utils/autorizador.feedback";
import {
  describirEstatus,
  describirVigencia,
  formatFecha,
} from "@features/admin/modules/autorizadores/utils/autorizador.format";
import {
  buildEdicionPayload,
  buildEmptyAutorizadorValues,
  mapAutorizadorToFormValues,
} from "@features/admin/modules/autorizadores/utils/autorizador.transform";

interface AutorizadorDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  resumen: AutorizadorItem | null;
  tiposCatalogo: TipoAutorizacionCatalogo[];
  canEdit: boolean;
  canChangeStatus: boolean;
  /** `admin:autorizadores:global` */
  canGrantGlobal: boolean;
  onAccion: (accion: AccionAutorizador, item: AutorizadorItem) => void;
}

const FORM_ID = "autorizador-details-form";

export function AutorizadorDetailsDialog({
  open,
  onOpenChange,
  onClose,
  resumen,
  tiposCatalogo,
  canEdit,
  canChangeStatus,
  canGrantGlobal,
  onAccion,
}: AutorizadorDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } = useDetailsDialogCloseGuard(onOpenChange);
  const claves = tiposCatalogo.map((tipo) => tipo.clave);

  const { data, isLoading, isError, error, refetch } = useAutorizadorDetail(resumen?.id, open);
  const detalle = data?.autorizador;
  const actualizar = useUpdateAutorizador();

  const tieneGlobal = Boolean(detalle?.tipos.some((tipo) => tipo.alcance.global));
  const bloqueadoGlobal = tieneGlobal && !canGrantGlobal;
  const acciones = detalle ? accionesDisponibles(detalle) : null;
  const editable = canEdit && Boolean(acciones?.editar) && !bloqueadoGlobal;

  const form = useForm<AutorizadorFormValues>({
    resolver: zodResolver(buildAutorizadorSchema({ canGrantGlobal, modo: "edicion" })),
    defaultValues: buildEmptyAutorizadorValues([]),
  });
  const isDirty = form.formState.isDirty;

  // Tras guardar o cambiar estatus llega una version nueva: se recarga el formulario si no hay cambios sin guardar.
  useEffect(() => {
    if (!detalle || !open || isDirty || tiposCatalogo.length === 0) return;
    form.reset(mapAutorizadorToFormValues(detalle, tiposCatalogo.map((tipo) => tipo.clave)));
  }, [detalle, form, isDirty, open, tiposCatalogo]);

  const cerrar = () => {
    markClosing();
    form.reset(detalle ? mapAutorizadorToFormValues(detalle, claves) : buildEmptyAutorizadorValues([]));
    onClose?.();
    onOpenChange(false);
  };

  const guardar = async (valores: AutorizadorFormValues) => {
    if (!detalle || !editable) return;
    try {
      await actualizar.mutateAsync({ id: detalle.id, data: buildEdicionPayload(valores, detalle.version) });
      toast.success("Autorizador actualizado", { description: "Los cambios quedaron en el historial." });
      form.reset(valores);
    } catch (mutationError) {
      toast.error("No se pudo guardar", {
        description: getAutorizadorErrorMessage(mutationError, "Error al guardar el autorizador"),
      });
    }
  };

  const item = detalle ?? resumen;
  const estatus = item ? describirEstatus(item.estatus) : null;
  const vigencia = item ? describirVigencia(item.estadoVigencia) : null;

  const encabezado = item ? (
    <CatalogDialogHeader
      title={item.usuario.nombreCompleto}
      subtitle={[item.usuario.usuario, item.cargo].filter(Boolean).join(" · ") || null}
      icon={<UserCheck className="size-7" />}
      status={
        <span className="inline-flex flex-wrap items-center gap-2">
          {estatus ? <Badge variant={estatus.variante}>{estatus.etiqueta}</Badge> : null}
          {vigencia && item.estatus !== "INACTIVO" ? (
            <Badge variant={vigencia.variante}>{vigencia.etiqueta}</Badge>
          ) : null}
        </span>
      }
      meta={
        <span className="inline-flex items-center gap-2">
          <CalendarClock className="size-4 shrink-0" />
          Vigencia {formatFecha(item.fechaInicioVigencia)} – {formatFecha(item.fechaFinVigencia)}
        </span>
      }
    />
  ) : null;

  const avisoSoloLectura = !detalle
    ? null
    : detalle.estatus === "INACTIVO"
      ? "Este autorizador está dado de baja. Se conserva como historial y ya no se puede modificar."
      : bloqueadoGlobal && canEdit
        ? "Este autorizador tiene alcance de todos los centros; solo quien tenga ese permiso puede modificarlo."
        : !canEdit
          ? "Solo lectura: no tienes permiso para editar autorizadores."
          : null;

  const hayAcciones = Boolean(
    acciones &&
      ((canEdit && acciones.renovar && !bloqueadoGlobal) ||
        (canChangeStatus && (acciones.reactivar || acciones.suspender || acciones.darDeBaja))),
  );

  const botonesAccion = detalle && acciones ? (
    <div className="flex flex-wrap gap-2">
      {canEdit && acciones.renovar && !bloqueadoGlobal ? (
        <Button type="button" variant="outline" size="sm" onClick={() => onAccion("renovar", detalle)}>
          <CalendarClock className="size-4" />
          Renovar vigencia
        </Button>
      ) : null}
      {canChangeStatus && acciones.reactivar ? (
        <Button type="button" variant="outline" size="sm" onClick={() => onAccion("reactivar", detalle)}>
          <Play className="size-4" />
          Reactivar
        </Button>
      ) : null}
      {canChangeStatus && acciones.suspender ? (
        <Button type="button" variant="outline" size="sm" onClick={() => onAccion("suspender", detalle)}>
          <Pause className="size-4" />
          Suspender
        </Button>
      ) : null}
      {canChangeStatus && acciones.darDeBaja ? (
        <Button type="button" variant="destructive" size="sm" onClick={() => onAccion("baja", detalle)}>
          <UserX className="size-4" />
          Dar de baja
        </Button>
      ) : null}
    </div>
  ) : null;

  const secciones: AdminDetailsDialogSection[] = detalle
    ? [
        {
          id: "general",
          label: "General",
          content: (
            <div className="space-y-6">
              {hayAcciones ? (
                <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line-struct px-4 py-3">
                  <span className="text-xs font-semibold uppercase tracking-wide text-txt-muted">Acciones</span>
                  {botonesAccion}
                </div>
              ) : null}
              {avisoSoloLectura ? <AdminReadOnlyNotice message={avisoSoloLectura} /> : null}

              {detalle.estatus === "SUSPENDIDO" && detalle.motivoEstatus ? (
                <AdminReadOnlyNotice
                  message={`Suspendido: ${detalle.motivoEstatus.descripcion}${
                    detalle.descripcionMotivoEstatus ? ` — ${detalle.descripcionMotivoEstatus}` : ""
                  }${detalle.fechaFinSuspension ? ` (hasta ${formatFecha(detalle.fechaFinSuspension)})` : ""}`}
                />
              ) : null}

              {tiposCatalogo.length > 0 ? (
                <AutorizadorFormFields
                  key={`${detalle.id}-${detalle.version}`}
                  form={form}
                  formId={FORM_ID}
                  onSubmit={guardar}
                  modo="edicion"
                  tiposCatalogo={tiposCatalogo}
                  canGrantGlobal={canGrantGlobal}
                  disabled={!editable}
                  nombreUsuario={detalle.usuario.nombreCompleto}
                  enabled={open}
                />
              ) : null}

              <Separator />

              <dl className="grid gap-4 rounded-2xl bg-surface-hover px-4 py-3 text-sm sm:grid-cols-3">
                <div className="min-w-0">
                  <dt className="text-xs text-txt-muted">Cédula profesional</dt>
                  <dd className="truncate">
                    {detalle.usuario.cedulas.find((c) => c.esPrincipal)?.numero ??
                      detalle.usuario.cedulas[0]?.numero ??
                      "Sin cédula en Usuarios"}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-xs text-txt-muted">Registrado por</dt>
                  <dd className="truncate">
                    {detalle.creadoPor?.name ?? "—"}
                    {detalle.fechaCreacion ? ` · ${formatFecha(detalle.fechaCreacion)}` : ""}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-xs text-txt-muted">Última modificación</dt>
                  <dd className="truncate">
                    {detalle.modificadoPor?.name ?? "—"}
                    {detalle.fechaModificacion ? ` · ${formatFecha(detalle.fechaModificacion)}` : ""}
                  </dd>
                </div>
              </dl>
            </div>
          ),
        },
        {
          id: "historial",
          label: "Historial",
          content: <AutorizadorHistorial idAutorizador={detalle.id} enabled={open} />,
        },
      ]
    : [];

  return (
    <AdminDetailsDialogShell
      open={open}
      onOpenChange={handleOpenChange}
      onRequestClose={cerrar}
      titleSrOnly="Detalle de autorizador médico"
      descriptionSrOnly="Consulta y edita los tipos, centros y vigencia de este autorizador, y revisa su historial."
      header={encabezado}
      topContent={<Separator />}
      isDirty={isDirty}
      isLoading={open && isLoading && !isClosing}
      isError={open && !isClosing && (isError || (!isLoading && !detalle))}
      loadingContent={
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, indice) => (
            <Skeleton key={`aut-skel-${indice}`} className="h-12" />
          ))}
        </div>
      }
      errorContent={
        <div className="rounded-2xl border border-line-struct bg-paper p-6 text-center">
          <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-status-critical/10 text-status-critical">
            <AlertTriangle className="size-6" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-txt-body">No se pudo cargar el autorizador</h3>
          <p className="mt-1 text-sm text-txt-muted">
            {getAutorizadorErrorMessage(error, "Intenta nuevamente para ver el detalle completo.")}
          </p>
          <Button variant="outline" size="sm" className="mt-4" onClick={() => void refetch()}>
            Reintentar
          </Button>
        </div>
      }
      sections={secciones}
      defaultSectionId="general"
      dialogContentClassName="h-auto max-h-[90vh] w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] sm:max-w-none lg:w-215 xl:w-235"
      footer={({ onCancel }) => (
        <CatalogDetailsFooter
          isDirty={isDirty}
          isSaving={actualizar.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!editable}
        />
      )}
    />
  );
}
