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
  FormMessage,
} from "@shared/ui/form";
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
import { useClinicalHistory, usePatientProfile } from "@features/expedientes/queries/useClinicalHistory";
import { useUpdatePatientProfile } from "@features/expedientes/mutations/useUpdatePatientProfile";
import { AllergyList } from "@features/expedientes/components/AllergyList";
import { PatientBackgroundSection } from "@features/expedientes/components/PatientBackgroundSection";
import { HistoricalNotesSection } from "@features/expedientes/components/HistoricalNotesSection";
import {
  PATIENT_SEX_LABELS,
  isValidCurp,
  normalizeCurp,
} from "@features/expedientes/domain/patient-identity";
import { ApiError } from "@api/utils/errors";
import type { PatientSex, UpdatePatientProfileRequest } from "@api/types";

interface ExpedienteGeneralesTabProps {
  noExp: string;
  pkNum?: number;
}

// Radix Select no admite un item con value="" -- este centinela representa
// "Sin especificar" y se traduce a null al guardar.
const SEX_NONE = "none";

interface FormValues {
  curp: string;
  sex: PatientSex | typeof SEX_NONE;
  occupationId: string;
  educationLevelId: string;
  maritalStatusId: string;
  religionId: string;
  residenceTypeId: string;
  phone: string;
}

const EMPTY_VALUES: FormValues = {
  curp: "",
  sex: SEX_NONE,
  occupationId: "",
  educationLevelId: "",
  maritalStatusId: "",
  religionId: "",
  residenceTypeId: "",
  phone: "",
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
] as const;

export function ExpedienteGeneralesTab({
  noExp,
  pkNum = 0,
}: ExpedienteGeneralesTabProps) {
  // PACIENTE (ficha editable) + HISTORIA_CLINICA (cabecera: apertura).
  const { data, isLoading, isError } = usePatientProfile(noExp, pkNum);
  const { data: history } = useClinicalHistory(noExp, pkNum);
  const updateClinicalHistory = useUpdatePatientProfile();

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
      curp: data.curp ?? "",
      sex: data.sex ?? SEX_NONE,
      occupationId: data.occupationId?.toString() ?? "",
      educationLevelId: data.educationLevelId?.toString() ?? "",
      maritalStatusId: data.maritalStatusId?.toString() ?? "",
      religionId: data.religionId?.toString() ?? "",
      residenceTypeId: data.residenceTypeId?.toString() ?? "",
      phone: data.phone ?? "",
    });
  }, [data, form]);

  const onSubmit = async (values: FormValues) => {
    const dirtyFields = form.formState.dirtyFields;
    const payload: UpdatePatientProfileRequest = {};

    if (dirtyFields.curp) {
      const curp = normalizeCurp(values.curp);
      if (curp && !isValidCurp(curp)) {
        form.setError("curp", { message: "CURP con formato inválido" });
        return;
      }
      payload.curp = curp || null;
    }
    if (dirtyFields.sex) {
      payload.sex = values.sex === SEX_NONE ? null : values.sex;
    }

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
      toast.success("Ficha del paciente actualizada");
      form.reset(values);
    } catch (error) {
      const details = error instanceof ApiError ? error.details : undefined;
      const curpError = details && typeof details === "object" && "curp" in details;
      if (curpError) {
        form.setError("curp", { message: "CURP con formato inválido" });
      }
      toast.error("No se pudo guardar la ficha del paciente", {
        description: curpError
          ? "Revisa el CURP capturado."
          : "Intenta nuevamente en unos segundos.",
      });
    }
  };

  if (isLoading) {
    return (
      <p className="text-txt-muted text-sm py-12 text-center">
        Cargando ficha del paciente...
      </p>
    );
  }

  if (isError) {
    return (
      <p className="text-status-critical text-sm py-12 text-center">
        No se pudo cargar la ficha de este paciente.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      {history?.openedOn ? (
        <p className="text-xs text-txt-muted">
          Historia clínica abierta el {history.openedOn}
          {history.openingClinicCode ? ` · clínica ${history.openingClinicCode}` : ""}
          {history.openingDoctorCode ? ` · médico ${history.openingDoctorCode}` : ""}
        </p>
      ) : null}
      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-txt-body">Alergias</h3>
        <AllergyList noExp={noExp} pkNum={pkNum} source="general" />
      </section>

      <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
        <section className="space-y-4">
          <h3 className="text-sm font-semibold text-txt-body">Identificación</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <FormField
              control={form.control}
              name="curp"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>CURP</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      maxLength={18}
                      className="font-mono uppercase"
                      onChange={(e) => field.onChange(e.target.value.toUpperCase())}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="sex"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Sexo</FormLabel>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value={SEX_NONE}>Sin especificar</SelectItem>
                      {Object.entries(PATIENT_SEX_LABELS).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormItem>
              )}
            />
          </div>
        </section>

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
                    <Input {...field} maxLength={50} />
                  </FormControl>
                </FormItem>
              )}
            />
          </div>
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

      <section className="space-y-4">
        <h3 className="text-sm font-semibold text-txt-body">Antecedentes</h3>
        <PatientBackgroundSection noExp={noExp} pkNum={pkNum} source="general" />
      </section>

      <HistoricalNotesSection noExp={noExp} pkNum={pkNum} />
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
