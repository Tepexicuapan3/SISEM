import { useEffect } from "react";
import { AlertTriangle, CalendarDays, Pencil } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Separator } from "@shared/ui/separator";
import { Skeleton } from "@shared/ui/skeleton";
import { MotivoCancelacionCirugiaDetailsGeneralSection } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/components/MotivoCancelacionCirugiaDetailsGeneralSection";
import { MotivoCancelacionCirugiaDialogHeader } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/components/MotivoCancelacionCirugiaDialogHeader";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import {
  motivoCancelacionCirugiaDetailsSchema,
  type MotivoCancelacionCirugiaDetailsFormValues,
} from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/domain/motivos-cancelacion-cirugia.schemas";
import { useUpdateMotivoCancelacionCirugia } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/mutations/useUpdateMotivoCancelacionCirugia";
import { useMotivoCancelacionCirugiaDetail } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/queries/useMotivoCancelacionCirugiaDetail";
import { getMotivoCancelacionCirugiaErrorMessage } from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/utils/motivos-cancelacion-cirugia.feedback";
import {
  formatDate,
  formatDateTime,
} from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/utils/motivos-cancelacion-cirugia.format";
import {
  mapMotivoCancelacionCirugiaDetailToFormValues,
  buildUpdateMotivoCancelacionCirugiaPayload,
} from "@features/admin/modules/catalogos/motivos-cancelacion-cirugia/utils/motivos-cancelacion-cirugia.transform";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type { MotivoCancelacionCirugiaListItem } from "@api/types";

interface MotivoCancelacionCirugiaDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  motivoCancelacionCirugiaSummary: MotivoCancelacionCirugiaListItem | null;
  canEdit: boolean;
}

const DEFAULT_FORM_VALUES: MotivoCancelacionCirugiaDetailsFormValues = { name: "" };
const FORM_ID = "motivos-cancelacion-cirugia-details-form";

export function MotivoCancelacionCirugiaDetailsDialog({
  open, onOpenChange, onClose, motivoCancelacionCirugiaSummary, canEdit,
}: MotivoCancelacionCirugiaDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } = useDetailsDialogCloseGuard(onOpenChange);
  const motivoCancelacionCirugiaId = motivoCancelacionCirugiaSummary?.id;
  const {
    data: motivoCancelacionCirugiaDetailResponse, isLoading, isError, error: motivoCancelacionCirugiaDetailError, refetch,
  } = useMotivoCancelacionCirugiaDetail(motivoCancelacionCirugiaId, open && Boolean(motivoCancelacionCirugiaId));

  const motivoCancelacionCirugiaDetail = motivoCancelacionCirugiaDetailResponse?.motivoCancelacionCirugia;
  const updateMotivoCancelacionCirugia = useUpdateMotivoCancelacionCirugia();

  const form = useForm<MotivoCancelacionCirugiaDetailsFormValues>({
    resolver: zodResolver(motivoCancelacionCirugiaDetailsSchema),
    defaultValues: DEFAULT_FORM_VALUES,
  });
  const isDirty = form.formState.isDirty;

  useEffect(() => {
    if (!motivoCancelacionCirugiaDetail || !open || isDirty) return;
    form.reset(mapMotivoCancelacionCirugiaDetailToFormValues(motivoCancelacionCirugiaDetail));
  }, [motivoCancelacionCirugiaDetail, form, isDirty, open]);

  const closeDialog = () => {
    markClosing();
    form.reset(motivoCancelacionCirugiaDetail ? mapMotivoCancelacionCirugiaDetailToFormValues(motivoCancelacionCirugiaDetail) : DEFAULT_FORM_VALUES);
    onClose?.();
    onOpenChange(false);
  };

  const shouldShowLoading = open && isLoading && !isClosing;
  const shouldShowError = open && !isClosing && (isError || (!isLoading && !motivoCancelacionCirugiaDetail));
  const readOnlyMessage = "Solo lectura: no puedes actualizar este registro porque no tienes permisos.";

  const handleSave = async (values: MotivoCancelacionCirugiaDetailsFormValues) => {
    if (!motivoCancelacionCirugiaDetail || !canEdit) return;
    const payload = buildUpdateMotivoCancelacionCirugiaPayload(values, form.formState.dirtyFields);
    if (Object.keys(payload).length === 0) return;

    try {
      await updateMotivoCancelacionCirugia.mutateAsync({ id: motivoCancelacionCirugiaDetail.id, data: payload });
      toast.success("Registro actualizado", { description: "Los cambios se guardaron correctamente." });
      form.reset(values);
    } catch (error) {
      toast.error("No se pudo guardar", { description: getMotivoCancelacionCirugiaErrorMessage(error, "Error al guardar cambios") });
    }
  };

  const handleStatusChange = async (nextActive: boolean) => {
    if (!motivoCancelacionCirugiaDetail || !canEdit) return;
    try {
      await updateMotivoCancelacionCirugia.mutateAsync({ id: motivoCancelacionCirugiaDetail.id, data: { isActive: nextActive } });
      toast.success(nextActive ? "Registro activado" : "Registro desactivado");
    } catch (error) {
      toast.error("No se pudo actualizar el estado", { description: getMotivoCancelacionCirugiaErrorMessage(error, "Error al actualizar estado") });
    }
  };

  const title = motivoCancelacionCirugiaDetail?.name || motivoCancelacionCirugiaSummary?.name || "Motivo de Cancelación de Cirugía";
  const isActive = motivoCancelacionCirugiaDetail?.isActive ?? motivoCancelacionCirugiaSummary?.isActive;
  const statusBadge = typeof isActive === "boolean" ? <CatalogStatusBadge isActive={isActive} /> : null;

  const createdMetaLabel = motivoCancelacionCirugiaDetail
    ? `Creado ${formatDate(motivoCancelacionCirugiaDetail.createdAt)} por ${motivoCancelacionCirugiaDetail.createdBy?.name ?? "-"}`
    : null;
  const createdMeta = createdMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <CalendarDays className="size-4 shrink-0" />
      <span className="truncate" title={createdMetaLabel}>{createdMetaLabel}</span>
    </span>
  ) : null;

  const updatedMetaLabel = motivoCancelacionCirugiaDetail?.updatedAt
    ? `Actualizado ${formatDateTime(motivoCancelacionCirugiaDetail.updatedAt)} por ${motivoCancelacionCirugiaDetail.updatedBy?.name ?? "-"}`
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
        {getMotivoCancelacionCirugiaErrorMessage(motivoCancelacionCirugiaDetailError, "Intenta nuevamente para ver el detalle completo.")}
      </p>
      <Button variant="outline" size="sm" className="mt-4" onClick={() => void refetch()}>Reintentar</Button>
    </div>
  );

  const sections: AdminDetailsDialogSection[] = motivoCancelacionCirugiaDetail
    ? [{
        id: "general",
        label: "General",
        content: (
          <>
            <MotivoCancelacionCirugiaDetailsGeneralSection
              form={form}
              formId={FORM_ID}
              motivoCancelacionCirugiaDetail={motivoCancelacionCirugiaDetail}
              onSubmit={handleSave}
              onStatusChange={handleStatusChange}
              isStatusPending={updateMotivoCancelacionCirugia.isPending}
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
        motivoCancelacionCirugiaSummary || motivoCancelacionCirugiaDetail ? (
          <MotivoCancelacionCirugiaDialogHeader
            title={title}
            status={statusBadge}
            meta={motivoCancelacionCirugiaDetail ? <span className="flex min-w-0 flex-wrap gap-3">{createdMeta}{updatedMeta}</span> : null}
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
          isSaving={updateMotivoCancelacionCirugia.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!canEdit}
        />
      )}
    />
  );
}
