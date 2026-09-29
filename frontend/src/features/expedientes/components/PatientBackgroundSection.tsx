import { Badge } from "@shared/ui/badge";
import { usePatientRecords, useClinicalCatalogs } from "@features/expedientes/queries/useUnifiedHistory";
import { usePatientRecordMutations } from "@features/expedientes/mutations/usePatientRecordMutations";
import {
  NONE,
  RecordListCard,
  type RecordFieldDef,
} from "@features/expedientes/components/RecordListCard";
import type {
  FamilyHistoryItem,
  HabitItem,
  PatientRecordResource,
  PersonalHistoryItem,
  SurgicalHistoryItem,
} from "@api/types";

type Specialty = "general" | "stomatology";

interface Props {
  noExp: string;
  pkNum: number;
  /** Especialidad que captura un registro NUEVO (solo trazabilidad). */
  source: Specialty;
}

const SOURCE_LABEL: Record<string, string> = {
  general: "Medicina General",
  stomatology: "Estomatología",
  legacy: "Sistema anterior",
};

const text = (value: string | boolean) => (typeof value === "string" ? value.trim() : "");
const nullable = (value: string | boolean) => {
  const trimmed = text(value);
  return trimmed && trimmed !== NONE ? trimmed : null;
};

function SourceBadge({ source }: { source: string }) {
  return <Badge variant="secondary">{SOURCE_LABEL[source] ?? source}</Badge>;
}

function RestrictedLabel() {
  return <span className="text-sm font-semibold text-txt-muted">Antecedente restringido</span>;
}

function useResource<T extends { id: number }>(resource: PatientRecordResource, noExp: string, pkNum: number) {
  const query = usePatientRecords<T>(resource, noExp, pkNum);
  const { create, update, deactivate } = usePatientRecordMutations({ resource, noExp, pkNum });
  return {
    items: query.data?.items ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    onCreate: (payload: object) => create.mutateAsync(payload),
    onUpdate: (recordId: number, payload: object) => update.mutateAsync({ recordId, data: payload }),
    onDeactivate: (recordId: number, reason: string) => deactivate.mutateAsync({ recordId, reason }),
    isSaving: create.isPending || update.isPending,
    isDeactivating: deactivate.isPending,
  };
}

export function PatientBackgroundSection({ noExp, pkNum, source }: Props) {
  const { data: catalogs } = useClinicalCatalogs();
  const personal = useResource<PersonalHistoryItem>("personal-history", noExp, pkNum);
  const family = useResource<FamilyHistoryItem>("family-history", noExp, pkNum);
  const surgical = useResource<SurgicalHistoryItem>("surgical-history", noExp, pkNum);
  const habits = useResource<HabitItem>("habits", noExp, pkNum);

  const personalFields: RecordFieldDef[] = [
    { name: "cieCode", label: "CIE-10 (opcional)", kind: "text", maxLength: 8, placeholder: "Ej. E11" },
    {
      name: "status", label: "Estado", kind: "select",
      options: [{ value: "A", label: "Activo" }, { value: "R", label: "Resuelto" }],
    },
    { name: "description", label: "Descripción", kind: "text", wide: true, maxLength: 500 },
    { name: "diagnosisDate", label: "Fecha aproximada de diagnóstico", kind: "date" },
  ];

  const familyFields: RecordFieldDef[] = [
    {
      name: "relationshipId", label: "Parentesco", kind: "select",
      options: [
        { value: NONE, label: "No especificado" },
        ...(catalogs?.relationships ?? []).map((item) => ({ value: item.id, label: item.name })),
      ],
    },
    { name: "cieCode", label: "CIE-10 (opcional)", kind: "text", maxLength: 8 },
    { name: "description", label: "Padecimiento", kind: "text", wide: true, maxLength: 500 },
    { name: "isDeceased", label: "Finado", kind: "checkbox" },
    { name: "causeOfDeath", label: "Causa de muerte", kind: "text", maxLength: 255 },
  ];

  const surgicalFields: RecordFieldDef[] = [
    { name: "procedure", label: "Procedimiento", kind: "text", wide: true, maxLength: 500 },
    { name: "approximateDate", label: "Fecha aproximada", kind: "date" },
    { name: "place", label: "Lugar", kind: "text", maxLength: 255 },
  ];

  const habitFields: RecordFieldDef[] = [
    {
      name: "habitId", label: "Hábito", kind: "select", placeholder: "Selecciona un hábito",
      options: (catalogs?.habits ?? []).map((item) => ({ value: String(item.id), label: item.name })),
    },
    {
      name: "status", label: "Estado", kind: "select",
      options: [{ value: "A", label: "Actual" }, { value: "E", label: "Ex (ya no lo practica)" }],
    },
    { name: "frequency", label: "Frecuencia", kind: "text", maxLength: 100 },
    { name: "quantity", label: "Cantidad", kind: "text", maxLength: 100 },
    { name: "since", label: "Desde", kind: "date" },
    { name: "notes", label: "Notas", kind: "textarea" },
  ];

  return (
    <div className="space-y-6">
      <RecordListCard<PersonalHistoryItem>
        title="Antecedentes personales patológicos"
        emptyText="Sin antecedentes personales registrados."
        addLabel="Agregar antecedente"
        {...personal}
        fields={personalFields}
        emptyValues={{ cieCode: "", status: "A", description: "", diagnosisDate: "" }}
        canEdit={(item) => !item.isRestricted}
        toFormValues={(item) => ({
          cieCode: item.cieCode ?? "",
          status: item.status,
          description: item.description ?? "",
          diagnosisDate: item.diagnosisDate ?? "",
        })}
        toPayload={(values) => {
          const payload = {
            cieCode: nullable(values.cieCode),
            description: nullable(values.description),
            diagnosisDate: nullable(values.diagnosisDate),
            status: text(values.status) || "A",
            source,
          };
          return payload.cieCode || payload.description ? payload : "Indica un CIE-10 o una descripción.";
        }}
        renderItem={(item) =>
          item.isRestricted ? <RestrictedLabel /> : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-txt-body">
                  {item.cieDescription ?? item.description}
                </span>
                {item.cieCode ? <Badge variant="outline">{item.cieCode}</Badge> : null}
                <Badge variant={item.status === "A" ? "alert" : "secondary"}>
                  {item.status === "A" ? "Activo" : "Resuelto"}
                </Badge>
                <SourceBadge source={item.source} />
              </div>
              {item.cieDescription && item.description ? (
                <p className="text-xs text-txt-muted">{item.description}</p>
              ) : null}
            </>
          )
        }
      />

      <RecordListCard<FamilyHistoryItem>
        title="Antecedentes heredofamiliares"
        emptyText="Sin antecedentes familiares registrados."
        addLabel="Agregar antecedente familiar"
        {...family}
        fields={familyFields}
        emptyValues={{ relationshipId: NONE, cieCode: "", description: "", isDeceased: false, causeOfDeath: "" }}
        canEdit={(item) => !item.isRestricted}
        toFormValues={(item) => ({
          relationshipId: item.relationshipId ?? NONE,
          cieCode: item.cieCode ?? "",
          description: item.description ?? "",
          isDeceased: item.isDeceased,
          causeOfDeath: item.causeOfDeath ?? "",
        })}
        toPayload={(values) => {
          const payload = {
            relationshipId: nullable(values.relationshipId),
            cieCode: nullable(values.cieCode),
            description: nullable(values.description),
            isDeceased: values.isDeceased === true,
            causeOfDeath: nullable(values.causeOfDeath),
            source,
          };
          return payload.cieCode || payload.description || payload.causeOfDeath
            ? payload
            : "Indica un CIE-10, un padecimiento o la causa de muerte.";
        }}
        renderItem={(item) =>
          item.isRestricted ? <RestrictedLabel /> : (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-txt-body">
                {item.cieDescription ?? item.description ?? "Familiar"}
              </span>
              <Badge variant="outline">{item.relationshipName ?? "Parentesco no especificado"}</Badge>
              {item.isDeceased ? (
                <Badge variant="secondary">Finado{item.causeOfDeath ? `: ${item.causeOfDeath}` : ""}</Badge>
              ) : null}
              <SourceBadge source={item.source} />
            </div>
          )
        }
      />

      <RecordListCard<SurgicalHistoryItem>
        title="Antecedentes quirúrgicos"
        emptyText="Sin antecedentes quirúrgicos registrados."
        addLabel="Agregar cirugía"
        {...surgical}
        fields={surgicalFields}
        emptyValues={{ procedure: "", approximateDate: "", place: "" }}
        toFormValues={(item) => ({
          procedure: item.procedure,
          approximateDate: item.approximateDate ?? "",
          place: item.place ?? "",
        })}
        toPayload={(values) => {
          const procedure = text(values.procedure);
          if (!procedure) return "Indica el procedimiento.";
          return {
            procedure,
            approximateDate: nullable(values.approximateDate),
            place: nullable(values.place),
            source,
          };
        }}
        renderItem={(item) => (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-txt-body">{item.procedure}</span>
            {item.approximateDate ? <Badge variant="outline">{item.approximateDate}</Badge> : null}
            {item.place ? <span className="text-xs text-txt-muted">{item.place}</span> : null}
            <SourceBadge source={item.source} />
          </div>
        )}
      />

      <RecordListCard<HabitItem>
        title="Hábitos"
        emptyText="Sin hábitos registrados."
        addLabel="Agregar hábito"
        {...habits}
        fields={habitFields}
        emptyValues={{ habitId: "", status: "A", frequency: "", quantity: "", since: "", notes: "" }}
        toFormValues={(item) => ({
          habitId: String(item.habitId),
          status: item.status,
          frequency: item.frequency ?? "",
          quantity: item.quantity ?? "",
          since: item.since ?? "",
          notes: item.notes ?? "",
        })}
        toPayload={(values) => {
          const habitId = Number(text(values.habitId));
          if (!habitId) return "Selecciona el hábito.";
          return {
            habitId,
            status: text(values.status) || "A",
            frequency: nullable(values.frequency),
            quantity: nullable(values.quantity),
            since: nullable(values.since),
            notes: nullable(values.notes),
            source,
          };
        }}
        renderItem={(item) => (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-txt-body">{item.habitName}</span>
              <Badge variant={item.status === "A" ? "alert" : "secondary"}>
                {item.status === "A" ? "Actual" : "Ex"}
              </Badge>
              {[item.quantity, item.frequency].filter(Boolean).length ? (
                <span className="text-xs text-txt-muted">
                  {[item.quantity, item.frequency].filter(Boolean).join(" · ")}
                </span>
              ) : null}
              <SourceBadge source={item.source} />
            </div>
            {item.notes ? <p className="text-xs text-txt-muted">{item.notes}</p> : null}
          </>
        )}
      />
    </div>
  );
}
