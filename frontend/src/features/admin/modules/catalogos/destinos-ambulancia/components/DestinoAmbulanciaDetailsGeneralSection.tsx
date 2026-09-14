import type { UseFormReturn } from "react-hook-form";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { Separator } from "@shared/ui/separator";
import type { DestinoAmbulanciaDetail } from "@api/types";
import { CATALOG_STATUS, type CatalogStatus } from "@features/admin/modules/catalogos/shared/domain/catalog-status";
import type { DestinoAmbulanciaDetailsFormValues } from "@features/admin/modules/catalogos/destinos-ambulancia/domain/destinos-ambulancia.schemas";

interface DestinoAmbulanciaDetailsGeneralSectionProps {
  form: UseFormReturn<DestinoAmbulanciaDetailsFormValues>;
  formId: string;
  destinoAmbulanciaDetail: DestinoAmbulanciaDetail;
  onSubmit: (values: DestinoAmbulanciaDetailsFormValues) => void;
  onStatusChange?: (nextActive: boolean) => void;
  isStatusPending?: boolean;
  isEditable?: boolean;
}

export function DestinoAmbulanciaDetailsGeneralSection({
  form, formId, destinoAmbulanciaDetail, onSubmit, onStatusChange, isStatusPending = false, isEditable = true,
}: DestinoAmbulanciaDetailsGeneralSectionProps) {
  const statusValue: CatalogStatus = destinoAmbulanciaDetail.isActive ? CATALOG_STATUS.ACTIVE : CATALOG_STATUS.INACTIVE;

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
          <FormField
            control={form.control}
            name="street"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Calle</FormLabel>
                <FormControl><Input {...field} disabled={!isEditable} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="zipCode"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Codigo Postal</FormLabel>
                <FormControl><Input {...field} disabled={!isEditable} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="neighborhood"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Colonia</FormLabel>
                <FormControl><Input {...field} disabled={!isEditable} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="borough"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Delegacion/Municipio</FormLabel>
                <FormControl><Input {...field} disabled={!isEditable} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="phone"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Telefono</FormLabel>
                <FormControl><Input {...field} disabled={!isEditable} /></FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div className="space-y-2">
            <Label>ID</Label>
            <Input value={destinoAmbulanciaDetail.id.toString()} disabled />
          </div>
        </div>

        <FormField
          control={form.control}
          name="reference"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Referencia</FormLabel>
              <FormControl><Input {...field} disabled={!isEditable} /></FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Separator />
      </form>
    </Form>
  );
}
