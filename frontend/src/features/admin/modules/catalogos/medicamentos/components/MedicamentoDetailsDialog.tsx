import { useEffect } from "react";
import { AlertTriangle, CalendarDays, Pencil } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Separator } from "@shared/ui/separator";
import { Skeleton } from "@shared/ui/skeleton";
import { MedicamentoDetailsGeneralSection } from "@features/admin/modules/catalogos/medicamentos/components/MedicamentoDetailsGeneralSection";
import { MedicamentoDialogHeader } from "@features/admin/modules/catalogos/medicamentos/components/MedicamentoDialogHeader";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import {
  medicamentoDetailsSchema,
  type MedicamentoDetailsFormValues,
} from "@features/admin/modules/catalogos/medicamentos/domain/medicamentos.schemas";
import { useUpdateMedicamento } from "@features/admin/modules/catalogos/medicamentos/mutations/useUpdateMedicamento";
import { useMedicamentoDetail } from "@features/admin/modules/catalogos/medicamentos/queries/useMedicamentoDetail";
import { getMedicamentoErrorMessage } from "@features/admin/modules/catalogos/medicamentos/utils/medicamentos.feedback";
import {
  formatDate,
  formatDateTime,
} from "@features/admin/modules/catalogos/medicamentos/utils/medicamentos.format";
import {
  mapMedicamentoDetailToFormValues,
  buildUpdateMedicamentoPayload,
} from "@features/admin/modules/catalogos/medicamentos/utils/medicamentos.transform";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type { MedicamentoListItem } from "@api/types";

interface MedicamentoDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  medicamentoSummary: MedicamentoListItem | null;
  canEdit: boolean;
}

const DEFAULT_FORM_VALUES = mapMedicamentoDetailToFormValues(null);

const FORM_ID = "medicamento-details-form";

export function MedicamentoDetailsDialog({
  open,
  onOpenChange,
  onClose,
  medicamentoSummary,
  canEdit,
}: MedicamentoDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } =
    useDetailsDialogCloseGuard(onOpenChange);
  const medicamentoId = medicamentoSummary?.id;
  const {
    data: medicamentoDetailResponse,
    isLoading,
    isError,
    error: medicamentoDetailError,
    refetch,
  } = useMedicamentoDetail(medicamentoId, open && Boolean(medicamentoId));

  const medicamentoDetail = medicamentoDetailResponse?.medication;
  const updateMedicamento = useUpdateMedicamento();

  const form = useForm<MedicamentoDetailsFormValues>({
    resolver: zodResolver(medicamentoDetailsSchema),
    defaultValues: DEFAULT_FORM_VALUES,
  });
  const isDirty = form.formState.isDirty;

  useEffect(() => {
    if (!medicamentoDetail || !open || isDirty) return;
    form.reset(mapMedicamentoDetailToFormValues(medicamentoDetail));
  }, [medicamentoDetail, form, isDirty, open]);

  const closeDialog = () => {
    markClosing();
    form.reset(
      medicamentoDetail
        ? mapMedicamentoDetailToFormValues(medicamentoDetail)
        : DEFAULT_FORM_VALUES,
    );
    onClose?.();
    onOpenChange(false);
  };

  const shouldShowLoading = open && isLoading && !isClosing;
  const shouldShowError =
    open && !isClosing && (isError || (!isLoading && !medicamentoDetail));
  const readOnlyMessage =
    "Solo lectura: no puedes actualizar este medicamento porque no tienes permisos.";

  const handleSave = async (values: MedicamentoDetailsFormValues) => {
    if (!medicamentoDetail || !canEdit) return;
    const payload = buildUpdateMedicamentoPayload(values, form.formState.dirtyFields);

    if (Object.keys(payload).length === 0) return;

    try {
      await updateMedicamento.mutateAsync({ id: medicamentoDetail.id, data: payload });
      toast.success("Medicamento actualizado", {
        description: "Los cambios se guardaron correctamente.",
      });
      form.reset(values);
    } catch (error) {
      toast.error("No se pudo guardar", {
        description: getMedicamentoErrorMessage(error, "Error al guardar cambios"),
      });
    }
  };

  const handleStatusChange = async (nextActive: boolean) => {
    if (!medicamentoDetail || !canEdit) return;

    try {
      await updateMedicamento.mutateAsync({
        id: medicamentoDetail.id,
        data: { isActive: nextActive },
      });
      toast.success(nextActive ? "Medicamento activado" : "Medicamento desactivado");
    } catch (error) {
      toast.error("No se pudo actualizar el estado", {
        description: getMedicamentoErrorMessage(error, "Error al actualizar estado"),
      });
    }
  };

  const title = medicamentoDetail?.name || medicamentoSummary?.name || "Medicamento";
  const subtitle = medicamentoDetail?.code || medicamentoSummary?.code || null;
  const isActive = medicamentoDetail?.isActive ?? medicamentoSummary?.isActive;

  const statusBadge =
    typeof isActive === "boolean" ? (
      <CatalogStatusBadge isActive={isActive} />
    ) : null;

  const createdMetaLabel = medicamentoDetail
    ? `Creado ${formatDate(medicamentoDetail.createdAt)} por ${medicamentoDetail.createdBy?.name ?? "-"}`
    : null;

  const createdMeta = createdMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <CalendarDays className="size-4 shrink-0" />
      <span className="truncate" title={createdMetaLabel}>
        {createdMetaLabel}
      </span>
    </span>
  ) : null;

  const updatedMetaLabel = medicamentoDetail?.updatedAt
    ? `Actualizado ${formatDateTime(medicamentoDetail.updatedAt)} por ${medicamentoDetail.updatedBy?.name ?? "-"}`
    : null;

  const updatedMeta = updatedMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <Pencil className="size-4 shrink-0" />
      <span className="truncate" title={updatedMetaLabel}>
        {updatedMetaLabel}
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
        No se pudo cargar el medicamento
      </h3>
      <p className="mt-1 text-sm text-txt-muted">
        {getMedicamentoErrorMessage(
          medicamentoDetailError,
          "Intenta nuevamente para ver el detalle completo.",
        )}
      </p>
      <Button
        variant="outline"
        size="sm"
        className="mt-4"
        onClick={() => void refetch()}
      >
        Reintentar
      </Button>
    </div>
  );

  const sections: AdminDetailsDialogSection[] = medicamentoDetail
    ? [
        {
          id: "general",
          label: "General",
          content: (
            <>
              <MedicamentoDetailsGeneralSection
                form={form}
                formId={FORM_ID}
                medicamentoDetail={medicamentoDetail}
                onSubmit={handleSave}
                onStatusChange={handleStatusChange}
                isStatusPending={updateMedicamento.isPending}
                isEditable={canEdit}
              />
              {!canEdit ? (
                <AdminReadOnlyNotice message={readOnlyMessage} />
              ) : null}
            </>
          ),
        },
      ]
    : [];

  return (
    <AdminDetailsDialogShell
      open={open}
      onOpenChange={handleOpenChange}
      onRequestClose={closeDialog}
      titleSrOnly="Detalle de medicamento"
      descriptionSrOnly="Gestiona la configuracion de este medicamento."
      header={
        medicamentoSummary || medicamentoDetail ? (
          <MedicamentoDialogHeader
            title={title}
            subtitle={subtitle}
            status={statusBadge}
            meta={
              medicamentoDetail ? (
                <span className="flex min-w-0 flex-wrap gap-3">
                  {createdMeta}
                  {updatedMeta}
                </span>
              ) : null
            }
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
          isSaving={updateMedicamento.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!canEdit}
        />
      )}
    />
  );
}
