import { useEffect, useMemo } from "react";
import { SlidersHorizontal } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Badge } from "@shared/ui/badge";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Separator } from "@shared/ui/separator";
import { CatalogDetailsFooter } from "@features/admin/modules/catalogos/shared/components/CatalogDetailsFooter";
import { CatalogDialogHeader } from "@features/admin/modules/catalogos/shared/components/CatalogDialogHeader";
import { ParametroCentrosSection } from "@features/admin/modules/catalogos/parametros/components/ParametroCentrosSection";
import { ParametroValueInput } from "@features/admin/modules/catalogos/parametros/components/ParametroValueInput";
import {
  TIPO_LABELS,
  describeLimits,
  moduleLabel,
} from "@features/admin/modules/catalogos/parametros/domain/parametro.value";
import {
  buildParametroValueSchema,
  type ParametroValueFormValues,
} from "@features/admin/modules/catalogos/parametros/domain/parametros.schemas";
import { useUpdateParametroGeneral } from "@features/admin/modules/catalogos/parametros/queries/useParametros";
import { getParametroErrorMessage } from "@features/admin/modules/catalogos/parametros/utils/parametro.feedback";
import { AdminReadOnlyNotice } from "@features/admin/shared/components/AdminReadOnlyNotice";
import { AdminDetailsDialogShell } from "@features/admin/shared/components/details/AdminDetailsDialogShell";
import { useDetailsDialogCloseGuard } from "@features/admin/shared/hooks/useDetailsDialogCloseGuard";
import type { AdminDetailsDialogSection } from "@features/admin/shared/types/details-dialog.types";
import type { Parametro } from "@api/types/catalogos/parameters.types";

interface ParametroDetailsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClose?: () => void;
  /** Version fresca del listado (se invalida tras cada cambio). */
  parametro: Parametro | null;
  canEdit: boolean;
}

const FORM_ID = "parametro-details-form";
const NO_RULES = { valueType: "TEXTO", minValue: null, maxValue: null } as const;

export function ParametroDetailsDialog({
  open,
  onOpenChange,
  onClose,
  parametro,
  canEdit,
}: ParametroDetailsDialogProps) {
  const { markClosing, handleOpenChange } = useDetailsDialogCloseGuard(onOpenChange);
  const updateGeneral = useUpdateParametroGeneral();

  const valueType = parametro?.valueType ?? NO_RULES.valueType;
  const minValue = parametro?.minValue ?? null;
  const maxValue = parametro?.maxValue ?? null;
  const schema = useMemo(
    () => buildParametroValueSchema({ valueType, minValue, maxValue }),
    [valueType, minValue, maxValue],
  );

  const form = useForm<ParametroValueFormValues>({
    resolver: zodResolver(schema),
    mode: "onChange",
    defaultValues: { value: parametro?.generalValue ?? "" },
  });

  const isDirty = form.formState.isDirty;

  useEffect(() => {
    if (!parametro || !open || isDirty) return;
    form.reset({ value: parametro.generalValue });
  }, [parametro, form, isDirty, open]);

  if (!parametro) return null;

  const limits = describeLimits(parametro);

  const closeDialog = () => {
    markClosing();
    form.reset({ value: parametro.generalValue });
    onClose?.();
    onOpenChange(false);
  };

  const handleSave = async (values: ParametroValueFormValues) => {
    if (!canEdit) return;
    try {
      await updateGeneral.mutateAsync({ key: parametro.key, value: values.value });
      toast.success("Parámetro actualizado", { description: parametro.description });
      form.reset(values);
    } catch (mutationError) {
      toast.error("No se pudo guardar", {
        description: getParametroErrorMessage(mutationError, "Error al guardar el parámetro"),
      });
    }
  };

  const sections: AdminDetailsDialogSection[] = [
    {
      id: "general",
      label: "General",
      content: (
        <Form {...form}>
          <form id={FORM_ID} onSubmit={form.handleSubmit(handleSave)} className="space-y-6">
            <FormField
              control={form.control}
              name="value"
              render={({ field, fieldState }) => (
                <FormItem>
                  <FormLabel>Valor general</FormLabel>
                  <FormControl>
                    <ParametroValueInput
                      id="param-valor-general"
                      valueType={parametro.valueType}
                      value={field.value}
                      onChange={field.onChange}
                      disabled={!canEdit || updateGeneral.isPending}
                      invalid={Boolean(fieldState.error)}
                    />
                  </FormControl>
                  <FormMessage />
                  <p className="text-xs text-txt-muted">
                    {parametro.allowsCenterOverride
                      ? "Aplica a todos los centros salvo los que tengan un valor propio."
                      : "Aplica igual en todos los centros: este parámetro no admite valor por centro."}
                  </p>
                </FormItem>
              )}
            />

            <Separator />

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Clave</Label>
                <Input value={parametro.key} disabled />
              </div>
              <div className="space-y-2">
                <Label>Tipo</Label>
                <Input value={TIPO_LABELS[parametro.valueType]} disabled />
              </div>
              {limits ? (
                <div className="space-y-2">
                  <Label>Límites</Label>
                  <Input value={limits} disabled />
                </div>
              ) : null}
              {parametro.legacySource ? (
                <div className="space-y-2">
                  <Label>Origen en el legado</Label>
                  <Input value={parametro.legacySource} disabled />
                </div>
              ) : null}
            </div>

            {!canEdit ? (
              <AdminReadOnlyNotice message="Solo lectura: no tienes permiso para modificar parámetros." />
            ) : null}
          </form>
        </Form>
      ),
    },
  ];

  if (parametro.allowsCenterOverride) {
    sections.push({
      id: "centros",
      label: `Por centro (${parametro.centerValues.length})`,
      content: <ParametroCentrosSection parametro={parametro} canEdit={canEdit} enabled={open} />,
    });
  }

  return (
    <AdminDetailsDialogShell
      open={open}
      onOpenChange={handleOpenChange}
      onRequestClose={closeDialog}
      titleSrOnly="Detalle de parámetro"
      descriptionSrOnly="Consulta y modifica el valor general y los valores por centro de este parámetro."
      header={
        <CatalogDialogHeader
          title={parametro.description}
          subtitle={moduleLabel(parametro.module)}
          status={
            <Badge variant="outline">
              {parametro.allowsCenterOverride ? "Admite valor por centro" : "General"}
            </Badge>
          }
          icon={<SlidersHorizontal className="size-7" />}
        />
      }
      topContent={<Separator />}
      isDirty={isDirty}
      sections={sections}
      defaultSectionId="general"
      dialogContentClassName="h-auto max-h-[90vh] w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215 xl:w-235"
      footer={({ onCancel }) => (
        <CatalogDetailsFooter
          isDirty={isDirty}
          isSaving={updateGeneral.isPending}
          formId={FORM_ID}
          onCancel={onCancel}
          disableSave={!canEdit || !form.formState.isValid}
        />
      )}
    />
  );
}
