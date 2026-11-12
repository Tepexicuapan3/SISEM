import type { Control, UseFormReturn } from "react-hook-form";
import { Button } from "@shared/ui/button";
import {
  FormControl,
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
import { ADMINISTRATION_ROUTES } from "@features/consulta-medica/modules/atencion/domain/administration-routes";
import {
  DURATION_PRESETS,
  FREQUENCY_PRESETS,
} from "@features/consulta-medica/modules/atencion/domain/prescription-presets";
import type { PrescriptionItemFieldsValues } from "@features/consulta-medica/modules/atencion/domain/prescription-item-form";

interface PresetChipsProps {
  presets: readonly string[];
  onPick: (value: string) => void;
}

function PresetChips({ presets, onPick }: PresetChipsProps) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {presets.map((preset) => (
        <Button
          key={preset}
          type="button"
          variant="outline"
          size="sm"
          className="h-7 rounded-full px-2.5 text-xs"
          onClick={() => onPick(preset)}
        >
          {preset}
        </Button>
      ))}
    </div>
  );
}

interface PrescriptionItemFieldsProps<T extends PrescriptionItemFieldsValues> {
  form: UseFormReturn<T>;
  maxQuantity?: number | null;
}

/** Dosis, via, cantidad, frecuencia, duracion e indicaciones de un renglon. */
export function PrescriptionItemFields<T extends PrescriptionItemFieldsValues>({
  form,
  maxQuantity,
}: PrescriptionItemFieldsProps<T>) {
  // Los formularios de agregar y editar comparten estos campos; el de agregar
  // ademas lleva el medicamento.
  const fieldsForm = form as unknown as UseFormReturn<PrescriptionItemFieldsValues>;
  const control: Control<PrescriptionItemFieldsValues> = fieldsForm.control;
  const pickPreset = (field: "frequency" | "duration") => (value: string) =>
    fieldsForm.setValue(field, value, { shouldDirty: true, shouldValidate: true });

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-3">
        <FormField
          control={control}
          name="dose"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Dosis (opcional)</FormLabel>
              <FormControl>
                <Input {...field} placeholder="1 tableta" />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={control}
          name="route"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Vía de administración</FormLabel>
              <Select value={field.value} onValueChange={field.onChange}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Selecciona la vía" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {ADMINISTRATION_ROUTES.map((route) => (
                    <SelectItem key={route.value} value={route.value}>
                      {route.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={control}
          name="quantity"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Cantidad (cajas)</FormLabel>
              <FormControl>
                <Input
                  type="number"
                  min={1}
                  max={maxQuantity ?? undefined}
                  {...field}
                  onChange={(event) => field.onChange(event.target.valueAsNumber)}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <FormField
          control={control}
          name="frequency"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Frecuencia</FormLabel>
              <FormControl>
                <Input {...field} maxLength={60} placeholder="Cada 8 horas" />
              </FormControl>
              <PresetChips presets={FREQUENCY_PRESETS} onPick={pickPreset("frequency")} />
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={control}
          name="duration"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Duración</FormLabel>
              <FormControl>
                <Input {...field} maxLength={60} placeholder="5 días" />
              </FormControl>
              <PresetChips presets={DURATION_PRESETS} onPick={pickPreset("duration")} />
              <FormMessage />
            </FormItem>
          )}
        />
      </div>

      <FormField
        control={control}
        name="indications"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Indicaciones</FormLabel>
            <FormControl>
              <Input {...field} maxLength={140} placeholder="Después de comer" />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    </>
  );
}
