import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { Loader2, Save } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Textarea } from "@shared/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@shared/ui/select";
import { Form, FormControl, FormField, FormItem, FormLabel } from "@shared/ui/form";
import { useStomatologyHistory } from "@features/expedientes/queries/useStomatologyHistory";
import { useUpdateStomatologyHistory } from "@features/expedientes/mutations/useUpdateStomatologyHistory";
import { useClinicalCatalogs, usePatientRecords } from "@features/expedientes/queries/useUnifiedHistory";
import { usePatientRecordMutations } from "@features/expedientes/mutations/usePatientRecordMutations";
import { AllergyList } from "@features/expedientes/components/AllergyList";
import { PatientBackgroundSection } from "@features/expedientes/components/PatientBackgroundSection";
import { HistoricalNotesSection } from "@features/expedientes/components/HistoricalNotesSection";
import { NONE, RecordListCard } from "@features/expedientes/components/RecordListCard";
import type { DentalTreatmentItem, OralHygiene, UpdateStomatologyHistoryRequest } from "@api/types";

interface ExpedienteEstomatologiaTabProps {
  noExp: string;
  pkNum?: number;
}

const ORAL_HYGIENE_LABEL: Record<OralHygiene, string> = {
  good: "Buena",
  regular: "Regular",
  poor: "Mala",
};

const FLOSS_OPTIONS = { yes: "Sí", no: "No" } as const;

interface FormValues {
  oralHygiene: OralHygiene | typeof NONE;
  brushingsPerDay: string;
  usesFloss: keyof typeof FLOSS_OPTIONS | typeof NONE;
  softTissues: string;
  tmj: string;
}

const EMPTY_VALUES: FormValues = {
  oralHygiene: NONE,
  brushingsPerDay: "",
  usesFloss: NONE,
  softTissues: "",
  tmj: "",
};

function DentalTreatmentsSection({ noExp, pkNum }: { noExp: string; pkNum: number }) {
  const { data: catalogs } = useClinicalCatalogs();
  const query = usePatientRecords<DentalTreatmentItem>("dental-treatments", noExp, pkNum);
  const { create, update, deactivate } = usePatientRecordMutations({ resource: "dental-treatments", noExp, pkNum });

  return (
    <RecordListCard<DentalTreatmentItem>
      title="Tratamientos dentales"
      emptyText="Sin tratamientos registrados."
      addLabel="Agregar tratamiento"
      items={query.data?.items ?? []}
      isLoading={query.isLoading}
      isError={query.isError}
      fields={[
        {
          name: "toothFdi", label: "Pieza (FDI)", kind: "select",
          options: [
            { value: NONE, label: "Sin pieza específica" },
            ...(catalogs?.teeth ?? []).map((tooth) => ({ value: tooth.fdi, label: `${tooth.fdi} · ${tooth.name}` })),
          ],
        },
        {
          name: "status", label: "Estado", kind: "select",
          options: [{ value: "planned", label: "Planeado" }, { value: "done", label: "Realizado" }],
        },
        { name: "procedure", label: "Procedimiento", kind: "text", wide: true, maxLength: 500 },
      ]}
      emptyValues={{ toothFdi: NONE, status: "planned", procedure: "" }}
      toFormValues={(item) => ({ toothFdi: item.toothFdi ?? NONE, status: item.status, procedure: item.procedure })}
      toPayload={(values) => {
        const procedure = typeof values.procedure === "string" ? values.procedure.trim() : "";
        if (!procedure) return "Indica el procedimiento.";
        return {
          procedure,
          status: values.status,
          toothFdi: values.toothFdi === NONE ? null : values.toothFdi,
          source: "stomatology",
        };
      }}
      renderItem={(item) => (
        <div className="flex flex-wrap items-center gap-2">
          {item.toothFdi ? <Badge variant="outline">Pieza {item.toothFdi}</Badge> : null}
          <span className="text-sm font-semibold text-txt-body">{item.procedure}</span>
          <Badge variant={item.status === "done" ? "stable" : "alert"}>
            {item.status === "done" ? "Realizado" : "Planeado"}
          </Badge>
          {item.performedAt ? (
            <span className="text-xs text-txt-muted">{new Date(item.performedAt).toLocaleDateString("es-MX")}</span>
          ) : null}
        </div>
      )}
      onCreate={(payload) => create.mutateAsync(payload)}
      onUpdate={(recordId, payload) => update.mutateAsync({ recordId, data: payload })}
      onDeactivate={(recordId, reason) => deactivate.mutateAsync({ recordId, reason })}
      isSaving={create.isPending || update.isPending}
      isDeactivating={deactivate.isPending}
    />
  );
}

export function ExpedienteEstomatologiaTab({ noExp, pkNum = 0 }: ExpedienteEstomatologiaTabProps) {
  const { data, isLoading, isError } = useStomatologyHistory(noExp, pkNum);
  const updateHistory = useUpdateStomatologyHistory();
  const form = useForm<FormValues>({ defaultValues: EMPTY_VALUES });

  useEffect(() => {
    if (!data) return;
    form.reset({
      oralHygiene: data.oralHygiene ?? NONE,
      brushingsPerDay: data.brushingsPerDay?.toString() ?? "",
      usesFloss: data.usesFloss === null ? NONE : data.usesFloss ? "yes" : "no",
      softTissues: data.softTissues ?? "",
      tmj: data.tmj ?? "",
    });
  }, [data, form]);

  const onSubmit = async (values: FormValues) => {
    const dirty = form.formState.dirtyFields;
    const payload: UpdateStomatologyHistoryRequest = {};
    if (dirty.oralHygiene) payload.oralHygiene = values.oralHygiene === NONE ? null : values.oralHygiene;
    if (dirty.brushingsPerDay) {
      const brushings = values.brushingsPerDay.trim();
      if (brushings && !/^\d{1,2}$/.test(brushings)) {
        toast.error("Cepillados por día debe ser un número entre 0 y 20.");
        return;
      }
      payload.brushingsPerDay = brushings ? Number(brushings) : null;
    }
    if (dirty.usesFloss) payload.usesFloss = values.usesFloss === NONE ? null : values.usesFloss === "yes";
    if (dirty.softTissues) payload.softTissues = values.softTissues.trim() || null;
    if (dirty.tmj) payload.tmj = values.tmj.trim() || null;
    if (Object.keys(payload).length === 0) return;

    try {
      await updateHistory.mutateAsync({ noExp, pkNum, data: payload });
      toast.success("Historia de estomatología actualizada");
      form.reset(values);
    } catch {
      toast.error("No se pudo guardar la historia de estomatología", {
        description: "Intenta nuevamente en unos segundos.",
      });
    }
  };

  if (isLoading) {
    return <p className="text-txt-muted text-sm py-12 text-center">Cargando historia de estomatología...</p>;
  }
  if (isError) {
    return (
      <p className="text-status-critical text-sm py-12 text-center">
        No se pudo cargar la historia de estomatología de este paciente.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-txt-body">Alergias</h3>
        <AllergyList noExp={noExp} pkNum={pkNum} source="stomatology" />
      </section>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <h3 className="text-sm font-semibold text-txt-body">Exploración bucal</h3>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField control={form.control} name="oralHygiene" render={({ field }) => (
              <FormItem>
                <FormLabel>Higiene oral</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                  <SelectContent>
                    <SelectItem value={NONE}>Sin especificar</SelectItem>
                    {Object.entries(ORAL_HYGIENE_LABEL).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormItem>
            )} />
            <FormField control={form.control} name="brushingsPerDay" render={({ field }) => (
              <FormItem>
                <FormLabel>Cepillados por día</FormLabel>
                <FormControl><Input {...field} inputMode="numeric" maxLength={2} /></FormControl>
              </FormItem>
            )} />
            <FormField control={form.control} name="usesFloss" render={({ field }) => (
              <FormItem>
                <FormLabel>Usa hilo dental</FormLabel>
                <Select value={field.value} onValueChange={field.onChange}>
                  <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
                  <SelectContent>
                    <SelectItem value={NONE}>Sin especificar</SelectItem>
                    {Object.entries(FLOSS_OPTIONS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormItem>
            )} />
          </div>
          <FormField control={form.control} name="softTissues" render={({ field }) => (
            <FormItem>
              <FormLabel>Tejidos blandos (mucosa, lengua, paladar)</FormLabel>
              <FormControl><Textarea {...field} rows={2} /></FormControl>
            </FormItem>
          )} />
          <FormField control={form.control} name="tmj" render={({ field }) => (
            <FormItem>
              <FormLabel>Articulación temporomandibular (ATM)</FormLabel>
              <FormControl><Textarea {...field} rows={2} /></FormControl>
            </FormItem>
          )} />
          <div className="flex justify-end">
            <Button type="submit" disabled={updateHistory.isPending || !form.formState.isDirty}>
              {updateHistory.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Save className="mr-2 size-4" />}
              Guardar
            </Button>
          </div>
        </form>
      </Form>

      <DentalTreatmentsSection noExp={noExp} pkNum={pkNum} />

      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-txt-body">Antecedentes (compartidos con Medicina General)</h3>
        <PatientBackgroundSection noExp={noExp} pkNum={pkNum} source="stomatology" />
      </section>

      <HistoricalNotesSection noExp={noExp} pkNum={pkNum} specialty="stomatology" />
    </div>
  );
}
