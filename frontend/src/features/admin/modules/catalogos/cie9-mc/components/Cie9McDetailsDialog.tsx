import { useEffect } from "react";
import { AlertTriangle, CalendarDays, Pencil } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Separator } from "@shared/ui/separator";
import { Skeleton } from "@shared/ui/skeleton";
import { Cie9McDetailsGeneralSection } from "@features/admin/modules/catalogos/cie9-mc/components/Cie9McDetailsGeneralSection";
import { Cie9McDialogHeader } from "@features/admin/modules/catalogos/cie9-mc/components/Cie9McDialogHeader";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import {
  cie9McDetailsSchema,
  type Cie9McDetailsFormValues,
} from "@features/admin/modules/catalogos/cie9-mc/domain/cie9-mc.schemas";
import { useUpdateCie9Mc } from "@features/admin/modules/catalogos/cie9-mc/mutations/useUpdateCie9Mc";
import { useCie9McDetail } from "@features/admin/modules/catalogos/cie9-mc/queries/useCie9McDetail";
import { getCie9McErrorMessage } from "@features/admin/modules/catalogos/cie9-mc/utils/cie9-mc.feedback";
import {
  formatDate,
  formatDateTime,
} from "@features/admin/modules/catalogos/cie9-mc/utils/cie9-mc.format";
import {
  mapCie9McDetailToFormValues,
  buildUpdateCie9McPayload,
} from "@features/admin/modules/catalogos/cie9-mc/utils/cie9-mc.transform";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type { Cie9McListItem } from "@api/types";

interface Cie9McDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  cie9McSummary: Cie9McListItem | null;
  canEdit: boolean;
}

const DEFAULT_FORM_VALUES: Cie9McDetailsFormValues = {
  name: "",
  code: "",
};

const FORM_ID = "cie9-mc-details-form";

export function Cie9McDetailsDialog({
  open,
  onOpenChange,
  onClose,
  cie9McSummary,
  canEdit,
}: Cie9McDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } =
    useDetailsDialogCloseGuard(onOpenChange);
  const cie9McId = cie9McSummary?.id;
  const {
    data: cie9McDetailResponse,
    isLoading,
    isError,
    error: cie9McDetailError,
    refetch,
  } = useCie9McDetail(cie9McId, open && Boolean(cie9McId));

  const cie9McDetail = cie9McDetailResponse?.cie9Mc;
  const updateCie9Mc = useUpdateCie9Mc();

  const form = useForm<Cie9McDetailsFormValues>({
    resolver: zodResolver(cie9McDetailsSchema),
    defaultValues: DEFAULT_FORM_VALUES,
  });
  const isDirty = form.formState.isDirty;

  useEffect(() => {
    if (!cie9McDetail || !open || isDirty) return;
    form.reset(mapCie9McDetailToFormValues(cie9McDetail));
  }, [cie9McDetail, form, isDirty, open]);

  const closeDialog = () => {
    markClosing();
    form.reset(
      cie9McDetail
        ? mapCie9McDetailToFormValues(cie9McDetail)
        : DEFAULT_FORM_VALUES,
    );
    onClose?.();
    onOpenChange(false);
  };

  const shouldShowLoading = open && isLoading && !isClosing;
  const shouldShowError =
    open && !isClosing && (isError || (!isLoading && !cie9McDetail));
  const readOnlyMessage =
    "Solo lectura: no puedes actualizar este código porque no tienes permisos.";

  const handleSave = async (values: Cie9McDetailsFormValues) => {
    if (!cie9McDetail || !canEdit) return;
    const payload = buildUpdateCie9McPayload(values, form.formState.dirtyFields);

    if (Object.keys(payload).length === 0) return;

    try {
      await updateCie9Mc.mutateAsync({ id: cie9McDetail.id, data: payload });
      toast.success("Código actualizado", {
        description: "Los cambios se guardaron correctamente.",
      });
      form.reset(values);
    } catch (error) {
      toast.error("No se pudo guardar", {
        description: getCie9McErrorMessage(error, "Error al guardar cambios"),
      });
    }
  };

  const handleStatusChange = async (nextActive: boolean) => {
    if (!cie9McDetail || !canEdit) return;

    try {
      await updateCie9Mc.mutateAsync({
        id: cie9McDetail.id,
        data: { isActive: nextActive },
      });
      toast.success(nextActive ? "Código activado" : "Código desactivado");
    } catch (error) {
      toast.error("No se pudo actualizar el estado", {
        description: getCie9McErrorMessage(
          error,
          "Error al actualizar estado",
        ),
      });
    }
  };

  const title = cie9McDetail?.code || cie9McSummary?.code || "CIE-9-MC";
  const subtitle = cie9McDetail?.name || cie9McSummary?.name || null;
  const isActive = cie9McDetail?.isActive ?? cie9McSummary?.isActive;

  const statusBadge =
    typeof isActive === "boolean" ? (
      <CatalogStatusBadge isActive={isActive} />
    ) : null;

  const createdMetaLabel = cie9McDetail
    ? `Creado ${formatDate(cie9McDetail.createdAt)} por ${cie9McDetail.createdBy?.name ?? "-"}`
    : null;

  const createdMeta = createdMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <CalendarDays className="size-4 shrink-0" />
      <span className="truncate" title={createdMetaLabel}>
        {createdMetaLabel}
      </span>
    </span>
  ) : null;

  const updatedMetaLabel = cie9McDetail?.updatedAt
    ? `Actualizado ${formatDateTime(cie9McDetail.updatedAt)} por ${cie9McDetail.updatedBy?.name ?? "-"}`
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
        {Array.from({ length: 4 }).map((_, index) => (
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
        No se pudo cargar el código
      </h3>
      <p className="mt-1 text-sm text-txt-muted">
        {getCie9McErrorMessage(
          cie9McDetailError,
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

  const sections: AdminDetailsDialogSection[] = cie9McDetail
    ? [
        {
          id: "general",
          label: "General",
          content: (
            <>
              <Cie9McDetailsGeneralSection
                form={form}
                formId={FORM_ID}
                cie9McDetail={cie9McDetail}
                onSubmit={handleSave}
                onStatusChange={handleStatusChange}
                isStatusPending={updateCie9Mc.isPending}
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
      titleSrOnly="Detalle de código CIE-9-MC"
      descriptionSrOnly="Gestiona la configuración de este código."
      header={
        cie9McSummary || cie9McDetail ? (
          <Cie9McDialogHeader
            title={title}
            subtitle={subtitle}
            status={statusBadge}
            meta={
              cie9McDetail ? (
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
          isSaving={updateCie9Mc.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!canEdit}
        />
      )}
    />
  );
}
