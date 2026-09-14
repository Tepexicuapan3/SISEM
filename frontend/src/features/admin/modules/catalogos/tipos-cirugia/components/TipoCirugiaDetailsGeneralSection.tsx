import type { UseFormReturn } from "react-hook-form";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { Separator } from "@shared/ui/separator";
import type { TipoCirugiaDetail } from "@api/types";
import { CATALOG_STATUS, type CatalogStatus } from "@features/admin/modules/catalogos/shared/domain/catalog-status";
import type { TipoCirugiaDetailsFormValues } from "@features/admin/modules/catalogos/tipos-cirugia/domain/tipos-cirugia.schemas";

interface TipoCirugiaDetailsGeneralSectionProps {
  form: UseFormReturn<TipoCirugiaDetailsFormValues>;
  formId: string;
  tipoCirugiaDetail: TipoCirugiaDetail;
  onSubmit: (values: TipoCirugiaDetailsFormValues) => void;
  onStatusChange?: (nextActive: boolean) => void;
  isStatusPending?: boolean;
  isEditable?: boolean;
}

export function TipoCirugiaDetailsGeneralSection({
  form, formId, tipoCirugiaDetail, onSubmit, onStatusChange, isStatusPending = false, isEditable = true,
}: TipoCirugiaDetailsGeneralSectionProps) {
  const statusValue: CatalogStatus = tipoCirugiaDetail.isActive ? CATALOG_STATUS.ACTIVE : CATALOG_STATUS.INACTIVE;

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

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>ID</Label>
            <Input value={tipoCirugiaDetail.id.toString()} disabled />
          </div>
        </div>

        <Separator />
      </form>
    </Form>
  );
}
