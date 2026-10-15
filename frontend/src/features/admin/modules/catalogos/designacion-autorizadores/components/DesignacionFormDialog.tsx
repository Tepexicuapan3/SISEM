import { useEffect, useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui/dialog";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { ScrollArea } from "@shared/ui/ScrollArea";
import { CatalogFkCombobox } from "@shared/ui/catalog-fk-combobox";
import type { DesignacionItem } from "@api/types";
import { DesignacionAlcanceFields } from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionAlcanceFields";
import { DesignacionDialogHeader } from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionDialogHeader";
import { DesignacionUserSelect } from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionUserSelect";
import {
  buildDesignacionSchema,
  type DesignacionFormValues,
} from "@features/admin/modules/catalogos/designacion-autorizadores/domain/designacion.schemas";
import { useCreateDesignacion } from "@features/admin/modules/catalogos/designacion-autorizadores/mutations/useCreateDesignacion";
import { useUpdateDesignacion } from "@features/admin/modules/catalogos/designacion-autorizadores/mutations/useUpdateDesignacion";
import { getDesignacionErrorMessage } from "@features/admin/modules/catalogos/designacion-autorizadores/utils/designacion.feedback";
import {
  buildDesignacionPayload,
  buildEmptyDesignacionValues,
  mapDesignacionToFormValues,
} from "@features/admin/modules/catalogos/designacion-autorizadores/utils/designacion.transform";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { useTiposAutorizacionList } from "@features/admin/modules/catalogos/tipos-autorizacion/queries/useTiposAutorizacionList";

interface DesignacionFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** null = alta; con valor = edicion. */
  designation: DesignacionItem | null;
  /** `admin.catalogs.designacionAutorizadores.global` */
  canGrantGlobal: boolean;
}

const FORM_ID = "designacion-form";

export function DesignacionFormDialog({
  open,
  onOpenChange,
  designation,
  canGrantGlobal,
}: DesignacionFormDialogProps) {
  const isEdit = designation !== null;
  const [adscripcion, setAdscripcion] = useState<string | null>(null);
  const [userLabel, setUserLabel] = useState<string | null>(designation?.user.name ?? null);

  // Reinicia el estado local cada vez que el dialogo se abre (ajuste durante el render,
  // evita setState dentro de un efecto).
  const resetKey = open ? (designation?.id ?? "new") : null;
  const [prevResetKey, setPrevResetKey] = useState(resetKey);
  if (resetKey !== prevResetKey) {
    setPrevResetKey(resetKey);
    setAdscripcion(null);
    setUserLabel(designation?.user.name ?? null);
  }

  const createDesignacion = useCreateDesignacion();
  const updateDesignacion = useUpdateDesignacion();
  const isPending = createDesignacion.isPending || updateDesignacion.isPending;

  const { data: centrosData } = useCentrosAtencionList(
    { pageSize: 200, isActive: true },
    { enabled: open },
  );
  const centerOptions = useMemo(
    () => (centrosData?.items ?? []).map((c) => ({ id: c.id, name: c.name })),
    [centrosData],
  );

  const { data: tiposData } = useTiposAutorizacionList(
    { pageSize: 200, isActive: true },
    { enabled: open },
  );
  const tipoOptions = (tiposData?.items ?? []).map((t) => ({ id: t.id, name: t.name }));

  const schema = useMemo(() => buildDesignacionSchema({ canGrantGlobal }), [canGrantGlobal]);

  const form = useForm<DesignacionFormValues>({
    resolver: zodResolver(schema),
    defaultValues: buildEmptyDesignacionValues(),
  });

  // Editar una designacion que ya es global sin el permiso global: solo lectura
  // (el backend responde 403 GLOBAL_PERMISSION_REQUIRED).
  const readOnlyGlobal = isEdit && designation.alcance.global && !canGrantGlobal;

  useEffect(() => {
    if (!open) return;
    form.reset(designation ? mapDesignacionToFormValues(designation) : buildEmptyDesignacionValues());
  }, [open, designation, form]);

  const handleDialogOpenChange = (nextOpen: boolean) => {
    onOpenChange(nextOpen);
  };

  const onSubmit = async (values: DesignacionFormValues) => {
    const data = buildDesignacionPayload(values);
    try {
      if (isEdit) {
        await updateDesignacion.mutateAsync({ id: designation.id, data });
        toast.success("Designación actualizada");
      } else {
        await createDesignacion.mutateAsync({ data });
        toast.success("Designación creada");
      }
      onOpenChange(false);
    } catch (error) {
      toast.error(
        isEdit ? "No se pudo actualizar la designación" : "No se pudo crear la designación",
        { description: getDesignacionErrorMessage(error, "Error al guardar la designación") },
      );
    }
  };

  const title = isEdit ? "Editar designación" : "Nueva designación";
  const [centros, tiposCentro, global] = useWatch({
    control: form.control,
    name: ["centros", "tiposCentro", "global"],
  });
  const scopeValue = { centros, tiposCentro, global };
  const scopeError =
    form.formState.errors.centros?.message ?? form.formState.errors.global?.message;

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="w-[95vw] max-w-none rounded-3xl bg-paper p-0 sm:w-[92vw] lg:w-215 xl:w-235">
        <div className="flex max-h-[88vh] flex-col">
          <DialogHeader className="px-8 pt-8">
            <DialogTitle className="sr-only">{title}</DialogTitle>
            <DialogDescription className="sr-only">
              Designa a un usuario como autorizador de un tipo de autorización para un alcance de
              centros y una vigencia.
            </DialogDescription>
            <DesignacionDialogHeader
              title={title}
              subtitle="Define quién autoriza, para qué centros y por cuánto tiempo"
              status={<Badge variant="outline">{isEdit ? "Edición" : "Plantilla"}</Badge>}
            />
          </DialogHeader>

          <ScrollArea className="flex-1 px-8 pb-8">
            <div className="space-y-6 pt-4">
              <div className="rounded-2xl border border-line-struct bg-paper p-4">
                <Form {...form}>
                  <form
                    id={FORM_ID}
                    onSubmit={form.handleSubmit(onSubmit)}
                    className="space-y-6"
                  >
                    {readOnlyGlobal ? (
                      <p className="text-sm text-txt-muted">
                        Esta designación abarca todos los centros; solo quien tenga el permiso
                        correspondiente puede modificarla.
                      </p>
                    ) : null}

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
                                disabled={readOnlyGlobal}
                                onChange={(userId, label, clinicName) => {
                                  field.onChange(userId);
                                  setUserLabel(label);
                                  setAdscripcion(clinicName);
                                }}
                              />
                            </FormControl>
                            {adscripcion ? (
                              <p className="text-xs text-txt-muted" data-testid="adscripcion-info">
                                Adscripción del usuario: <strong>{adscripcion}</strong> (solo
                                informativa; no determina dónde puede autorizar).
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
                                disabled={readOnlyGlobal}
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
                              <Input {...field} disabled={readOnlyGlobal} />
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
                              <Input {...field} disabled={readOnlyGlobal} />
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
                              <Input type="date" {...field} disabled={readOnlyGlobal} />
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
                                disabled={readOnlyGlobal}
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
                      disabled={readOnlyGlobal}
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
              </div>
            </div>
          </ScrollArea>

          <DialogFooter className="flex flex-col gap-3 border-t border-line-struct px-8 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-txt-muted">Completa los campos requeridos.</div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button type="button" variant="outline" onClick={() => handleDialogOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" form={FORM_ID} disabled={isPending || readOnlyGlobal}>
                {isEdit ? "Guardar cambios" : "Crear designación"}
              </Button>
            </div>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
