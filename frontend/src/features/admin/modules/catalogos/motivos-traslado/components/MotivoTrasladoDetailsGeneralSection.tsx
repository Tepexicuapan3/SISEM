import type { UseFormReturn } from "react-hook-form";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { Separator } from "@shared/ui/separator";
import { Switch } from "@shared/ui/switch";
import type { MotivoTrasladoDetail } from "@api/types";
import { CATALOG_STATUS, type CatalogStatus } from "@features/admin/modules/catalogos/shared/domain/catalog-status";
import type { MotivoTrasladoDetailsFormValues } from "@features/admin/modules/catalogos/motivos-traslado/domain/motivos-traslado.schemas";

interface MotivoTrasladoDetailsGeneralSectionProps {
  form: UseFormReturn<MotivoTrasladoDetailsFormValues>;
  formId: string;
  motivoTrasladoDetail: MotivoTrasladoDetail;
  onSubmit: (values: MotivoTrasladoDetailsFormValues) => void;
  onStatusChange?: (nextActive: boolean) => void;
  isStatusPending?: boolean;
  isEditable?: boolean;
}

export function MotivoTrasladoDetailsGeneralSection({
  form, formId, motivoTrasladoDetail, onSubmit, onStatusChange, isStatusPending = false, isEditable = true,
}: MotivoTrasladoDetailsGeneralSectionProps) {
  const statusValue: CatalogStatus = motivoTrasladoDetail.isActive ? CATALOG_STATUS.ACTIVE : CATALOG_STATUS.INACTIVE;

  return (
    <Form {...form}>
      <form id={formId} onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Nombre</FormLabel>
                <FormControl><Input {...field} disabled={!isEditable} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="space-y-2">
            <Label>Estado</Label>
            <Select
              value={statusValue}
              onValueChange={(value) => {
                if (!onStatusChange || !isEditable) return;
                if (value === statusValue) return;
                onStatusChange(value === CATALOG_STATUS.ACTIVE);
              }}
              disabled={!onStatusChange || isStatusPending || !isEditable}
            >
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={CATALOG_STATUS.ACTIVE}>Activo</SelectItem>
                <SelectItem value={CATALOG_STATUS.INACTIVE}>Inactivo</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <FormField
          control={form.control}
          name="requiresNotes"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center justify-between rounded-xl border border-line-struct p-3">
              <div>
                <FormLabel>Requiere notas adicionales</FormLabel>
                <p className="text-xs text-txt-muted">
                  Al usar este motivo, la solicitud exigira capturar texto libre (equivalente a "Otro").
                </p>
              </div>
              <FormControl>
                <Switch checked={field.value} onCheckedChange={field.onChange} disabled={!isEditable} />
              </FormControl>
            </FormItem>
          )}
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>ID</Label>
            <Input value={motivoTrasladoDetail.id.toString()} disabled />
          </div>
        </div>

        <Separator />
      </form>
    </Form>
  );
}
