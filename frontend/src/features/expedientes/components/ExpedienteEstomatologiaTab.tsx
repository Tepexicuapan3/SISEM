import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { Loader2, Save } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Checkbox } from "@shared/ui/checkbox";
import { Textarea } from "@shared/ui/textarea";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from "@shared/ui/form";
import { useStomatologyHistory } from "@features/expedientes/queries/useStomatologyHistory";
import { useUpdateStomatologyHistory } from "@features/expedientes/mutations/useUpdateStomatologyHistory";
import { AllergyList } from "@features/expedientes/components/AllergyList";
import type { UpdateStomatologyHistoryRequest } from "@api/types";

interface ExpedienteEstomatologiaTabProps {
  noExp: string;
  pkNum?: number;
}

interface FormValues {
  familyDiabetes: boolean;
  familyCancer: boolean;
  familyHighBloodPressure: boolean;
  familyLowBloodPressure: boolean;
  causeOfDeath: string;
  personalDiabetes: boolean;
  personalAsthma: boolean;
  personalHighBloodPressure: boolean;
  personalLowBloodPressure: boolean;
  personalHepatitis: boolean;
  personalHiv: boolean;
  personalSmoking: boolean;
  personalAlcoholism: boolean;
  personalSubstanceAbuse: boolean;
  habits: string;
  diet: string;
  surgicalHistory: string;
  traumaticHistory: string;
  currentIllnessHistory: string;
}

const BOOLEAN_FIELDS = [
  "familyDiabetes",
  "familyCancer",
  "familyHighBloodPressure",
  "familyLowBloodPressure",
  "personalDiabetes",
  "personalAsthma",
  "personalHighBloodPressure",
  "personalLowBloodPressure",
  "personalHepatitis",
  "personalHiv",
  "personalSmoking",
  "personalAlcoholism",
  "personalSubstanceAbuse",
] as const;

const TEXT_FIELDS = [
  "causeOfDeath",
  "habits",
  "diet",
  "surgicalHistory",
  "traumaticHistory",
  "currentIllnessHistory",
] as const;

const EMPTY_VALUES: FormValues = {
  familyDiabetes: false,
  familyCancer: false,
  familyHighBloodPressure: false,
  familyLowBloodPressure: false,
  causeOfDeath: "",
  personalDiabetes: false,
  personalAsthma: false,
  personalHighBloodPressure: false,
  personalLowBloodPressure: false,
  personalHepatitis: false,
  personalHiv: false,
  personalSmoking: false,
  personalAlcoholism: false,
  personalSubstanceAbuse: false,
  habits: "",
  diet: "",
  surgicalHistory: "",
  traumaticHistory: "",
  currentIllnessHistory: "",
};

export function ExpedienteEstomatologiaTab({
  noExp,
  pkNum = 0,
}: ExpedienteEstomatologiaTabProps) {
  const { data, isLoading, isError } = useStomatologyHistory(noExp, pkNum);
  const updateHistory = useUpdateStomatologyHistory();

  const form = useForm<FormValues>({ defaultValues: EMPTY_VALUES });

  useEffect(() => {
    if (!data) return;
    form.reset({
      familyDiabetes: data.familyDiabetes,
      familyCancer: data.familyCancer,
      familyHighBloodPressure: data.familyHighBloodPressure,
      familyLowBloodPressure: data.familyLowBloodPressure,
      causeOfDeath: data.causeOfDeath ?? "",
      personalDiabetes: data.personalDiabetes,
      personalAsthma: data.personalAsthma,
      personalHighBloodPressure: data.personalHighBloodPressure,
      personalLowBloodPressure: data.personalLowBloodPressure,
      personalHepatitis: data.personalHepatitis,
      personalHiv: data.personalHiv,
      personalSmoking: data.personalSmoking,
      personalAlcoholism: data.personalAlcoholism,
      personalSubstanceAbuse: data.personalSubstanceAbuse,
      habits: data.habits ?? "",
      diet: data.diet ?? "",
      surgicalHistory: data.surgicalHistory ?? "",
      traumaticHistory: data.traumaticHistory ?? "",
      currentIllnessHistory: data.currentIllnessHistory ?? "",
    });
  }, [data, form]);

  const onSubmit = async (values: FormValues) => {
    const dirtyFields = form.formState.dirtyFields;
    const payload: UpdateStomatologyHistoryRequest = {};

    for (const field of BOOLEAN_FIELDS) {
      if (dirtyFields[field]) {
        payload[field] = values[field];
      }
    }
    for (const field of TEXT_FIELDS) {
      if (dirtyFields[field]) {
        payload[field] = values[field] || null;
      }
    }

    if (Object.keys(payload).length === 0) return;

    try {
      await updateHistory.mutateAsync({ noExp, pkNum, data: payload });
      toast.success("Historia clínica de estomatología actualizada");
      form.reset(values);
    } catch {
      toast.error("No se pudo guardar", {
        description: "Intenta nuevamente en unos segundos.",
      });
    }
  };

  if (isLoading) {
    return (
      <p className="text-txt-muted text-sm py-12 text-center">
        Cargando historia clínica de estomatología...
      </p>
    );
  }

  if (isError) {
    return (
      <p className="text-status-critical text-sm py-12 text-center">
        No se pudo cargar la historia clínica de estomatología.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h3 className="text-sm font-semibold text-txt-body">
          Antecedentes Alérgicos
        </h3>
        <AllergyList noExp={noExp} pkNum={pkNum} source="stomatology" />
      </section>

      <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-txt-body">
            Antecedentes Heredofamiliares
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <BooleanField control={form.control} name="familyDiabetes" label="Diabetes" />
            <BooleanField control={form.control} name="familyCancer" label="Cáncer" />
            <BooleanField control={form.control} name="familyHighBloodPressure" label="Presión Alta" />
            <BooleanField control={form.control} name="familyLowBloodPressure" label="Presión Baja" />
          </div>
          <TextField control={form.control} name="causeOfDeath" label="Causa de Muerte" />
        </section>

        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-txt-body">
            Antecedentes Personales Patológicos
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <BooleanField control={form.control} name="personalDiabetes" label="Diabetes" />
            <BooleanField control={form.control} name="personalAsthma" label="Asma" />
            <BooleanField control={form.control} name="personalHighBloodPressure" label="Presión Alta" />
            <BooleanField control={form.control} name="personalLowBloodPressure" label="Presión Baja" />
            <BooleanField control={form.control} name="personalHepatitis" label="Hepatitis" />
            <BooleanField control={form.control} name="personalHiv" label="VIH" />
            <BooleanField control={form.control} name="personalSmoking" label="Tabaquismo" />
            <BooleanField control={form.control} name="personalAlcoholism" label="Alcoholismo" />
            <BooleanField control={form.control} name="personalSubstanceAbuse" label="Toxicomanías" />
          </div>
        </section>

        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-txt-body">
            Antecedentes Personales No Patológicos
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <TextField control={form.control} name="habits" label="Hábitos" />
            <TextField control={form.control} name="diet" label="Alimentación" />
          </div>
        </section>

        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-txt-body">
            Antecedentes Quirúrgicos y Traumáticos
          </h3>
          <TextareaField control={form.control} name="surgicalHistory" label="Antecedentes Quirúrgicos" />
          <TextareaField control={form.control} name="traumaticHistory" label="Antecedentes Traumáticos" />
        </section>

        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-txt-body">
            Padecimiento Actual
          </h3>
          <TextareaField
            control={form.control}
            name="currentIllnessHistory"
            label="Cronología, Terapias y Resultados"
          />
        </section>

        <div className="flex justify-end">
          <Button
            type="submit"
            disabled={updateHistory.isPending || !form.formState.isDirty}
          >
            {updateHistory.isPending ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <Save className="mr-2 size-4" />
            )}
            Guardar
          </Button>
        </div>
      </form>
      </Form>
    </div>
  );
}

// ── Campos reutilizables ──────────────────────────────────────────

type FormControlType = ReturnType<typeof useForm<FormValues>>["control"];

function BooleanField({
  control,
  name,
  label,
}: {
  control: FormControlType;
  name: (typeof BOOLEAN_FIELDS)[number];
  label: string;
}) {
  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem className="flex items-center gap-2 space-y-0">
          <FormControl>
            <Checkbox checked={field.value} onCheckedChange={field.onChange} />
          </FormControl>
          <FormLabel className="font-normal">{label}</FormLabel>
        </FormItem>
      )}
    />
  );
}

function TextField({
  control,
  name,
  label,
}: {
  control: FormControlType;
  name: (typeof TEXT_FIELDS)[number];
  label: string;
}) {
  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Input {...field} />
          </FormControl>
        </FormItem>
      )}
    />
  );
}

function TextareaField({
  control,
  name,
  label,
}: {
  control: FormControlType;
  name: (typeof TEXT_FIELDS)[number];
  label: string;
}) {
  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <FormControl>
            <Textarea {...field} rows={3} />
          </FormControl>
        </FormItem>
      )}
    />
  );
}
