import { useEffect } from "react";
import { AlertTriangle, CalendarDays, Pencil } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Separator } from "@shared/ui/separator";
import { Skeleton } from "@shared/ui/skeleton";
import { TipoTrasladoDetailsGeneralSection } from "@features/admin/modules/catalogos/tipos-traslado/components/TipoTrasladoDetailsGeneralSection";
import { TipoTrasladoDialogHeader } from "@features/admin/modules/catalogos/tipos-traslado/components/TipoTrasladoDialogHeader";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import {
  tipoTrasladoDetailsSchema,
  type TipoTrasladoDetailsFormValues,
} from "@features/admin/modules/catalogos/tipos-traslado/domain/tipos-traslado.schemas";
import { useUpdateTipoTraslado } from "@features/admin/modules/catalogos/tipos-traslado/mutations/useUpdateTipoTraslado";
import { useTipoTrasladoDetail } from "@features/admin/modules/catalogos/tipos-traslado/queries/useTipoTrasladoDetail";
import { getTipoTrasladoErrorMessage } from "@features/admin/modules/catalogos/tipos-traslado/utils/tipos-traslado.feedback";
import {
  formatDate,
  formatDateTime,
} from "@features/admin/modules/catalogos/tipos-traslado/utils/tipos-traslado.format";
import {
  mapTipoTrasladoDetailToFormValues,
  buildUpdateTipoTrasladoPayload,
} from "@features/admin/modules/catalogos/tipos-traslado/utils/tipos-traslado.transform";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type { TipoTrasladoListItem } from "@api/types";

interface TipoTrasladoDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  tipoTrasladoSummary: TipoTrasladoListItem | null;
  canEdit: boolean;
}

const DEFAULT_FORM_VALUES: TipoTrasladoDetailsFormValues = { name: "" };
const FORM_ID = "tipos-traslado-details-form";

export function TipoTrasladoDetailsDialog({
  open, onOpenChange, onClose, tipoTrasladoSummary, canEdit,
}: TipoTrasladoDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } = useDetailsDialogCloseGuard(onOpenChange);
  const tipoTrasladoId = tipoTrasladoSummary?.id;
  const {
    data: tipoTrasladoDetailResponse, isLoading, isError, error: tipoTrasladoDetailError, refetch,
  } = useTipoTrasladoDetail(tipoTrasladoId, open && Boolean(tipoTrasladoId));

  const tipoTrasladoDetail = tipoTrasladoDetailResponse?.tipoTraslado;
  const updateTipoTraslado = useUpdateTipoTraslado();

  const form = useForm<TipoTrasladoDetailsFormValues>({
    resolver: zodResolver(tipoTrasladoDetailsSchema),
    defaultValues: DEFAULT_FORM_VALUES,
  });
  const isDirty = form.formState.isDirty;

  useEffect(() => {
    if (!tipoTrasladoDetail || !open || isDirty) return;
    form.reset(mapTipoTrasladoDetailToFormValues(tipoTrasladoDetail));
  }, [tipoTrasladoDetail, form, isDirty, open]);

  const closeDialog = () => {
    markClosing();
    form.reset(tipoTrasladoDetail ? mapTipoTrasladoDetailToFormValues(tipoTrasladoDetail) : DEFAULT_FORM_VALUES);
    onClose?.();
    onOpenChange(false);
  };

  const shouldShowLoading = open && isLoading && !isClosing;
  const shouldShowError = open && !isClosing && (isError || (!isLoading && !tipoTrasladoDetail));
  const readOnlyMessage = "Solo lectura: no puedes actualizar este registro porque no tienes permisos.";

  const handleSave = async (values: TipoTrasladoDetailsFormValues) => {
    if (!tipoTrasladoDetail || !canEdit) return;
    const payload = buildUpdateTipoTrasladoPayload(values, form.formState.dirtyFields);
    if (Object.keys(payload).length === 0) return;

    try {
      await updateTipoTraslado.mutateAsync({ id: tipoTrasladoDetail.id, data: payload });
      toast.success("Registro actualizado", { description: "Los cambios se guardaron correctamente." });
      form.reset(values);
    } catch (error) {
      toast.error("No se pudo guardar", { description: getTipoTrasladoErrorMessage(error, "Error al guardar cambios") });
    }
  };

  const handleStatusChange = async (nextActive: boolean) => {
    if (!tipoTrasladoDetail || !canEdit) return;
    try {
      await updateTipoTraslado.mutateAsync({ id: tipoTrasladoDetail.id, data: { isActive: nextActive } });
      toast.success(nextActive ? "Registro activado" : "Registro desactivado");
    } catch (error) {
      toast.error("No se pudo actualizar el estado", { description: getTipoTrasladoErrorMessage(error, "Error al actualizar estado") });
    }
  };

  const title = tipoTrasladoDetail?.name || tipoTrasladoSummary?.name || "Tipo de Traslado";
  const isActive = tipoTrasladoDetail?.isActive ?? tipoTrasladoSummary?.isActive;
  const statusBadge = typeof isActive === "boolean" ? <CatalogStatusBadge isActive={isActive} /> : null;

  const createdMetaLabel = tipoTrasladoDetail
    ? `Creado ${formatDate(tipoTrasladoDetail.createdAt)} por ${tipoTrasladoDetail.createdBy?.name ?? "-"}`
    : null;
  const createdMeta = createdMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <CalendarDays className="size-4 shrink-0" />
      <span className="truncate" title={createdMetaLabel}>{createdMetaLabel}</span>
    </span>
  ) : null;

  const updatedMetaLabel = tipoTrasladoDetail?.updatedAt
    ? `Actualizado ${formatDateTime(tipoTrasladoDetail.updatedAt)} por ${tipoTrasladoDetail.updatedBy?.name ?? "-"}`
    : null;
  const updatedMeta = updatedMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <Pencil className="size-4 shrink-0" />
      <span className="truncate" title={updatedMetaLabel}>{updatedMetaLabel}</span>
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
        {Array.from({ length: 2 }).map((_, index) => (
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
      <h3 className="mt-4 text-base font-semibold text-txt-body">No se pudo cargar el registro</h3>
      <p className="mt-1 text-sm text-txt-muted">
        {getTipoTrasladoErrorMessage(tipoTrasladoDetailError, "Intenta nuevamente para ver el detalle completo.")}
      </p>
      <Button variant="outline" size="sm" className="mt-4" onClick={() => void refetch()}>Reintentar</Button>
    </div>
  );

  const sections: AdminDetailsDialogSection[] = tipoTrasladoDetail
    ? [{
        id: "general",
        label: "General",
        content: (
          <>
            <TipoTrasladoDetailsGeneralSection
              form={form}
              formId={FORM_ID}
              tipoTrasladoDetail={tipoTrasladoDetail}
              onSubmit={handleSave}
              onStatusChange={handleStatusChange}
              isStatusPending={updateTipoTraslado.isPending}
              isEditable={canEdit}
            />
            {!canEdit ? <AdminReadOnlyNotice message={readOnlyMessage} /> : null}
          </>
        ),
      }]
    : [];

  return (
    <AdminDetailsDialogShell
      open={open}
      onOpenChange={handleOpenChange}
      onRequestClose={closeDialog}
      titleSrOnly="Detalle de registro"
      descriptionSrOnly="Gestiona la configuracion de este registro."
      header={
        tipoTrasladoSummary || tipoTrasladoDetail ? (
          <TipoTrasladoDialogHeader
            title={title}
            status={statusBadge}
            meta={tipoTrasladoDetail ? <span className="flex min-w-0 flex-wrap gap-3">{createdMeta}{updatedMeta}</span> : null}
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
      dialogContentClassName="h-auto max-h-[90vh] w-[86vw] max-w-none rounded-3xl bg-paper p-0 sm:max-w-[880px]"
      footer={({ onCancel }) => (
        <CatalogDetailsFooter
          isDirty={isDirty}
          isSaving={updateTipoTraslado.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!canEdit}
        />
      )}
    />
  );
}
