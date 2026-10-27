import { useState, type ReactNode } from "react";
import { useWatch, type UseFormReturn } from "react-hook-form";
import type {
  ClaveTipoAutorizacion,
  TipoAutorizacionCatalogo,
  UsuarioElegible,
} from "@api/types/autorizaciones/autorizadores.types";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@shared/ui/form";
import { Input } from "@shared/ui/input";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { AutorizadorTiposFields } from "@features/admin/modules/autorizadores/components/AutorizadorTiposFields";
import { AutorizadorUsuarioSelect } from "@features/admin/modules/autorizadores/components/AutorizadorUsuarioSelect";
import type { AutorizadorFormValues } from "@features/admin/modules/autorizadores/domain/autorizador.schemas";
import { formatFecha } from "@features/admin/modules/autorizadores/utils/autorizador.format";

interface AutorizadorFormFieldsProps {
  form: UseFormReturn<AutorizadorFormValues>;
  formId: string;
  onSubmit: (values: AutorizadorFormValues) => void;
  modo: "alta" | "edicion";
  tiposCatalogo: TipoAutorizacionCatalogo[];
  /** `admin:autorizadores:global` */
  canGrantGlobal: boolean;
  disabled?: boolean;
  /** Edicion: nombre del medico (el usuario no se cambia). */
  nombreUsuario?: string | null;
  /** Carga los centros solo con el dialogo abierto. */
  enabled?: boolean;
}

function Seccion({ titulo, descripcion, children }: { titulo: string; descripcion?: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-xs font-semibold uppercase tracking-wide text-txt-muted">{titulo}</h3>
        {descripcion ? <p className="mt-0.5 text-xs text-txt-muted">{descripcion}</p> : null}
      </div>
      {children}
    </section>
  );
}

/** Campos compartidos por el alta y el detalle del autorizador, agrupados por seccion. */
export function AutorizadorFormFields({
  form,
  formId,
  onSubmit,
  modo,
  tiposCatalogo,
  canGrantGlobal,
  disabled = false,
  nombreUsuario = null,
  enabled = true,
}: AutorizadorFormFieldsProps) {
  const [usuarioElegido, setUsuarioElegido] = useState<UsuarioElegible | null>(null);

  const { data: centrosData } = useCentrosAtencionList({ pageSize: 200, isActive: true }, { enabled });
  const centros = (centrosData?.items ?? []).map((centro) => ({ id: centro.id, name: centro.name }));

  const [tipos, inicio, fin] = useWatch({
    control: form.control,
    name: ["tipos", "fechaInicioVigencia", "fechaFinVigencia"],
  });

  const errores = form.formState.errors.tipos;
  const errorGeneral = errores?.message ?? errores?.root?.message;
  const erroresPorClave: Partial<Record<ClaveTipoAutorizacion, string>> = {};
  tipos.forEach((tipo, indice) => {
    const mensaje = errores?.[indice]?.alcance?.message;
    if (mensaje) erroresPorClave[tipo.clave] = mensaje;
  });

  const exigeCedula = tipos.some(
    (tipo) => tipo.seleccionado && tiposCatalogo.find((t) => t.clave === tipo.clave)?.requiereCedula,
  );

  return (
    <Form {...form}>
      {/* @container: las columnas responden al ancho del formulario (el dialogo), no al de la ventana. */}
      <form id={formId} onSubmit={form.handleSubmit(onSubmit)} className="@container min-w-0 space-y-6">
        <Seccion
          titulo="Médico y designación"
          descripcion="Usuario existente de SIRES. La cédula se toma de Usuarios."
        >
          {/* Usuario a todo el ancho: los nombres completos son largos y no deben cortarse. */}
          <div className="grid gap-4 @xl:grid-cols-2">
            {modo === "alta" ? (
              <FormField
                control={form.control}
                name="usuarioId"
                render={({ field }) => (
                  <FormItem className="@xl:col-span-2">
                    <FormLabel>Usuario</FormLabel>
                    <FormControl>
                      <AutorizadorUsuarioSelect
                        value={field.value}
                        disabled={disabled}
                        onChange={(usuario) => {
                          field.onChange(usuario.id);
                          setUsuarioElegido(usuario);
                        }}
                      />
                    </FormControl>
                    {usuarioElegido && !usuarioElegido.tieneCedula && exigeCedula ? (
                      <p className="text-xs text-status-alert" data-testid="aviso-cedula">
                        Este usuario no tiene cédula profesional. Captúrala en Usuarios antes de
                        guardar: los tipos elegidos la exigen.
                      </p>
                    ) : null}
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : (
              <div className="space-y-2 @xl:col-span-2">
                <FormLabel>Usuario</FormLabel>
                <Input value={nombreUsuario ?? ""} title={nombreUsuario ?? undefined} disabled />
              </div>
            )}
            <FormField
              control={form.control}
              name="cargo"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Cargo (opcional)</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="Ej. Jefe de servicio" disabled={disabled} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="numeroOficio"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Número de oficio (opcional)</FormLabel>
                  <FormControl>
                    <Input {...field} placeholder="Ej. OF-2026-001" disabled={disabled} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        </Seccion>

        <Seccion
          titulo="Vigencia"
          descripcion={
            modo === "alta"
              ? "Fuera de este periodo no podrá autorizar."
              : "Para ampliarla usa “Renovar vigencia”; el periodo anterior queda en el historial."
          }
        >
          {modo === "alta" ? (
            <div className="grid gap-4 @md:grid-cols-2">
              <FormField
                control={form.control}
                name="fechaInicioVigencia"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Desde</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} disabled={disabled} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="fechaFinVigencia"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Hasta</FormLabel>
                    <FormControl>
                      <Input type="date" min={inicio || undefined} {...field} disabled={disabled} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          ) : (
            <p className="text-sm text-txt-body tabular-nums">
              {formatFecha(inicio)} – {formatFecha(fin)}
            </p>
          )}
        </Seccion>

        <Seccion titulo="Tipos de autorización y centros">
          <AutorizadorTiposFields
            value={tipos}
            tiposCatalogo={tiposCatalogo}
            centers={centros}
            canGrantGlobal={canGrantGlobal}
            disabled={disabled}
            errorMessage={errorGeneral}
            erroresPorClave={erroresPorClave}
            onChange={(siguiente) =>
              form.setValue("tipos", siguiente, {
                shouldDirty: true,
                shouldValidate: form.formState.isSubmitted,
              })
            }
          />
        </Seccion>
      </form>
    </Form>
  );
}
