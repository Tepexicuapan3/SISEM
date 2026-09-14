import { useEffect } from "react";
import { AlertTriangle, CalendarDays, Pencil } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Separator } from "@shared/ui/separator";
import { Skeleton } from "@shared/ui/skeleton";
import { MotivoTrasladoDetailsGeneralSection } from "@features/admin/modules/catalogos/motivos-traslado/components/MotivoTrasladoDetailsGeneralSection";
import { MotivoTrasladoDialogHeader } from "@features/admin/modules/catalogos/motivos-traslado/components/MotivoTrasladoDialogHeader";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import {
  motivoTrasladoDetailsSchema,
  type MotivoTrasladoDetailsFormValues,
} from "@features/admin/modules/catalogos/motivos-traslado/domain/motivos-traslado.schemas";
import { useUpdateMotivoTraslado } from "@features/admin/modules/catalogos/motivos-traslado/mutations/useUpdateMotivoTraslado";
import { useMotivoTrasladoDetail } from "@features/admin/modules/catalogos/motivos-traslado/queries/useMotivoTrasladoDetail";
import { getMotivoTrasladoErrorMessage } from "@features/admin/modules/catalogos/motivos-traslado/utils/motivos-traslado.feedback";
import {
  formatDate,
  formatDateTime,
} from "@features/admin/modules/catalogos/motivos-traslado/utils/motivos-traslado.format";
import {
  mapMotivoTrasladoDetailToFormValues,
  buildUpdateMotivoTrasladoPayload,
} from "@features/admin/modules/catalogos/motivos-traslado/utils/motivos-traslado.transform";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type { MotivoTrasladoListItem } from "@api/types";

interface MotivoTrasladoDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  motivoTrasladoSummary: MotivoTrasladoListItem | null;
  canEdit: boolean;
}

const DEFAULT_FORM_VALUES: MotivoTrasladoDetailsFormValues = { name: "", requiresNotes: false };
const FORM_ID = "motivos-traslado-details-form";

export function MotivoTrasladoDetailsDialog({
  open, onOpenChange, onClose, motivoTrasladoSummary, canEdit,
}: MotivoTrasladoDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } = useDetailsDialogCloseGuard(onOpenChange);
  const motivoTrasladoId = motivoTrasladoSummary?.id;
  const {
    data: motivoTrasladoDetailResponse, isLoading, isError, error: motivoTrasladoDetailError, refetch,
  } = useMotivoTrasladoDetail(motivoTrasladoId, open && Boolean(motivoTrasladoId));

  const motivoTrasladoDetail = motivoTrasladoDetailResponse?.motivoTraslado;
  const updateMotivoTraslado = useUpdateMotivoTraslado();

  const form = useForm<MotivoTrasladoDetailsFormValues>({
    resolver: zodResolver(motivoTrasladoDetailsSchema),
    defaultValues: DEFAULT_FORM_VALUES,
  });
  const isDirty = form.formState.isDirty;

  useEffect(() => {
    if (!motivoTrasladoDetail || !open || isDirty) return;
    form.reset(mapMotivoTrasladoDetailToFormValues(motivoTrasladoDetail));
  }, [motivoTrasladoDetail, form, isDirty, open]);

  const closeDialog = () => {
    markClosing();
    form.reset(motivoTrasladoDetail ? mapMotivoTrasladoDetailToFormValues(motivoTrasladoDetail) : DEFAULT_FORM_VALUES);
    onClose?.();
    onOpenChange(false);
  };

  const shouldShowLoading = open && isLoading && !isClosing;
  const shouldShowError = open && !isClosing && (isError || (!isLoading && !motivoTrasladoDetail));
  const readOnlyMessage = "Solo lectura: no puedes actualizar este registro porque no tienes permisos.";

  const handleSave = async (values: MotivoTrasladoDetailsFormValues) => {
    if (!motivoTrasladoDetail || !canEdit) return;
    const payload = buildUpdateMotivoTrasladoPayload(values, form.formState.dirtyFields);
    if (Object.keys(payload).length === 0) return;

    try {
      await updateMotivoTraslado.mutateAsync({ id: motivoTrasladoDetail.id, data: payload });
      toast.success("Registro actualizado", { description: "Los cambios se guardaron correctamente." });
      form.reset(values);
    } catch (error) {
      toast.error("No se pudo guardar", { description: getMotivoTrasladoErrorMessage(error, "Error al guardar cambios") });
    }
  };

  const handleStatusChange = async (nextActive: boolean) => {
    if (!motivoTrasladoDetail || !canEdit) return;
    try {
      await updateMotivoTraslado.mutateAsync({ id: motivoTrasladoDetail.id, data: { isActive: nextActive } });
      toast.success(nextActive ? "Registro activado" : "Registro desactivado");
    } catch (error) {
      toast.error("No se pudo actualizar el estado", { description: getMotivoTrasladoErrorMessage(error, "Error al actualizar estado") });
    }
  };

  const title = motivoTrasladoDetail?.name || motivoTrasladoSummary?.name || "Motivo de Traslado";
  const isActive = motivoTrasladoDetail?.isActive ?? motivoTrasladoSummary?.isActive;
  const statusBadge = typeof isActive === "boolean" ? <CatalogStatusBadge isActive={isActive} /> : null;

  const createdMetaLabel = motivoTrasladoDetail
    ? `Creado ${formatDate(motivoTrasladoDetail.createdAt)} por ${motivoTrasladoDetail.createdBy?.name ?? "-"}`
    : null;
  const createdMeta = createdMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <CalendarDays className="size-4 shrink-0" />
      <span className="truncate" title={createdMetaLabel}>{createdMetaLabel}</span>
    </span>
  ) : null;

  const updatedMetaLabel = motivoTrasladoDetail?.updatedAt
    ? `Actualizado ${formatDateTime(motivoTrasladoDetail.updatedAt)} por ${motivoTrasladoDetail.updatedBy?.name ?? "-"}`
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
        {getMotivoTrasladoErrorMessage(motivoTrasladoDetailError, "Intenta nuevamente para ver el detalle completo.")}
      </p>
      <Button variant="outline" size="sm" className="mt-4" onClick={() => void refetch()}>Reintentar</Button>
    </div>
  );

  const sections: AdminDetailsDialogSection[] = motivoTrasladoDetail
    ? [{
        id: "general",
        label: "General",
        content: (
          <>
            <MotivoTrasladoDetailsGeneralSection
              form={form}
              formId={FORM_ID}
              motivoTrasladoDetail={motivoTrasladoDetail}
              onSubmit={handleSave}
              onStatusChange={handleStatusChange}
              isStatusPending={updateMotivoTraslado.isPending}
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
      titleSrOnly="Detalle de motivo de traslado"
      descriptionSrOnly="Gestiona la configuracion de este motivo."
      header={
        motivoTrasladoSummary || motivoTrasladoDetail ? (
          <MotivoTrasladoDialogHeader
            title={title}
            status={statusBadge}
            meta={motivoTrasladoDetail ? <span className="flex min-w-0 flex-wrap gap-3">{createdMeta}{updatedMeta}</span> : null}
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
          isSaving={updateMotivoTraslado.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!canEdit}
        />
      )}
    />
  );
}
