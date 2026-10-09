import { useState } from "react";
import { toast } from "sonner";
import { Droplet, Loader2, Save } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Label } from "@shared/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import { ApiError } from "@api/utils/errors";
import type { BloodTypeSource } from "@api/types";
import { useClinicalCatalogs, usePatientBloodType } from "@features/expedientes/queries/useUnifiedHistory";
import { useSaveBloodType } from "@features/expedientes/mutations/useSaveBloodType";
import { ReasonDialog } from "@features/expedientes/components/ReasonDialog";
import {
  BLOOD_TYPE_SOURCE_LABELS,
  classifyBloodTypeChange,
} from "@features/expedientes/domain/blood-type";

interface BloodTypeSectionProps {
  noExp: string;
  pkNum: number;
}

interface Draft {
  bloodTypeId: string;
  source: BloodTypeSource;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("es-MX", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/**
 * GRUPO_SANGUINEO (5.2): tipo de sangre vigente con su fuente. Cambiar uno
 * vigente pide motivo: la anterior queda como "corregida" y el porque en la
 * bitacora (nada se pisa sin rastro).
 */
export function BloodTypeSection({ noExp, pkNum }: BloodTypeSectionProps) {
  const { data, isLoading, isError } = usePatientBloodType(noExp, pkNum);
  const { data: catalogs } = useClinicalCatalogs();
  const saveBloodType = useSaveBloodType();
  const [reasonOpen, setReasonOpen] = useState(false);

  // null = sin editar: se muestra lo vigente (sin copiar el servidor a estado).
  const [draft, setDraft] = useState<Draft | null>(null);
  const current = data?.current ?? null;
  const values: Draft = draft ?? {
    bloodTypeId: current ? String(current.bloodTypeId) : "",
    source: current?.source ?? "D",
  };
  const change = classifyBloodTypeChange(current, {
    bloodTypeId: values.bloodTypeId ? Number(values.bloodTypeId) : null,
    source: values.source,
  });

  const save = async (reason?: string) => {
    try {
      await saveBloodType.mutateAsync({
        noExp,
        pkNum,
        data: { bloodTypeId: Number(values.bloodTypeId), source: values.source, reason: reason ?? null },
      });
      setDraft(null);
      setReasonOpen(false);
      toast.success(change === "correction" ? "Tipo de sangre corregido" : "Tipo de sangre registrado");
    } catch (error) {
      toast.error("No se pudo guardar el tipo de sangre", {
        description: error instanceof ApiError ? error.message : undefined,
      });
    }
  };

  if (isLoading) {
    return <p className="text-txt-muted text-sm">Cargando tipo de sangre...</p>;
  }
  if (isError) {
    return <p className="text-status-critical text-sm">No se pudo cargar el tipo de sangre.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Droplet className="size-5 text-status-critical" aria-hidden />
        {current ? (
          <>
            <span className="text-2xl font-semibold text-txt-body">{current.bloodTypeName}</span>
            <Badge variant={current.source === "L" ? "info" : "alert"}>
              {BLOOD_TYPE_SOURCE_LABELS[current.source]}
            </Badge>
            <span className="text-xs text-txt-muted">desde el {formatDate(current.createdAt)}</span>
          </>
        ) : (
          <span className="text-sm text-txt-muted">Sin registrar</span>
        )}
      </div>
      {current?.source === "D" ? (
        <p className="text-xs text-txt-muted">
          Lo dijo el paciente; nadie lo ha confirmado con laboratorio.
        </p>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
        <div className="space-y-2">
          <Label htmlFor="blood-type-select">Tipo de sangre</Label>
          <Select
            value={values.bloodTypeId}
            onValueChange={(bloodTypeId) => setDraft({ ...values, bloodTypeId })}
          >
            <SelectTrigger id="blood-type-select">
              <SelectValue placeholder="Selecciona" />
            </SelectTrigger>
            <SelectContent>
              {(catalogs?.bloodTypes ?? []).map((option) => (
                <SelectItem key={option.id} value={String(option.id)}>
                  {option.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="blood-type-source">Fuente</Label>
          <Select
            value={values.source}
            onValueChange={(source) => setDraft({ ...values, source: source as BloodTypeSource })}
          >
            <SelectTrigger id="blood-type-source">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(BLOOD_TYPE_SOURCE_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex justify-end md:justify-start">
          <Button
            type="button"
            disabled={change === "none" || saveBloodType.isPending}
            onClick={() => (change === "correction" ? setReasonOpen(true) : save())}
          >
            {saveBloodType.isPending ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <Save className="mr-2 size-4" />
            )}
            {change === "correction" ? "Corregir" : "Guardar"}
          </Button>
        </div>
      </div>

      {data?.history.length ? (
        <div className="space-y-1">
          <p className="text-xs font-medium text-txt-muted">Valores anteriores</p>
          <ul className="space-y-1">
            {data.history.map((record) => (
              <li key={record.id} className="text-xs text-txt-muted">
                <span className="line-through">{record.bloodTypeName}</span>
                {" · "}
                {BLOOD_TYPE_SOURCE_LABELS[record.source]}
                {" · registrado el "}
                {formatDate(record.createdAt)}, corregido el {formatDate(record.updatedAt)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <ReasonDialog
        open={reasonOpen}
        title="Corregir tipo de sangre"
        description="El valor anterior no se borra: queda como corregido. Escribe por qué cambia; queda en la bitácora."
        confirmLabel="Corregir"
        isPending={saveBloodType.isPending}
        onOpenChange={setReasonOpen}
        onConfirm={(reason) => save(reason)}
      />
    </div>
  );
}
