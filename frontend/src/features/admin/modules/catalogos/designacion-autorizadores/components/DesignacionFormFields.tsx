import { useMemo, useState } from "react";
import { useWatch, type UseFormReturn } from "react-hook-form";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { CatalogFkCombobox } from "@shared/ui/catalog-fk-combobox";
import { DesignacionAlcanceFields } from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionAlcanceFields";
import { DesignacionUserSelect } from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionUserSelect";
import type { DesignacionFormValues } from "@features/admin/modules/catalogos/designacion-autorizadores/domain/designacion.schemas";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { useTiposAutorizacionList } from "@features/admin/modules/catalogos/tipos-autorizacion/queries/useTiposAutorizacionList";

interface DesignacionFormFieldsProps {
  form: UseFormReturn<DesignacionFormValues>;
  formId: string;
  onSubmit: (values: DesignacionFormValues) => void;
  /** `admin.catalogs.designacionAutorizadores.global` */
  canGrantGlobal: boolean;
  disabled?: boolean;
  /** Nombre del usuario ya asignado (edicion); el combobox no lo trae por si solo. */
  initialUserLabel?: string | null;
  /** Carga los catalogos de apoyo (centros, tipos) solo con el dialogo abierto. */
  enabled?: boolean;
}

/**
 * Campos compartidos por el alta (DesignacionFormDialog) y el detalle
 * (DesignacionDetailsDialog). El estado local (etiqueta del usuario,
 * adscripcion) se reinicia remontando con `key`.
 */
export function DesignacionFormFields({
  form,
  formId,
  onSubmit,
  canGrantGlobal,
  disabled = false,
  initialUserLabel = null,
  enabled = true,
}: DesignacionFormFieldsProps) {
  const [adscripcion, setAdscripcion] = useState<string | null>(null);
  const [userLabel, setUserLabel] = useState<string | null>(initialUserLabel);

  const { data: centrosData } = useCentrosAtencionList(
    { pageSize: 200, isActive: true },
    { enabled },
  );
  const centerOptions = useMemo(
    () => (centrosData?.items ?? []).map((c) => ({ id: c.id, name: c.name })),
    [centrosData],
  );

  const { data: tiposData } = useTiposAutorizacionList(
    { pageSize: 200, isActive: true },
    { enabled },
  );
  const tipoOptions = (tiposData?.items ?? []).map((t) => ({ id: t.id, name: t.name }));

  const [centros, tiposCentro, global] = useWatch({
    control: form.control,
    name: ["centros", "tiposCentro", "global"],
  });
  const scopeValue = { centros, tiposCentro, global };
  const scopeError =
    form.formState.errors.centros?.message ?? form.formState.errors.global?.message;

  return (
    <Form {...form}>
      <form id={formId} onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="userId"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Usuario</FormLabel>
                <FormControl>
                  <DesignacionUserSelect
                    value={field.value}
                    selectedLabel={userLabel}
                    disabled={disabled}
                    onChange={(userId, label, clinicName) => {
                      field.onChange(userId);
                      setUserLabel(label);
                      setAdscripcion(clinicName);
                    }}
                  />
                </FormControl>
                {adscripcion ? (
                  <p className="text-xs text-txt-muted" data-testid="adscripcion-info">
                    Adscripción del usuario: <strong>{adscripcion}</strong> (solo informativa; no
                    determina dónde puede autorizar).
                  </p>
                ) : null}
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="tipoAutorizacionId"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Tipo de autorización</FormLabel>
                <FormControl>
                  <CatalogFkCombobox
                    options={tipoOptions}
                    value={field.value}
                    onChange={field.onChange}
                    disabled={disabled}
                    placeholder="Selecciona un tipo"
                    searchPlaceholder="Buscar tipo..."
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="cargo"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Cargo</FormLabel>
                <FormControl>
                  <Input {...field} disabled={disabled} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="oficio"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Oficio (opcional)</FormLabel>
                <FormControl>
                  <Input {...field} disabled={disabled} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="fechaInicio"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Vigencia desde</FormLabel>
                <FormControl>
                  <Input type="date" {...field} disabled={disabled} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="fechaFin"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  Vigencia hasta{scopeValue.global ? " (obligatoria)" : " (opcional)"}
                </FormLabel>
                <FormControl>
                  <Input
                    type="date"
                    {...field}
                    aria-required={scopeValue.global}
                    disabled={disabled}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <DesignacionAlcanceFields
          value={scopeValue}
          centers={centerOptions}
          canGrantGlobal={canGrantGlobal || scopeValue.global}
          disabled={disabled}
          errorMessage={scopeError}
          onChange={(next) => {
            const options = { shouldDirty: true, shouldValidate: form.formState.isSubmitted };
            form.setValue("centros", next.centros, options);
            form.setValue("tiposCentro", next.tiposCentro, options);
            form.setValue("global", next.global, options);
          }}
        />
      </form>
    </Form>
  );
}
