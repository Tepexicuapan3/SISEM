import { useEffect } from "react";
import { AlertTriangle, CalendarDays, Pencil } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Separator } from "@shared/ui/separator";
import { Skeleton } from "@shared/ui/skeleton";
import { DestinoAmbulanciaDetailsGeneralSection } from "@features/admin/modules/catalogos/destinos-ambulancia/components/DestinoAmbulanciaDetailsGeneralSection";
import { DestinoAmbulanciaDialogHeader } from "@features/admin/modules/catalogos/destinos-ambulancia/components/DestinoAmbulanciaDialogHeader";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import {
  destinoAmbulanciaDetailsSchema,
  type DestinoAmbulanciaDetailsFormValues,
} from "@features/admin/modules/catalogos/destinos-ambulancia/domain/destinos-ambulancia.schemas";
import { useUpdateDestinoAmbulancia } from "@features/admin/modules/catalogos/destinos-ambulancia/mutations/useUpdateDestinoAmbulancia";
import { useDestinoAmbulanciaDetail } from "@features/admin/modules/catalogos/destinos-ambulancia/queries/useDestinoAmbulanciaDetail";
import { getDestinoAmbulanciaErrorMessage } from "@features/admin/modules/catalogos/destinos-ambulancia/utils/destinos-ambulancia.feedback";
import {
  formatDate,
  formatDateTime,
} from "@features/admin/modules/catalogos/destinos-ambulancia/utils/destinos-ambulancia.format";
import {
  mapDestinoAmbulanciaDetailToFormValues,
  buildUpdateDestinoAmbulanciaPayload,
} from "@features/admin/modules/catalogos/destinos-ambulancia/utils/destinos-ambulancia.transform";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type { DestinoAmbulanciaListItem } from "@api/types";

interface DestinoAmbulanciaDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  destinoAmbulanciaSummary: DestinoAmbulanciaListItem | null;
  canEdit: boolean;
}

const DEFAULT_FORM_VALUES: DestinoAmbulanciaDetailsFormValues = {
  name: "", street: "", zipCode: "", neighborhood: "", borough: "", phone: "", reference: "",
};
const FORM_ID = "destinos-ambulancia-details-form";

export function DestinoAmbulanciaDetailsDialog({
  open, onOpenChange, onClose, destinoAmbulanciaSummary, canEdit,
}: DestinoAmbulanciaDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } = useDetailsDialogCloseGuard(onOpenChange);
  const destinoAmbulanciaId = destinoAmbulanciaSummary?.id;
  const {
    data: destinoAmbulanciaDetailResponse, isLoading, isError, error: destinoAmbulanciaDetailError, refetch,
  } = useDestinoAmbulanciaDetail(destinoAmbulanciaId, open && Boolean(destinoAmbulanciaId));

  const destinoAmbulanciaDetail = destinoAmbulanciaDetailResponse?.destinoAmbulancia;
  const updateDestinoAmbulancia = useUpdateDestinoAmbulancia();

  const form = useForm<DestinoAmbulanciaDetailsFormValues>({
    resolver: zodResolver(destinoAmbulanciaDetailsSchema),
    defaultValues: DEFAULT_FORM_VALUES,
  });
  const isDirty = form.formState.isDirty;

  useEffect(() => {
    if (!destinoAmbulanciaDetail || !open || isDirty) return;
    form.reset(mapDestinoAmbulanciaDetailToFormValues(destinoAmbulanciaDetail));
  }, [destinoAmbulanciaDetail, form, isDirty, open]);

  const closeDialog = () => {
    markClosing();
    form.reset(destinoAmbulanciaDetail ? mapDestinoAmbulanciaDetailToFormValues(destinoAmbulanciaDetail) : DEFAULT_FORM_VALUES);
    onClose?.();
    onOpenChange(false);
  };

  const shouldShowLoading = open && isLoading && !isClosing;
  const shouldShowError = open && !isClosing && (isError || (!isLoading && !destinoAmbulanciaDetail));
  const readOnlyMessage = "Solo lectura: no puedes actualizar este destino porque no tienes permisos.";

  const handleSave = async (values: DestinoAmbulanciaDetailsFormValues) => {
    if (!destinoAmbulanciaDetail || !canEdit) return;
    const payload = buildUpdateDestinoAmbulanciaPayload(values, form.formState.dirtyFields);
    if (Object.keys(payload).length === 0) return;

    try {
      await updateDestinoAmbulancia.mutateAsync({ id: destinoAmbulanciaDetail.id, data: payload });
      toast.success("Destino actualizado", { description: "Los cambios se guardaron correctamente." });
      form.reset(values);
    } catch (error) {
      toast.error("No se pudo guardar", { description: getDestinoAmbulanciaErrorMessage(error, "Error al guardar cambios") });
    }
  };

  const handleStatusChange = async (nextActive: boolean) => {
    if (!destinoAmbulanciaDetail || !canEdit) return;
    try {
      await updateDestinoAmbulancia.mutateAsync({ id: destinoAmbulanciaDetail.id, data: { isActive: nextActive } });
      toast.success(nextActive ? "Destino activado" : "Destino desactivado");
    } catch (error) {
      toast.error("No se pudo actualizar el estado", { description: getDestinoAmbulanciaErrorMessage(error, "Error al actualizar estado") });
    }
  };

  const title = destinoAmbulanciaDetail?.name || destinoAmbulanciaSummary?.name || "Destino de Ambulancia";
  const isActive = destinoAmbulanciaDetail?.isActive ?? destinoAmbulanciaSummary?.isActive;
  const statusBadge = typeof isActive === "boolean" ? <CatalogStatusBadge isActive={isActive} /> : null;

  const createdMetaLabel = destinoAmbulanciaDetail
    ? `Creado ${formatDate(destinoAmbulanciaDetail.createdAt)} por ${destinoAmbulanciaDetail.createdBy?.name ?? "-"}`
    : null;
  const createdMeta = createdMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <CalendarDays className="size-4 shrink-0" />
      <span className="truncate" title={createdMetaLabel}>{createdMetaLabel}</span>
    </span>
  ) : null;

  const updatedMetaLabel = destinoAmbulanciaDetail?.updatedAt
    ? `Actualizado ${formatDateTime(destinoAmbulanciaDetail.updatedAt)} por ${destinoAmbulanciaDetail.updatedBy?.name ?? "-"}`
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
      <h3 className="mt-4 text-base font-semibold text-txt-body">No se pudo cargar el destino</h3>
      <p className="mt-1 text-sm text-txt-muted">
        {getDestinoAmbulanciaErrorMessage(destinoAmbulanciaDetailError, "Intenta nuevamente para ver el detalle completo.")}
      </p>
      <Button variant="outline" size="sm" className="mt-4" onClick={() => void refetch()}>Reintentar</Button>
    </div>
  );

  const sections: AdminDetailsDialogSection[] = destinoAmbulanciaDetail
    ? [{
        id: "general",
        label: "General",
        content: (
          <>
            <DestinoAmbulanciaDetailsGeneralSection
              form={form}
              formId={FORM_ID}
              destinoAmbulanciaDetail={destinoAmbulanciaDetail}
              onSubmit={handleSave}
              onStatusChange={handleStatusChange}
              isStatusPending={updateDestinoAmbulancia.isPending}
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
      titleSrOnly="Detalle de destino de ambulancia"
      descriptionSrOnly="Gestiona la configuracion de este destino."
      header={
        destinoAmbulanciaSummary || destinoAmbulanciaDetail ? (
          <DestinoAmbulanciaDialogHeader
            title={title}
            status={statusBadge}
            meta={destinoAmbulanciaDetail ? <span className="flex min-w-0 flex-wrap gap-3">{createdMeta}{updatedMeta}</span> : null}
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
          isSaving={updateDestinoAmbulancia.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!canEdit}
        />
      )}
    />
  );
}
