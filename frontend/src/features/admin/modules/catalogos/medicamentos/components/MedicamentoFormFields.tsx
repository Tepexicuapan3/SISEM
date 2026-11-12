import type { UseFormReturn } from "react-hook-form";
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import {
  CUADRO_BASICO_OPTIONS,
  type MedicamentoDetailsFormValues,
} from "@features/admin/modules/catalogos/medicamentos/domain/medicamentos.schemas";

interface MedicamentoFormFieldsProps {
  form: UseFormReturn<MedicamentoDetailsFormValues>;
  disabled?: boolean;
}

const CONTROLLED = { YES: "si", NO: "no" } as const;

/** Campos del medicamento, compartidos por el alta y el detalle. */
export function MedicamentoFormFields({ form, disabled = false }: MedicamentoFormFieldsProps) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Nombre del medicamento</FormLabel>
              <FormControl>
                <Input {...field} disabled={disabled} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="code"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Clave</FormLabel>
              <FormControl>
                <Input {...field} disabled={disabled} placeholder="Ej. 010.000.0104.00" />
              </FormControl>
              <FormDescription>Clave del Compendio Nacional de Insumos (opcional).</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="genericName"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Denominación genérica</FormLabel>
              <FormControl>
                <Input {...field} disabled={disabled} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="presentation"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Presentación</FormLabel>
              <FormControl>
                <Input {...field} disabled={disabled} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <FormField
          control={form.control}
          name="cuadroBasico"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Cuadro</FormLabel>
              <Select value={field.value} onValueChange={field.onChange} disabled={disabled}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {CUADRO_BASICO_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="isControlled"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Controlado</FormLabel>
              <Select
                value={field.value ? CONTROLLED.YES : CONTROLLED.NO}
                onValueChange={(value) => field.onChange(value === CONTROLLED.YES)}
                disabled={disabled}
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value={CONTROLLED.NO}>No</SelectItem>
                  <SelectItem value={CONTROLLED.YES}>Sí</SelectItem>
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="maxQuantity"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Máximo de cajas</FormLabel>
              <FormControl>
                <Input {...field} inputMode="numeric" disabled={disabled} placeholder="Sin tope" />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>
    </>
  );
}
