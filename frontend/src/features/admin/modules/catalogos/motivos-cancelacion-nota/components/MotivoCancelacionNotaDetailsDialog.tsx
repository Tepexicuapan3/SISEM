import { useEffect } from "react";
import { AlertTriangle, CalendarDays, Pencil } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Separator } from "@shared/ui/separator";
import { Skeleton } from "@shared/ui/skeleton";
import { MotivoCancelacionNotaDetailsGeneralSection } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/components/MotivoCancelacionNotaDetailsGeneralSection";
import { MotivoCancelacionNotaDialogHeader } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/components/MotivoCancelacionNotaDialogHeader";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import {
  motivoCancelacionNotaDetailsSchema,
  type MotivoCancelacionNotaDetailsFormValues,
} from "@features/admin/modules/catalogos/motivos-cancelacion-nota/domain/motivos-cancelacion-nota.schemas";
import { useUpdateMotivoCancelacionNota } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/mutations/useUpdateMotivoCancelacionNota";
import { useMotivoCancelacionNotaDetail } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/queries/useMotivoCancelacionNotaDetail";
import { getMotivoCancelacionNotaErrorMessage } from "@features/admin/modules/catalogos/motivos-cancelacion-nota/utils/motivos-cancelacion-nota.feedback";
import {
  formatDate,
  formatDateTime,
} from "@features/admin/modules/catalogos/motivos-cancelacion-nota/utils/motivos-cancelacion-nota.format";
import {
  mapMotivoCancelacionNotaDetailToFormValues,
  buildUpdateMotivoCancelacionNotaPayload,
} from "@features/admin/modules/catalogos/motivos-cancelacion-nota/utils/motivos-cancelacion-nota.transform";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type { MotivoCancelacionNotaListItem } from "@api/types";

interface MotivoCancelacionNotaDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  motivoCancelacionNotaSummary: MotivoCancelacionNotaListItem | null;
  canEdit: boolean;
}

const DEFAULT_FORM_VALUES: MotivoCancelacionNotaDetailsFormValues = { name: "" };
const FORM_ID = "motivos-cancelacion-nota-details-form";

export function MotivoCancelacionNotaDetailsDialog({
  open, onOpenChange, onClose, motivoCancelacionNotaSummary, canEdit,
}: MotivoCancelacionNotaDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } = useDetailsDialogCloseGuard(onOpenChange);
  const motivoCancelacionNotaId = motivoCancelacionNotaSummary?.id;
  const {
    data: motivoCancelacionNotaDetailResponse, isLoading, isError, error: motivoCancelacionNotaDetailError, refetch,
  } = useMotivoCancelacionNotaDetail(motivoCancelacionNotaId, open && Boolean(motivoCancelacionNotaId));

  const motivoCancelacionNotaDetail = motivoCancelacionNotaDetailResponse?.motivoCancelacionNota;
  const updateMotivoCancelacionNota = useUpdateMotivoCancelacionNota();

  const form = useForm<MotivoCancelacionNotaDetailsFormValues>({
    resolver: zodResolver(motivoCancelacionNotaDetailsSchema),
    defaultValues: DEFAULT_FORM_VALUES,
  });
  const isDirty = form.formState.isDirty;

  useEffect(() => {
    if (!motivoCancelacionNotaDetail || !open || isDirty) return;
    form.reset(mapMotivoCancelacionNotaDetailToFormValues(motivoCancelacionNotaDetail));
  }, [motivoCancelacionNotaDetail, form, isDirty, open]);

  const closeDialog = () => {
    markClosing();
    form.reset(motivoCancelacionNotaDetail ? mapMotivoCancelacionNotaDetailToFormValues(motivoCancelacionNotaDetail) : DEFAULT_FORM_VALUES);
    onClose?.();
    onOpenChange(false);
  };

  const shouldShowLoading = open && isLoading && !isClosing;
  const shouldShowError = open && !isClosing && (isError || (!isLoading && !motivoCancelacionNotaDetail));
  const readOnlyMessage = "Solo lectura: no puedes actualizar este registro porque no tienes permisos.";

  const handleSave = async (values: MotivoCancelacionNotaDetailsFormValues) => {
    if (!motivoCancelacionNotaDetail || !canEdit) return;
    const payload = buildUpdateMotivoCancelacionNotaPayload(values, form.formState.dirtyFields);
    if (Object.keys(payload).length === 0) return;

    try {
      await updateMotivoCancelacionNota.mutateAsync({ id: motivoCancelacionNotaDetail.id, data: payload });
      toast.success("Registro actualizado", { description: "Los cambios se guardaron correctamente." });
      form.reset(values);
    } catch (error) {
      toast.error("No se pudo guardar", { description: getMotivoCancelacionNotaErrorMessage(error, "Error al guardar cambios") });
    }
  };

  const handleStatusChange = async (nextActive: boolean) => {
    if (!motivoCancelacionNotaDetail || !canEdit) return;
    try {
      await updateMotivoCancelacionNota.mutateAsync({ id: motivoCancelacionNotaDetail.id, data: { isActive: nextActive } });
      toast.success(nextActive ? "Registro activado" : "Registro desactivado");
    } catch (error) {
      toast.error("No se pudo actualizar el estado", { description: getMotivoCancelacionNotaErrorMessage(error, "Error al actualizar estado") });
    }
  };

  const title = motivoCancelacionNotaDetail?.name || motivoCancelacionNotaSummary?.name || "Motivo de Cancelación de Nota";
  const isActive = motivoCancelacionNotaDetail?.isActive ?? motivoCancelacionNotaSummary?.isActive;
  const statusBadge = typeof isActive === "boolean" ? <CatalogStatusBadge isActive={isActive} /> : null;

  const createdMetaLabel = motivoCancelacionNotaDetail
    ? `Creado ${formatDate(motivoCancelacionNotaDetail.createdAt)} por ${motivoCancelacionNotaDetail.createdBy?.name ?? "-"}`
    : null;
  const createdMeta = createdMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <CalendarDays className="size-4 shrink-0" />
      <span className="truncate" title={createdMetaLabel}>{createdMetaLabel}</span>
    </span>
  ) : null;

  const updatedMetaLabel = motivoCancelacionNotaDetail?.updatedAt
    ? `Actualizado ${formatDateTime(motivoCancelacionNotaDetail.updatedAt)} por ${motivoCancelacionNotaDetail.updatedBy?.name ?? "-"}`
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
        {getMotivoCancelacionNotaErrorMessage(motivoCancelacionNotaDetailError, "Intenta nuevamente para ver el detalle completo.")}
      </p>
      <Button variant="outline" size="sm" className="mt-4" onClick={() => void refetch()}>Reintentar</Button>
    </div>
  );

  const sections: AdminDetailsDialogSection[] = motivoCancelacionNotaDetail
    ? [{
        id: "general",
        label: "General",
        content: (
          <>
            <MotivoCancelacionNotaDetailsGeneralSection
              form={form}
              formId={FORM_ID}
              motivoCancelacionNotaDetail={motivoCancelacionNotaDetail}
              onSubmit={handleSave}
              onStatusChange={handleStatusChange}
              isStatusPending={updateMotivoCancelacionNota.isPending}
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
        motivoCancelacionNotaSummary || motivoCancelacionNotaDetail ? (
          <MotivoCancelacionNotaDialogHeader
            title={title}
            status={statusBadge}
            meta={motivoCancelacionNotaDetail ? <span className="flex min-w-0 flex-wrap gap-3">{createdMeta}{updatedMeta}</span> : null}
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
          isSaving={updateMotivoCancelacionNota.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!canEdit}
        />
      )}
    />
  );
}
