import { useEffect } from "react";
import { AlertTriangle, CalendarDays, Pencil } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Separator } from "@shared/ui/separator";
import { Skeleton } from "@shared/ui/skeleton";
import { TipoServicioAmbulanciaDetailsGeneralSection } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/components/TipoServicioAmbulanciaDetailsGeneralSection";
import { TipoServicioAmbulanciaDialogHeader } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/components/TipoServicioAmbulanciaDialogHeader";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogStatusBadge } from "@features/admin/modules/catalogos/shared/components/CatalogStatusBadge";
import {
  tipoServicioAmbulanciaDetailsSchema,
  type TipoServicioAmbulanciaDetailsFormValues,
} from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/domain/tipos-servicio-ambulancia.schemas";
import { useUpdateTipoServicioAmbulancia } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/mutations/useUpdateTipoServicioAmbulancia";
import { useTipoServicioAmbulanciaDetail } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/queries/useTipoServicioAmbulanciaDetail";
import { getTipoServicioAmbulanciaErrorMessage } from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/utils/tipos-servicio-ambulancia.feedback";
import {
  formatDate,
  formatDateTime,
} from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/utils/tipos-servicio-ambulancia.format";
import {
  mapTipoServicioAmbulanciaDetailToFormValues,
  buildUpdateTipoServicioAmbulanciaPayload,
} from "@features/admin/modules/catalogos/tipos-servicio-ambulancia/utils/tipos-servicio-ambulancia.transform";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type { TipoServicioAmbulanciaListItem } from "@api/types";

interface TipoServicioAmbulanciaDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  tipoServicioAmbulanciaSummary: TipoServicioAmbulanciaListItem | null;
  canEdit: boolean;
}

const DEFAULT_FORM_VALUES: TipoServicioAmbulanciaDetailsFormValues = { name: "" };
const FORM_ID = "tipos-servicio-ambulancia-details-form";

export function TipoServicioAmbulanciaDetailsDialog({
  open, onOpenChange, onClose, tipoServicioAmbulanciaSummary, canEdit,
}: TipoServicioAmbulanciaDetailsDialogProps) {
  const { isClosing, markClosing, handleOpenChange } = useDetailsDialogCloseGuard(onOpenChange);
  const tipoServicioAmbulanciaId = tipoServicioAmbulanciaSummary?.id;
  const {
    data: tipoServicioAmbulanciaDetailResponse, isLoading, isError, error: tipoServicioAmbulanciaDetailError, refetch,
  } = useTipoServicioAmbulanciaDetail(tipoServicioAmbulanciaId, open && Boolean(tipoServicioAmbulanciaId));

  const tipoServicioAmbulanciaDetail = tipoServicioAmbulanciaDetailResponse?.tipoServicioAmbulancia;
  const updateTipoServicioAmbulancia = useUpdateTipoServicioAmbulancia();

  const form = useForm<TipoServicioAmbulanciaDetailsFormValues>({
    resolver: zodResolver(tipoServicioAmbulanciaDetailsSchema),
    defaultValues: DEFAULT_FORM_VALUES,
  });
  const isDirty = form.formState.isDirty;

  useEffect(() => {
    if (!tipoServicioAmbulanciaDetail || !open || isDirty) return;
    form.reset(mapTipoServicioAmbulanciaDetailToFormValues(tipoServicioAmbulanciaDetail));
  }, [tipoServicioAmbulanciaDetail, form, isDirty, open]);

  const closeDialog = () => {
    markClosing();
    form.reset(tipoServicioAmbulanciaDetail ? mapTipoServicioAmbulanciaDetailToFormValues(tipoServicioAmbulanciaDetail) : DEFAULT_FORM_VALUES);
    onClose?.();
    onOpenChange(false);
  };

  const shouldShowLoading = open && isLoading && !isClosing;
  const shouldShowError = open && !isClosing && (isError || (!isLoading && !tipoServicioAmbulanciaDetail));
  const readOnlyMessage = "Solo lectura: no puedes actualizar este registro porque no tienes permisos.";

  const handleSave = async (values: TipoServicioAmbulanciaDetailsFormValues) => {
    if (!tipoServicioAmbulanciaDetail || !canEdit) return;
    const payload = buildUpdateTipoServicioAmbulanciaPayload(values, form.formState.dirtyFields);
    if (Object.keys(payload).length === 0) return;

    try {
      await updateTipoServicioAmbulancia.mutateAsync({ id: tipoServicioAmbulanciaDetail.id, data: payload });
      toast.success("Registro actualizado", { description: "Los cambios se guardaron correctamente." });
      form.reset(values);
    } catch (error) {
      toast.error("No se pudo guardar", { description: getTipoServicioAmbulanciaErrorMessage(error, "Error al guardar cambios") });
    }
  };

  const handleStatusChange = async (nextActive: boolean) => {
    if (!tipoServicioAmbulanciaDetail || !canEdit) return;
    try {
      await updateTipoServicioAmbulancia.mutateAsync({ id: tipoServicioAmbulanciaDetail.id, data: { isActive: nextActive } });
      toast.success(nextActive ? "Registro activado" : "Registro desactivado");
    } catch (error) {
      toast.error("No se pudo actualizar el estado", { description: getTipoServicioAmbulanciaErrorMessage(error, "Error al actualizar estado") });
    }
  };

  const title = tipoServicioAmbulanciaDetail?.name || tipoServicioAmbulanciaSummary?.name || "Tipo de Servicio de Ambulancia";
  const isActive = tipoServicioAmbulanciaDetail?.isActive ?? tipoServicioAmbulanciaSummary?.isActive;
  const statusBadge = typeof isActive === "boolean" ? <CatalogStatusBadge isActive={isActive} /> : null;

  const createdMetaLabel = tipoServicioAmbulanciaDetail
    ? `Creado ${formatDate(tipoServicioAmbulanciaDetail.createdAt)} por ${tipoServicioAmbulanciaDetail.createdBy?.name ?? "-"}`
    : null;
  const createdMeta = createdMetaLabel ? (
    <span className="inline-flex max-w-full min-w-0 items-center gap-2">
      <CalendarDays className="size-4 shrink-0" />
      <span className="truncate" title={createdMetaLabel}>{createdMetaLabel}</span>
    </span>
  ) : null;

  const updatedMetaLabel = tipoServicioAmbulanciaDetail?.updatedAt
    ? `Actualizado ${formatDateTime(tipoServicioAmbulanciaDetail.updatedAt)} por ${tipoServicioAmbulanciaDetail.updatedBy?.name ?? "-"}`
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
        {getTipoServicioAmbulanciaErrorMessage(tipoServicioAmbulanciaDetailError, "Intenta nuevamente para ver el detalle completo.")}
      </p>
      <Button variant="outline" size="sm" className="mt-4" onClick={() => void refetch()}>Reintentar</Button>
    </div>
  );

  const sections: AdminDetailsDialogSection[] = tipoServicioAmbulanciaDetail
    ? [{
        id: "general",
        label: "General",
        content: (
          <>
            <TipoServicioAmbulanciaDetailsGeneralSection
              form={form}
              formId={FORM_ID}
              tipoServicioAmbulanciaDetail={tipoServicioAmbulanciaDetail}
              onSubmit={handleSave}
              onStatusChange={handleStatusChange}
              isStatusPending={updateTipoServicioAmbulancia.isPending}
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
        tipoServicioAmbulanciaSummary || tipoServicioAmbulanciaDetail ? (
          <TipoServicioAmbulanciaDialogHeader
            title={title}
            status={statusBadge}
            meta={tipoServicioAmbulanciaDetail ? <span className="flex min-w-0 flex-wrap gap-3">{createdMeta}{updatedMeta}</span> : null}
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
          isSaving={updateTipoServicioAmbulancia.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!canEdit}
        />
      )}
    />
  );
}
