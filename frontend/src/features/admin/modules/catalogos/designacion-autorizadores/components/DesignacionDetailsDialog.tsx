import { useEffect, useMemo } from "react";
import { AlertTriangle, CalendarDays, Trash2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Separator } from "@shared/ui/separator";
import { Skeleton } from "@shared/ui/skeleton";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import { DesignacionDialogHeader } from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionDialogHeader";
import { DesignacionFormFields } from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionFormFields";
import {
  buildDesignacionSchema,
  type DesignacionFormValues,
} from "@features/admin/modules/catalogos/designacion-autorizadores/domain/designacion.schemas";
import { useUpdateDesignacion } from "@features/admin/modules/catalogos/designacion-autorizadores/mutations/useUpdateDesignacion";
import { useDesignacionDetail } from "@features/admin/modules/catalogos/designacion-autorizadores/queries/useDesignacionDetail";
import { getDesignacionErrorMessage } from "@features/admin/modules/catalogos/designacion-autorizadores/utils/designacion.feedback";
import { formatDate } from "@features/admin/modules/catalogos/designacion-autorizadores/utils/designacion.format";
import {
  buildDesignacionPayload,
  buildEmptyDesignacionValues,
  mapDesignacionToFormValues,
} from "@features/admin/modules/catalogos/designacion-autorizadores/utils/designacion.transform";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type { DesignacionItem } from "@api/types";

interface DesignacionDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  designacionSummary: DesignacionItem | null;
  canEdit: boolean;
  /** `admin.catalogs.designacionAutorizadores.global` */
  canGrantGlobal: boolean;
  /** Abre la confirmacion de baja (la maneja la pagina). */
  onRequestRevoke: (item: DesignacionItem) => void;
}

const FORM_ID = "designacion-details-form";

export function DesignacionDetailsDialog({
  open,
  onOpenChange,
  onClose,
  designacionSummary,
  canEdit,
  canGrantGlobal,
  onRequestRevoke,
}: DesignacionDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } = useDetailsDialogCloseGuard(onOpenChange);

  const itemId = designacionSummary?.id;

  const {
    data: detailResponse,
    isLoading,
    isError,
    error: detailError,
    refetch,
  } = useDesignacionDetail(itemId, open && Boolean(itemId));

  const detail = detailResponse?.designation;
  const updateDesignacion = useUpdateDesignacion();

  const schema = useMemo(() => buildDesignacionSchema({ canGrantGlobal }), [canGrantGlobal]);

  const form = useForm<DesignacionFormValues>({
    resolver: zodResolver(schema),
    defaultValues: buildEmptyDesignacionValues(),
  });

  const isDirty = form.formState.isDirty;

  useEffect(() => {
    if (!detail || !open || isDirty) return;
    form.reset(mapDesignacionToFormValues(detail));
  }, [detail, form, isDirty, open]);

  // Una designacion dada de baja no se reactiva (el backend solo revoca);
  // una GLOBAL solo la modifica quien tiene el permiso global.
  const isRevoked = detail ? !detail.isActive : false;
  const lockedGlobal = Boolean(detail?.alcance.global) && !canGrantGlobal;
  const isEditable = canEdit && !isRevoked && !lockedGlobal;

  const closeDialog = () => {
    markClosing();
    form.reset(detail ? mapDesignacionToFormValues(detail) : buildEmptyDesignacionValues());
    onClose?.();
    onOpenChange(false);
  };

  const shouldShowLoading = open && isLoading && !isClosing;
  const shouldShowError = open && !isClosing && (isError || (!isLoading && !detail));

  const handleSave = async (values: DesignacionFormValues) => {
    if (!detail || !isEditable) return;

    try {
      await updateDesignacion.mutateAsync({
        id: detail.id,
        data: buildDesignacionPayload(values),
      });
      toast.success("Designación actualizada", {
        description: "Los cambios se guardaron correctamente.",
      });
      form.reset(values);
    } catch (error) {
      toast.error("No se pudo guardar", {
        description: getDesignacionErrorMessage(error, "Error al guardar la designación"),
      });
    }
  };

  const title = detail?.user.name || designacionSummary?.user.name || "Designación";
  const subtitle =
    [
      detail?.tipoAutorizacion.name ?? designacionSummary?.tipoAutorizacion.name,
      detail?.cargo ?? designacionSummary?.cargo,
    ]
      .filter(Boolean)
      .join(" · ") || null;
  const isActive = detail?.isActive ?? designacionSummary?.isActive;
  const vigente = detail?.vigente ?? designacionSummary?.vigente;

  const statusBadge =
    typeof isActive === "boolean" ? (
      <span className="inline-flex items-center gap-2">
        <CatalogStatusBadge isActive={isActive} />
        {isActive && vigente === false ? <Badge variant="outline">Fuera de vigencia</Badge> : null}
      </span>
    ) : null;

  const createdMetaLabel = detail?.createdAt ? `Creada ${formatDate(detail.createdAt)}` : null;

  const createdMeta = createdMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <CalendarDays className="size-4 shrink-0" />
      <span className="truncate" title={createdMetaLabel}>
        {createdMetaLabel}
      </span>
    </span>
  ) : null;

  const loadingContent = (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <Skeleton className="size-12 rounded-2xl" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-3 w-32" />
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={`field-skel-${index}`} className="h-12" />
        ))}
      </div>
    </div>
  );

  const errorContent = (
    <div className="rounded-2xl border border-line-struct bg-paper p-6 text-center">
      <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-status-critical/10 text-status-critical">
        <AlertTriangle className="size-6" />
      </div>
      <h3 className="mt-4 text-base font-semibold text-txt-body">
        No se pudo cargar la designación
      </h3>
      <p className="mt-1 text-sm text-txt-muted">
        {getDesignacionErrorMessage(detailError, "Intenta nuevamente para ver el detalle completo.")}
      </p>
      <Button variant="outline" size="sm" className="mt-4" onClick={() => void refetch()}>
        Reintentar
      </Button>
    </div>
  );

  const readOnlyMessage = isRevoked
    ? "Esta designación está dada de baja. Se conserva como historial y ya no se puede modificar."
    : lockedGlobal && canEdit
      ? "Esta designación abarca todos los centros; solo quien tenga el permiso correspondiente puede modificarla."
      : !canEdit
        ? "Solo lectura: no puedes modificar designaciones porque no tienes permisos."
        : null;

  const sections: AdminDetailsDialogSection[] = detail
    ? [
        {
          id: "general",
          label: "General",
          content: (
            <div className="space-y-6">
              <DesignacionFormFields
                key={detail.id}
                form={form}
                formId={FORM_ID}
                onSubmit={handleSave}
                canGrantGlobal={canGrantGlobal}
                disabled={!isEditable}
                initialUserLabel={detail.user.name}
                enabled={open}
              />

              <Separator />

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>ID</Label>
                  <Input value={detail.id.toString()} disabled />
                </div>
                <div className="space-y-2">
                  <Label>Estado</Label>
                  <div className="flex min-h-9 flex-wrap items-center gap-3">
                    <CatalogStatusBadge isActive={detail.isActive} />
                    {canEdit && detail.isActive && !lockedGlobal ? (
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        onClick={() => onRequestRevoke(detail)}
                      >
                        <Trash2 className="size-4" />
                        Dar de baja
                      </Button>
                    ) : null}
                  </div>
                </div>
              </div>

              {readOnlyMessage ? <AdminReadOnlyNotice message={readOnlyMessage} /> : null}
            </div>
          ),
        },
      ]
    : [];

  return (
    <AdminDetailsDialogShell
      open={open}
      onOpenChange={handleOpenChange}
      onRequestClose={closeDialog}
      titleSrOnly="Detalle de designación de autorizador"
      descriptionSrOnly="Consulta, edita o da de baja esta designación de autorizador."
      header={
        designacionSummary || detail ? (
          <DesignacionDialogHeader
            title={title}
            subtitle={subtitle}
            status={statusBadge}
            meta={detail ? <span className="flex min-w-0 flex-wrap gap-3">{createdMeta}</span> : null}
          />
        ) : null
      }
      topContent={<Separator />}
      isDirty={isDirty}
      isLoading={shouldShowLoading}
      isError={shouldShowError}
      loadingContent={loadingContent}
      errorContent={errorContent}
      sections={sections}
      defaultSectionId="general"
      dialogContentClassName="h-auto max-h-[90vh] w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215 xl:w-235"
      footer={({ onCancel }) => (
        <CatalogDetailsFooter
          isDirty={isDirty}
          isSaving={updateDesignacion.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!isEditable}
        />
      )}
    />
  );
}
