import { useEffect } from "react";
import { AlertTriangle, CalendarDays, Pencil } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Separator } from "@shared/ui/separator";
import { Skeleton } from "@shared/ui/skeleton";
import { MotivoBajaPadronDetailsGeneralSection } from "@features/admin/modules/catalogos/motivos-baja-padron/components/MotivoBajaPadronDetailsGeneralSection";
import { MotivoBajaPadronDialogHeader } from "@features/admin/modules/catalogos/motivos-baja-padron/components/MotivoBajaPadronDialogHeader";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import {
  motivoBajaPadronDetailsSchema,
  type MotivoBajaPadronDetailsFormValues,
} from "@features/admin/modules/catalogos/motivos-baja-padron/domain/motivos-baja-padron.schemas";
import { useUpdateMotivoBajaPadron } from "@features/admin/modules/catalogos/motivos-baja-padron/mutations/useUpdateMotivoBajaPadron";
import { useMotivoBajaPadronDetail } from "@features/admin/modules/catalogos/motivos-baja-padron/queries/useMotivoBajaPadronDetail";
import { getMotivoBajaPadronErrorMessage } from "@features/admin/modules/catalogos/motivos-baja-padron/utils/motivos-baja-padron.feedback";
import {
  formatDate,
  formatDateTime,
} from "@features/admin/modules/catalogos/motivos-baja-padron/utils/motivos-baja-padron.format";
import {
  mapMotivoBajaPadronDetailToFormValues,
  buildUpdateMotivoBajaPadronPayload,
} from "@features/admin/modules/catalogos/motivos-baja-padron/utils/motivos-baja-padron.transform";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type { MotivoBajaPadronListItem } from "@api/types";

interface MotivoBajaPadronDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  motivoBajaPadronSummary: MotivoBajaPadronListItem | null;
  canEdit: boolean;
}

const DEFAULT_FORM_VALUES: MotivoBajaPadronDetailsFormValues = { name: "" };
const FORM_ID = "motivos-baja-padron-details-form";

export function MotivoBajaPadronDetailsDialog({
  open, onOpenChange, onClose, motivoBajaPadronSummary, canEdit,
}: MotivoBajaPadronDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } = useDetailsDialogCloseGuard(onOpenChange);
  const motivoBajaPadronId = motivoBajaPadronSummary?.id;
  const {
    data: motivoBajaPadronDetailResponse, isLoading, isError, error: motivoBajaPadronDetailError, refetch,
  } = useMotivoBajaPadronDetail(motivoBajaPadronId, open && Boolean(motivoBajaPadronId));

  const motivoBajaPadronDetail = motivoBajaPadronDetailResponse?.motivoBajaPadron;
  const updateMotivoBajaPadron = useUpdateMotivoBajaPadron();

  const form = useForm<MotivoBajaPadronDetailsFormValues>({
    resolver: zodResolver(motivoBajaPadronDetailsSchema),
    defaultValues: DEFAULT_FORM_VALUES,
  });
  const isDirty = form.formState.isDirty;

  useEffect(() => {
    if (!motivoBajaPadronDetail || !open || isDirty) return;
    form.reset(mapMotivoBajaPadronDetailToFormValues(motivoBajaPadronDetail));
  }, [motivoBajaPadronDetail, form, isDirty, open]);

  const closeDialog = () => {
    markClosing();
    form.reset(motivoBajaPadronDetail ? mapMotivoBajaPadronDetailToFormValues(motivoBajaPadronDetail) : DEFAULT_FORM_VALUES);
    onClose?.();
    onOpenChange(false);
  };

  const shouldShowLoading = open && isLoading && !isClosing;
  const shouldShowError = open && !isClosing && (isError || (!isLoading && !motivoBajaPadronDetail));
  const readOnlyMessage = "Solo lectura: no puedes actualizar este registro porque no tienes permisos.";

  const handleSave = async (values: MotivoBajaPadronDetailsFormValues) => {
    if (!motivoBajaPadronDetail || !canEdit) return;
    const payload = buildUpdateMotivoBajaPadronPayload(values, form.formState.dirtyFields);
    if (Object.keys(payload).length === 0) return;

    try {
      await updateMotivoBajaPadron.mutateAsync({ id: motivoBajaPadronDetail.id, data: payload });
      toast.success("Registro actualizado", { description: "Los cambios se guardaron correctamente." });
      form.reset(values);
    } catch (error) {
      toast.error("No se pudo guardar", { description: getMotivoBajaPadronErrorMessage(error, "Error al guardar cambios") });
    }
  };

  const handleStatusChange = async (nextActive: boolean) => {
    if (!motivoBajaPadronDetail || !canEdit) return;
    try {
      await updateMotivoBajaPadron.mutateAsync({ id: motivoBajaPadronDetail.id, data: { isActive: nextActive } });
      toast.success(nextActive ? "Registro activado" : "Registro desactivado");
    } catch (error) {
      toast.error("No se pudo actualizar el estado", { description: getMotivoBajaPadronErrorMessage(error, "Error al actualizar estado") });
    }
  };

  const title = motivoBajaPadronDetail?.name || motivoBajaPadronSummary?.name || "Motivo de Baja de Padrón";
  const isActive = motivoBajaPadronDetail?.isActive ?? motivoBajaPadronSummary?.isActive;
  const statusBadge = typeof isActive === "boolean" ? <CatalogStatusBadge isActive={isActive} /> : null;

  const createdMetaLabel = motivoBajaPadronDetail
    ? `Creado ${formatDate(motivoBajaPadronDetail.createdAt)} por ${motivoBajaPadronDetail.createdBy?.name ?? "-"}`
    : null;
  const createdMeta = createdMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <CalendarDays className="size-4 shrink-0" />
      <span className="truncate" title={createdMetaLabel}>{createdMetaLabel}</span>
    </span>
  ) : null;

  const updatedMetaLabel = motivoBajaPadronDetail?.updatedAt
    ? `Actualizado ${formatDateTime(motivoBajaPadronDetail.updatedAt)} por ${motivoBajaPadronDetail.updatedBy?.name ?? "-"}`
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
        {getMotivoBajaPadronErrorMessage(motivoBajaPadronDetailError, "Intenta nuevamente para ver el detalle completo.")}
      </p>
      <Button variant="outline" size="sm" className="mt-4" onClick={() => void refetch()}>Reintentar</Button>
    </div>
  );

  const sections: AdminDetailsDialogSection[] = motivoBajaPadronDetail
    ? [{
        id: "general",
        label: "General",
        content: (
          <>
            <MotivoBajaPadronDetailsGeneralSection
              form={form}
              formId={FORM_ID}
              motivoBajaPadronDetail={motivoBajaPadronDetail}
              onSubmit={handleSave}
              onStatusChange={handleStatusChange}
              isStatusPending={updateMotivoBajaPadron.isPending}
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
        motivoBajaPadronSummary || motivoBajaPadronDetail ? (
          <MotivoBajaPadronDialogHeader
            title={title}
            status={statusBadge}
            meta={motivoBajaPadronDetail ? <span className="flex min-w-0 flex-wrap gap-3">{createdMeta}{updatedMeta}</span> : null}
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
          isSaving={updateMotivoBajaPadron.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!canEdit}
        />
      )}
    />
  );
}
