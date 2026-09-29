import { useState, type ReactNode } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Checkbox } from "@shared/ui/checkbox";
import { Input } from "@shared/ui/input";
import { Textarea } from "@shared/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { Form, FormControl, FormField, FormItem, FormLabel } from "@shared/ui/form";
import { ApiError } from "@api/utils/errors";
import { ReasonDialog } from "@features/expedientes/components/ReasonDialog";

/** Radix Select no admite value="": centinela para "sin seleccion". */
export const NONE = "__none";

export type RecordFormValues = Record<string, string | boolean>;

export interface RecordFieldDef {
  name: string;
  label: string;
  kind: "text" | "textarea" | "date" | "select" | "checkbox";
  options?: { value: string; label: string }[];
  placeholder?: string;
  maxLength?: number;
  wide?: boolean;
}

interface RecordListCardProps<T extends { id: number }> {
  title: string;
  emptyText: string;
  addLabel: string;
  items: T[];
  isLoading: boolean;
  isError: boolean;
  fields: RecordFieldDef[];
  emptyValues: RecordFormValues;
  renderItem: (item: T) => ReactNode;
  toFormValues: (item: T) => RecordFormValues;
  /** Devuelve el payload o un mensaje de error de validacion. */
  toPayload: (values: RecordFormValues) => object | string;
  onCreate: (payload: object) => Promise<unknown>;
  onUpdate: (recordId: number, payload: object) => Promise<unknown>;
  onDeactivate: (recordId: number, reason: string) => Promise<unknown>;
  isSaving: boolean;
  isDeactivating: boolean;
  canEdit?: (item: T) => boolean;
}

function describeError(error: unknown) {
  if (error instanceof ApiError && error.details && typeof error.details === "object") {
    const messages = Object.values(error.details as Record<string, unknown>).flat();
    if (messages.length) return messages.join(" ");
  }
  return "Intenta nuevamente en unos segundos.";
}

/**
 * Lista + formulario en linea de un registro permanente del paciente
 * (antecedentes, habitos, tratamientos). La baja pide motivo obligatorio.
 */
export function RecordListCard<T extends { id: number }>({
  title, emptyText, addLabel, items, isLoading, isError, fields, emptyValues, renderItem,
  toFormValues, toPayload, onCreate, onUpdate, onDeactivate, isSaving, isDeactivating,
  canEdit = () => true,
}: RecordListCardProps<T>) {
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [removingId, setRemovingId] = useState<number | null>(null);
  const form = useForm<RecordFormValues>({ defaultValues: emptyValues });

  const closeForm = () => {
    setShowForm(false);
    setEditingId(null);
    form.reset(emptyValues);
  };

  const onSubmit = async (values: RecordFormValues) => {
    const payload = toPayload(values);
    if (typeof payload === "string") {
      toast.error(payload);
      return;
    }
    try {
      if (editingId !== null) {
        await onUpdate(editingId, payload);
        toast.success("Registro actualizado");
      } else {
        await onCreate(payload);
        toast.success("Registro agregado");
      }
      closeForm();
    } catch (error) {
      toast.error("No se pudo guardar", { description: describeError(error) });
    }
  };

  return (
    <section className="space-y-3">
      <h4 className="text-sm font-semibold text-txt-body">{title}</h4>

      {isLoading ? <p className="text-sm text-txt-muted">Cargando...</p> : null}
      {isError ? <p className="text-sm text-status-critical">No se pudo cargar esta sección.</p> : null}
      {!isLoading && !isError && items.length === 0 ? (
        <p className="text-sm text-txt-muted">{emptyText}</p>
      ) : null}

      {items.length > 0 ? (
        <ul className="space-y-2">
          {items.map((item) => (
            <li
              key={item.id}
              className="flex items-start justify-between gap-3 rounded-lg border border-line-struct p-3"
            >
              <div className="min-w-0 flex-1 space-y-1">{renderItem(item)}</div>
              {canEdit(item) ? (
                <div className="flex shrink-0 gap-1">
                  <Button
                    type="button" variant="ghost" size="icon" aria-label="Editar"
                    onClick={() => {
                      setEditingId(item.id);
                      form.reset(toFormValues(item));
                      setShowForm(true);
                    }}
                  >
                    <Pencil className="size-4" />
                  </Button>
                  <Button
                    type="button" variant="ghost" size="icon" aria-label="Dar de baja"
                    onClick={() => setRemovingId(item.id)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {showForm ? (
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="space-y-3 rounded-lg border border-line-struct p-3"
          >
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {fields.map((def) => (
                <FormField
                  key={def.name}
                  control={form.control}
                  name={def.name}
                  render={({ field }) => (
                    <FormItem className={def.wide || def.kind === "textarea" ? "md:col-span-2" : undefined}>
                      {def.kind === "checkbox" ? (
                        <div className="flex items-center gap-2 pt-6">
                          <FormControl>
                            <Checkbox
                              checked={Boolean(field.value)}
                              onCheckedChange={(checked) => field.onChange(checked === true)}
                            />
                          </FormControl>
                          <FormLabel className="!mt-0">{def.label}</FormLabel>
                        </div>
                      ) : (
                        <>
                          <FormLabel>{def.label}</FormLabel>
                          {def.kind === "select" ? (
                            <Select value={String(field.value)} onValueChange={field.onChange}>
                              <FormControl>
                                <SelectTrigger><SelectValue placeholder={def.placeholder} /></SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                {(def.options ?? []).map((option) => (
                                  <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          ) : (
                            <FormControl>
                              {def.kind === "textarea" ? (
                                <Textarea {...field} value={String(field.value)} rows={2} placeholder={def.placeholder} />
                              ) : (
                                <Input
                                  {...field}
                                  value={String(field.value)}
                                  type={def.kind === "date" ? "date" : "text"}
                                  maxLength={def.maxLength}
                                  placeholder={def.placeholder}
                                />
                              )}
                            </FormControl>
                          )}
                        </>
                      )}
                    </FormItem>
                  )}
                />
              ))}
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={closeForm}>Cancelar</Button>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                {editingId !== null ? "Guardar cambios" : addLabel}
              </Button>
            </div>
          </form>
        </Form>
      ) : (
        <Button
          type="button" variant="outline"
          onClick={() => {
            setEditingId(null);
            form.reset(emptyValues);
            setShowForm(true);
          }}
        >
          <Plus className="mr-2 size-4" />
          {addLabel}
        </Button>
      )}

      <ReasonDialog
        open={removingId !== null}
        title="Dar de baja el registro"
        description="El registro no se borra: queda fuera de la historia activa con el motivo que indiques."
        confirmLabel="Dar de baja"
        destructive
        isPending={isDeactivating}
        onOpenChange={(open) => { if (!open) setRemovingId(null); }}
        onConfirm={async (reason) => {
          if (removingId === null) return;
          try {
            await onDeactivate(removingId, reason);
            toast.success("Registro dado de baja");
            setRemovingId(null);
          } catch (error) {
            toast.error("No se pudo dar de baja", { description: describeError(error) });
          }
        }}
      />
    </section>
  );
}
