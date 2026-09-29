import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { CheckCircle2, Loader2, Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Textarea } from "@shared/ui/textarea";
import { Badge } from "@shared/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import { Form, FormControl, FormField, FormItem, FormLabel } from "@shared/ui/form";
import { useAllergies } from "@features/expedientes/queries/useAllergies";
import { useCreateAllergy } from "@features/expedientes/mutations/useCreateAllergy";
import { useUpdateAllergy } from "@features/expedientes/mutations/useUpdateAllergy";
import { useChangeAllergyStatus } from "@features/expedientes/mutations/useChangeAllergyStatus";
import { ReasonDialog } from "@features/expedientes/components/ReasonDialog";
import { useClinicalCatalogs } from "@features/expedientes/queries/useUnifiedHistory";
import type { Allergy, AllergySeverity, AllergySource, AllergyStatus } from "@api/types";

// Lista de alergias estructuradas de un paciente (change `alergias-unificadas`):
// reemplaza el texto libre duplicado de ClinicalHistory.allergies y los 6
// campos StomatologyHistory.allergy_* -- una sola fuente, visible tanto en
// la pestana General como en Estomatologia para el mismo paciente.

// Documento: L leve, M moderada, G grave. Los tipos (CAT_TIPO_ALERGIA:
// 1 medicamento, 2 anestesia, 3 material dental, 4 ambiental, 5 alimento,
// 9 otro) vienen del catalogo via /clinical-catalogs.
const SEVERITY_LABEL: Record<AllergySeverity, string> = {
  L: "Leve",
  M: "Moderada",
  G: "Grave",
};

const SEVERITY_BADGE_VARIANT: Record<AllergySeverity, "alert" | "critical"> = {
  L: "alert",
  M: "alert",
  G: "critical",
};

const SOURCE_LABEL: Record<AllergySource, string> = {
  general: "Medicina General",
  stomatology: "Estomatología",
};

interface FormValues {
  allergyTypeId: string;
  substance: string;
  severity: AllergySeverity | "";
  reaction: string;
}

const EMPTY_VALUES: FormValues = {
  allergyTypeId: "",
  substance: "",
  severity: "",
  reaction: "",
};

interface AllergyListProps {
  noExp: string;
  pkNum?: number;
  /** Especialidad desde la que se captura una alergia NUEVA -- solo
   * trazabilidad (`Allergy.source`), la lista completa siempre es visible
   * para ambas especialidades. */
  source: AllergySource;
}

export function AllergyList({ noExp, pkNum = 0, source }: AllergyListProps) {
  const { data, isLoading, isError } = useAllergies(noExp, pkNum);
  const { data: catalogs } = useClinicalCatalogs();
  const createAllergy = useCreateAllergy();
  const updateAllergy = useUpdateAllergy();
  const changeStatus = useChangeAllergyStatus();
  const [statusTarget, setStatusTarget] = useState<{ allergy: Allergy; status: AllergyStatus } | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  const form = useForm<FormValues>({ defaultValues: EMPTY_VALUES });

  const startCreate = () => {
    setEditingId(null);
    form.reset(EMPTY_VALUES);
    setShowForm(true);
  };

  const startEdit = (allergy: Allergy) => {
    setEditingId(allergy.id);
    form.reset({
      allergyTypeId: String(allergy.allergyTypeId),
      substance: allergy.substance,
      severity: allergy.severity,
      reaction: allergy.reaction ?? "",
    });
    setShowForm(true);
  };

  const cancelForm = () => {
    setShowForm(false);
    setEditingId(null);
    form.reset(EMPTY_VALUES);
  };

  const onSubmit = async (values: FormValues) => {
    if (!values.allergyTypeId || !values.substance.trim() || !values.severity) {
      toast.error("Completa tipo, sustancia y severidad.");
      return;
    }

    try {
      if (editingId !== null) {
        await updateAllergy.mutateAsync({
          noExp,
          pkNum,
          allergyId: editingId,
          data: {
            allergyTypeId: Number(values.allergyTypeId),
            substance: values.substance.trim(),
            severity: values.severity,
            reaction: values.reaction.trim() || null,
          },
        });
        toast.success("Alergia actualizada");
      } else {
        await createAllergy.mutateAsync({
          noExp,
          pkNum,
          data: {
            allergyTypeId: Number(values.allergyTypeId),
            substance: values.substance.trim(),
            severity: values.severity,
            reaction: values.reaction.trim() || undefined,
            source,
          },
        });
        toast.success("Alergia agregada");
      }
      cancelForm();
    } catch {
      toast.error("No se pudo guardar la alergia", {
        description: "Intenta nuevamente en unos segundos.",
      });
    }
  };

  const STATUS_COPY: Record<AllergyStatus, { title: string; description: string; confirm: string; done: string }> = {
    R: {
      title: "Marcar alergia como resuelta",
      description: "Seguirá visible en la historia, pero ya no alertará al recetar.",
      confirm: "Marcar resuelta",
      done: "Alergia marcada como resuelta",
    },
    E: {
      title: "Alergia capturada por error",
      description: "Se retira de la historia activa. No se borra: queda registrada con el motivo.",
      confirm: "Retirar alergia",
      done: "Alergia retirada",
    },
    A: {
      title: "Reactivar alergia",
      description: "Vuelve a estar activa y a alertar al recetar.",
      confirm: "Reactivar",
      done: "Alergia reactivada",
    },
  };

  const confirmStatusChange = async (reason: string) => {
    if (!statusTarget) return;
    try {
      await changeStatus.mutateAsync({
        noExp,
        pkNum,
        allergyId: statusTarget.allergy.id,
        data: { status: statusTarget.status, reason },
      });
      toast.success(STATUS_COPY[statusTarget.status].done);
      setStatusTarget(null);
    } catch {
      toast.error("No se pudo actualizar la alergia");
    }
  };

  const allergies = data?.items ?? [];
  const isSaving = createAllergy.isPending || updateAllergy.isPending;

  if (isLoading) {
    return <p className="text-txt-muted text-sm py-4">Cargando alergias...</p>;
  }

  if (isError) {
    return (
      <p className="text-status-critical text-sm py-4">
        No se pudieron cargar las alergias de este paciente.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {allergies.length === 0 ? (
        <p className="text-sm text-txt-muted">Sin alergias registradas.</p>
      ) : (
        <ul className="space-y-2">
          {allergies.map((allergy) => (
            <li
              key={allergy.id}
              className="flex items-start justify-between gap-3 rounded-lg border border-line-struct p-3"
            >
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-txt-body">
                    {allergy.substance}
                  </span>
                  <Badge variant={SEVERITY_BADGE_VARIANT[allergy.severity]}>
                    {SEVERITY_LABEL[allergy.severity]}
                  </Badge>
                  <Badge variant="outline">{allergy.allergyTypeName}</Badge>
                  <Badge variant="secondary">{SOURCE_LABEL[allergy.source]}</Badge>
                  {allergy.status === "R" ? <Badge variant="outline">Resuelta</Badge> : null}
                </div>
                {allergy.reaction ? (
                  <p className="text-xs text-txt-muted">{allergy.reaction}</p>
                ) : null}
                {allergy.status === "R" && allergy.statusReason ? (
                  <p className="text-xs text-txt-muted">Motivo: {allergy.statusReason}</p>
                ) : null}
              </div>
              <div className="flex shrink-0 gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => startEdit(allergy)}
                  aria-label="Editar alergia"
                >
                  <Pencil className="size-4" />
                </Button>
                {allergy.status === "A" ? (
                  <Button
                    type="button" variant="ghost" size="icon" aria-label="Marcar resuelta"
                    title="Marcar resuelta"
                    onClick={() => setStatusTarget({ allergy, status: "R" })}
                  >
                    <CheckCircle2 className="size-4" />
                  </Button>
                ) : (
                  <Button
                    type="button" variant="ghost" size="icon" aria-label="Reactivar"
                    title="Reactivar"
                    onClick={() => setStatusTarget({ allergy, status: "A" })}
                  >
                    <RotateCcw className="size-4" />
                  </Button>
                )}
                <Button
                  type="button" variant="ghost" size="icon" aria-label="Capturada por error"
                  title="Capturada por error"
                  onClick={() => setStatusTarget({ allergy, status: "E" })}
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {showForm ? (
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="space-y-3 rounded-lg border border-line-struct p-3"
          >
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <FormField
                control={form.control}
                name="allergyTypeId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Tipo de alergia</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Selecciona un tipo" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {(catalogs?.allergyTypes ?? []).map((type) => (
                          <SelectItem key={type.id} value={String(type.id)}>
                            {type.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="severity"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Severidad</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Selecciona la severidad" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {(Object.keys(SEVERITY_LABEL) as AllergySeverity[]).map((value) => (
                          <SelectItem key={value} value={value}>
                            {SEVERITY_LABEL[value]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FormItem>
                )}
              />
            </div>
            <FormField
              control={form.control}
              name="substance"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Sustancia</FormLabel>
                  <FormControl>
                    <Input {...field} maxLength={255} placeholder="Ej. Penicilina" />
                  </FormControl>
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="reaction"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reacción (opcional)</FormLabel>
                  <FormControl>
                    <Textarea
                      {...field}
                      rows={2}
                      placeholder="Ej. Urticaria, dificultad para respirar"
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={cancelForm}>
                Cancelar
              </Button>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                {editingId !== null ? "Guardar cambios" : "Agregar alergia"}
              </Button>
            </div>
          </form>
        </Form>
      ) : (
        <Button type="button" variant="outline" onClick={startCreate}>
          <Plus className="mr-2 size-4" />
          Agregar alergia
        </Button>
      )}

      <ReasonDialog
        open={statusTarget !== null}
        title={statusTarget ? STATUS_COPY[statusTarget.status].title : ""}
        description={statusTarget ? STATUS_COPY[statusTarget.status].description : ""}
        confirmLabel={statusTarget ? STATUS_COPY[statusTarget.status].confirm : ""}
        destructive={statusTarget?.status === "E"}
        isPending={changeStatus.isPending}
        onOpenChange={(open) => { if (!open) setStatusTarget(null); }}
        onConfirm={confirmStatusChange}
      />
    </div>
  );
}
