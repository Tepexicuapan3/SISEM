import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, Save } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from "@shared/ui/form";
import { Textarea } from "@shared/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import { ocupacionesAPI } from "@api/resources/catalogos/ocupaciones.api";
import { escolaridadAPI } from "@api/resources/catalogos/escolaridad.api";
import { edoCivilAPI } from "@api/resources/catalogos/edoCivil.api";
import { religionesAPI } from "@api/resources/catalogos/religiones.api";
import { tiposResidenciaAPI } from "@api/resources/catalogos/tipos-residencia.api";
import { useClinicalHistory } from "@features/expedientes/queries/useClinicalHistory";
import { useUpdateClinicalHistory } from "@features/expedientes/mutations/useUpdateClinicalHistory";
import { AllergyList } from "@features/expedientes/components/AllergyList";
import type { UpdateClinicalHistoryRequest } from "@api/types";

interface ExpedienteGeneralesTabProps {
  noExp: string;
  pkNum?: number;
}

interface FormValues {
  occupationId: string;
  educationLevelId: string;
  maritalStatusId: string;
  religionId: string;
  residenceTypeId: string;
  phone: string;
  familyHistory: string;
  currentIllness: string;
  systemsReview: string;
  headExam: string;
  neckExam: string;
  chestExam: string;
  abdomenExam: string;
  genitalsExam: string;
  limbsExam: string;
  diagnosticManagement: string;
  therapeuticManagement: string;
}

const EMPTY_VALUES: FormValues = {
  occupationId: "",
  educationLevelId: "",
  maritalStatusId: "",
  religionId: "",
  residenceTypeId: "",
  phone: "",
  familyHistory: "",
  currentIllness: "",
  systemsReview: "",
  headExam: "",
  neckExam: "",
  chestExam: "",
  abdomenExam: "",
  genitalsExam: "",
  limbsExam: "",
  diagnosticManagement: "",
  therapeuticManagement: "",
};

const SELECT_FIELDS = [
  "occupationId",
  "educationLevelId",
  "maritalStatusId",
  "religionId",
  "residenceTypeId",
] as const;

const TEXT_FIELDS = [
  "phone",
  "familyHistory",
  "currentIllness",
  "systemsReview",
  "headExam",
  "neckExam",
  "chestExam",
  "abdomenExam",
  "genitalsExam",
  "limbsExam",
  "diagnosticManagement",
  "therapeuticManagement",
] as const;

export function ExpedienteGeneralesTab({
  noExp,
  pkNum = 0,
}: ExpedienteGeneralesTabProps) {
  const { data, isLoading, isError } = useClinicalHistory(noExp, pkNum);
  const updateClinicalHistory = useUpdateClinicalHistory();

  const { data: ocupaciones } = useQuery({
    queryKey: ["catalogos", "ocupaciones", "options"],
    queryFn: () => ocupacionesAPI.getAll({ pageSize: 200 }),
  });
  const { data: escolaridades } = useQuery({
    queryKey: ["catalogos", "escolaridad", "options"],
    queryFn: () => escolaridadAPI.getAll({ pageSize: 200 }),
  });
  const { data: estadosCiviles } = useQuery({
    queryKey: ["catalogos", "edo-civil", "options"],
    queryFn: () => edoCivilAPI.getAll({ pageSize: 200 }),
  });
  const { data: religiones } = useQuery({
    queryKey: ["catalogos", "religiones", "options"],
    queryFn: () => religionesAPI.getAll({ pageSize: 200 }),
  });
  const { data: tiposResidencia } = useQuery({
    queryKey: ["catalogos", "tipos-residencia", "options"],
    queryFn: () => tiposResidenciaAPI.getAll({ pageSize: 200 }),
  });

  const form = useForm<FormValues>({ defaultValues: EMPTY_VALUES });

  useEffect(() => {
    if (!data) return;
    form.reset({
      occupationId: data.occupationId?.toString() ?? "",
      educationLevelId: data.educationLevelId?.toString() ?? "",
      maritalStatusId: data.maritalStatusId?.toString() ?? "",
      religionId: data.religionId?.toString() ?? "",
      residenceTypeId: data.residenceTypeId?.toString() ?? "",
      phone: data.phone ?? "",
      familyHistory: data.familyHistory ?? "",
      currentIllness: data.currentIllness ?? "",
      systemsReview: data.systemsReview ?? "",
      headExam: data.headExam ?? "",
      neckExam: data.neckExam ?? "",
      chestExam: data.chestExam ?? "",
      abdomenExam: data.abdomenExam ?? "",
      genitalsExam: data.genitalsExam ?? "",
      limbsExam: data.limbsExam ?? "",
      diagnosticManagement: data.diagnosticManagement ?? "",
      therapeuticManagement: data.therapeuticManagement ?? "",
    });
  }, [data, form]);

  const onSubmit = async (values: FormValues) => {
    const dirtyFields = form.formState.dirtyFields;
    const payload: UpdateClinicalHistoryRequest = {};

    for (const field of SELECT_FIELDS) {
      if (dirtyFields[field]) {
        payload[field] = values[field] ? Number(values[field]) : null;
      }
    }

    for (const field of TEXT_FIELDS) {
      if (dirtyFields[field]) {
        payload[field] = values[field] || null;
      }
    }

    if (Object.keys(payload).length === 0) return;

    try {
      await updateClinicalHistory.mutateAsync({ noExp, pkNum, data: payload });
      toast.success("Historia clínica actualizada");
      form.reset(values);
    } catch {
      toast.error("No se pudo guardar la historia clínica", {
        description: "Intenta nuevamente en unos segundos.",
      });
    }
  };

  if (isLoading) {
    return (
      <p className="text-txt-muted text-sm py-12 text-center">
        Cargando historia clínica...
      </p>
    );
  }

  if (isError) {
    return (
      <p className="text-status-critical text-sm py-12 text-center">
        No se pudo cargar la historia clínica de este paciente.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-txt-body">Alergias</h3>
        <AllergyList noExp={noExp} pkNum={pkNum} source="general" />
      </section>

      <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-txt-body">
            Datos sociodemográficos
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <CatalogSelectField
              control={form.control}
              name="occupationId"
              label="Ocupación"
              options={ocupaciones?.items}
            />
            <CatalogSelectField
              control={form.control}
              name="educationLevelId"
              label="Escolaridad"
              options={escolaridades?.items}
            />
            <CatalogSelectField
              control={form.control}
              name="maritalStatusId"
              label="Estado Civil"
              options={estadosCiviles?.items}
            />
            <CatalogSelectField
              control={form.control}
              name="religionId"
              label="Religión"
              options={religiones?.items}
            />
            <CatalogSelectField
              control={form.control}
              name="residenceTypeId"
              label="Tipo de Residencia"
              options={tiposResidencia?.items}
            />
            <FormField
              control={form.control}
              name="phone"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Teléfono</FormLabel>
                  <FormControl>
                    <Input {...field} maxLength={15} />
                  </FormControl>
                </FormItem>
              )}
            />
          </div>
        </section>

        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-txt-body">
            Antecedentes y padecimiento
          </h3>
          <TextareaField
            control={form.control}
            name="familyHistory"
            label="Antecedentes"
          />
          <TextareaField
            control={form.control}
            name="currentIllness"
            label="Padecimiento Actual"
          />
          <TextareaField
            control={form.control}
            name="systemsReview"
            label="Órganos, Aparatos y Sistemas"
          />
        </section>

        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-txt-body">
            Exploración Física
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ShortTextField control={form.control} name="headExam" label="Cabeza" />
            <ShortTextField control={form.control} name="neckExam" label="Cuello" />
            <ShortTextField control={form.control} name="chestExam" label="Tórax" />
            <ShortTextField control={form.control} name="abdomenExam" label="Abdomen" />
            <ShortTextField control={form.control} name="genitalsExam" label="Genitales" />
            <ShortTextField control={form.control} name="limbsExam" label="Miembros" />
          </div>
        </section>

        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-txt-body">
            Manejo
          </h3>
          <TextareaField
            control={form.control}
            name="diagnosticManagement"
            label="Manejo Diagnóstico"
          />
          <TextareaField
            control={form.control}
            name="therapeuticManagement"
            label="Manejo Terapéutico"
          />
        </section>

        <div className="flex justify-end">
          <Button
            type="submit"
            disabled={updateClinicalHistory.isPending || !form.formState.isDirty}
          >
            {updateClinicalHistory.isPending ? (
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

interface CatalogOption {
  id: number;
  name: string;
}

function CatalogSelectField({
  control,
  name,
  label,
  options,
}: {
  control: ReturnType<typeof useForm<FormValues>>["control"];
  name: (typeof SELECT_FIELDS)[number];
  label: string;
  options: CatalogOption[] | undefined;
}) {
  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel>{label}</FormLabel>
          <Select value={field.value} onValueChange={field.onChange}>
            <FormControl>
              <SelectTrigger>
                <SelectValue placeholder="Sin especificar" />
              </SelectTrigger>
            </FormControl>
            <SelectContent>
              {(options ?? []).map((option) => (
                <SelectItem key={option.id} value={String(option.id)}>
                  {option.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
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
  control: ReturnType<typeof useForm<FormValues>>["control"];
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

function ShortTextField({
  control,
  name,
  label,
}: {
  control: ReturnType<typeof useForm<FormValues>>["control"];
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
