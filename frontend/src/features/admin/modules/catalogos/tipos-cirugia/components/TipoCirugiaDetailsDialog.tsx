import { useEffect } from "react";
import { AlertTriangle, CalendarDays, Pencil } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Separator } from "@shared/ui/separator";
import { Skeleton } from "@shared/ui/skeleton";
import { TipoCirugiaDetailsGeneralSection } from "@features/admin/modules/catalogos/tipos-cirugia/components/TipoCirugiaDetailsGeneralSection";
import { TipoCirugiaDialogHeader } from "@features/admin/modules/catalogos/tipos-cirugia/components/TipoCirugiaDialogHeader";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import {
  tipoCirugiaDetailsSchema,
  type TipoCirugiaDetailsFormValues,
} from "@features/admin/modules/catalogos/tipos-cirugia/domain/tipos-cirugia.schemas";
import { useUpdateTipoCirugia } from "@features/admin/modules/catalogos/tipos-cirugia/mutations/useUpdateTipoCirugia";
import { useTipoCirugiaDetail } from "@features/admin/modules/catalogos/tipos-cirugia/queries/useTipoCirugiaDetail";
import { getTipoCirugiaErrorMessage } from "@features/admin/modules/catalogos/tipos-cirugia/utils/tipos-cirugia.feedback";
import {
  formatDate,
  formatDateTime,
} from "@features/admin/modules/catalogos/tipos-cirugia/utils/tipos-cirugia.format";
import {
  mapTipoCirugiaDetailToFormValues,
  buildUpdateTipoCirugiaPayload,
} from "@features/admin/modules/catalogos/tipos-cirugia/utils/tipos-cirugia.transform";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type { TipoCirugiaListItem } from "@api/types";

interface TipoCirugiaDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  tipoCirugiaSummary: TipoCirugiaListItem | null;
  canEdit: boolean;
}

const DEFAULT_FORM_VALUES: TipoCirugiaDetailsFormValues = { name: "" };
const FORM_ID = "tipos-cirugia-details-form";

export function TipoCirugiaDetailsDialog({
  open, onOpenChange, onClose, tipoCirugiaSummary, canEdit,
}: TipoCirugiaDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } = useDetailsDialogCloseGuard(onOpenChange);
  const tipoCirugiaId = tipoCirugiaSummary?.id;
  const {
    data: tipoCirugiaDetailResponse, isLoading, isError, error: tipoCirugiaDetailError, refetch,
  } = useTipoCirugiaDetail(tipoCirugiaId, open && Boolean(tipoCirugiaId));

  const tipoCirugiaDetail = tipoCirugiaDetailResponse?.tipoCirugia;
  const updateTipoCirugia = useUpdateTipoCirugia();

  const form = useForm<TipoCirugiaDetailsFormValues>({
    resolver: zodResolver(tipoCirugiaDetailsSchema),
    defaultValues: DEFAULT_FORM_VALUES,
  });
  const isDirty = form.formState.isDirty;

  useEffect(() => {
    if (!tipoCirugiaDetail || !open || isDirty) return;
    form.reset(mapTipoCirugiaDetailToFormValues(tipoCirugiaDetail));
  }, [tipoCirugiaDetail, form, isDirty, open]);

  const closeDialog = () => {
    markClosing();
    form.reset(tipoCirugiaDetail ? mapTipoCirugiaDetailToFormValues(tipoCirugiaDetail) : DEFAULT_FORM_VALUES);
    onClose?.();
    onOpenChange(false);
  };

  const shouldShowLoading = open && isLoading && !isClosing;
  const shouldShowError = open && !isClosing && (isError || (!isLoading && !tipoCirugiaDetail));
  const readOnlyMessage = "Solo lectura: no puedes actualizar este registro porque no tienes permisos.";

  const handleSave = async (values: TipoCirugiaDetailsFormValues) => {
    if (!tipoCirugiaDetail || !canEdit) return;
    const payload = buildUpdateTipoCirugiaPayload(values, form.formState.dirtyFields);
    if (Object.keys(payload).length === 0) return;

    try {
      await updateTipoCirugia.mutateAsync({ id: tipoCirugiaDetail.id, data: payload });
      toast.success("Registro actualizado", { description: "Los cambios se guardaron correctamente." });
      form.reset(values);
    } catch (error) {
      toast.error("No se pudo guardar", { description: getTipoCirugiaErrorMessage(error, "Error al guardar cambios") });
    }
  };

  const handleStatusChange = async (nextActive: boolean) => {
    if (!tipoCirugiaDetail || !canEdit) return;
    try {
      await updateTipoCirugia.mutateAsync({ id: tipoCirugiaDetail.id, data: { isActive: nextActive } });
      toast.success(nextActive ? "Registro activado" : "Registro desactivado");
    } catch (error) {
      toast.error("No se pudo actualizar el estado", { description: getTipoCirugiaErrorMessage(error, "Error al actualizar estado") });
    }
  };

  const title = tipoCirugiaDetail?.name || tipoCirugiaSummary?.name || "Tipo de Cirugía";
  const isActive = tipoCirugiaDetail?.isActive ?? tipoCirugiaSummary?.isActive;
  const statusBadge = typeof isActive === "boolean" ? <CatalogStatusBadge isActive={isActive} /> : null;

  const createdMetaLabel = tipoCirugiaDetail
    ? `Creado ${formatDate(tipoCirugiaDetail.createdAt)} por ${tipoCirugiaDetail.createdBy?.name ?? "-"}`
    : null;
  const createdMeta = createdMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <CalendarDays className="size-4 shrink-0" />
      <span className="truncate" title={createdMetaLabel}>{createdMetaLabel}</span>
    </span>
  ) : null;

  const updatedMetaLabel = tipoCirugiaDetail?.updatedAt
    ? `Actualizado ${formatDateTime(tipoCirugiaDetail.updatedAt)} por ${tipoCirugiaDetail.updatedBy?.name ?? "-"}`
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
        {getTipoCirugiaErrorMessage(tipoCirugiaDetailError, "Intenta nuevamente para ver el detalle completo.")}
      </p>
      <Button variant="outline" size="sm" className="mt-4" onClick={() => void refetch()}>Reintentar</Button>
    </div>
  );

  const sections: AdminDetailsDialogSection[] = tipoCirugiaDetail
    ? [{
        id: "general",
        label: "General",
        content: (
          <>
            <TipoCirugiaDetailsGeneralSection
              form={form}
              formId={FORM_ID}
              tipoCirugiaDetail={tipoCirugiaDetail}
              onSubmit={handleSave}
              onStatusChange={handleStatusChange}
              isStatusPending={updateTipoCirugia.isPending}
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
        tipoCirugiaSummary || tipoCirugiaDetail ? (
          <TipoCirugiaDialogHeader
            title={title}
            status={statusBadge}
            meta={tipoCirugiaDetail ? <span className="flex min-w-0 flex-wrap gap-3">{createdMeta}{updatedMeta}</span> : null}
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
          isSaving={updateTipoCirugia.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!canEdit}
        />
      )}
    />
  );
}
