import { useMemo, useState } from "react";
import { Plus, Save, Undo2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Label } from "@shared/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import { useCentrosAtencionList } from "@features/admin/modules/catalogos/centros-atencion/queries/useCentrosAtencionList";
import { ParametroValueInput } from "@features/admin/modules/catalogos/parametros/components/ParametroValueInput";
import {
  formatParametroValue,
  validateParametroValue,
} from "@features/admin/modules/catalogos/parametros/domain/parametro.value";
import {
  useDeleteParametroCentro,
  useSetParametroCentro,
} from "@features/admin/modules/catalogos/parametros/queries/useParametros";
import { getParametroErrorMessage } from "@features/admin/modules/catalogos/parametros/utils/parametro.feedback";
import type { Parametro, ParametroCentroValor } from "@api/types/catalogos/parameters.types";

interface ParametroCentrosSectionProps {
  parametro: Parametro;
  canEdit: boolean;
  enabled: boolean;
}

function CentroRow({
  parametro,
  item,
  canEdit,
}: {
  parametro: Parametro;
  item: ParametroCentroValor;
  canEdit: boolean;
}) {
  const [draft, setDraft] = useState(item.value);
  const setValue = useSetParametroCentro();
  const removeValue = useDeleteParametroCentro();
  const error = validateParametroValue(parametro, draft);
  const isDirty = draft !== item.value;
  const busy = setValue.isPending || removeValue.isPending;

  const handleSave = async () => {
    try {
      await setValue.mutateAsync({ key: parametro.key, centerId: item.centerId, value: draft });
      toast.success("Valor del centro actualizado", { description: item.centerName });
    } catch (mutationError) {
      toast.error("No se pudo guardar", {
        description: getParametroErrorMessage(mutationError, "Error al guardar el valor del centro"),
      });
    }
  };

  const handleRemove = async () => {
    try {
      await removeValue.mutateAsync({ key: parametro.key, centerId: item.centerId });
      toast.success("El centro vuelve al valor general", { description: item.centerName });
    } catch (mutationError) {
      toast.error("No se pudo quitar", {
        description: getParametroErrorMessage(mutationError, "Error al quitar el valor del centro"),
      });
    }
  };

  return (
    <li className="grid gap-2 rounded-xl border border-line-hairline p-3 sm:grid-cols-[1fr_1.4fr_auto] sm:items-start">
      <span className="pt-2 text-sm font-medium text-txt-body">{item.centerName}</span>
      <div className="space-y-1">
        {canEdit ? (
          <ParametroValueInput
            id={`param-centro-${item.centerId}`}
            valueType={parametro.valueType}
            value={draft}
            onChange={setDraft}
            disabled={busy}
            invalid={Boolean(error)}
            ariaLabel={`Valor para ${item.centerName}`}
          />
        ) : (
          <p className="pt-2 text-sm text-txt-body">
            {formatParametroValue(parametro.valueType, item.value)}
          </p>
        )}
        {canEdit && error ? <p className="text-xs text-status-critical">{error}</p> : null}
      </div>
      {canEdit ? (
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!isDirty || Boolean(error) || busy}
            onClick={() => void handleSave()}
          >
            <Save className="size-4" />
            Guardar
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => void handleRemove()}
          >
            <Undo2 className="size-4" />
            Usar general
          </Button>
        </div>
      ) : null}
    </li>
  );
}

export function ParametroCentrosSection({ parametro, canEdit, enabled }: ParametroCentrosSectionProps) {
  const [centerId, setCenterId] = useState<string>("");
  const [value, setValue] = useState(parametro.generalValue);
  const addValue = useSetParametroCentro();

  const { data: centrosData } = useCentrosAtencionList(
    { pageSize: 200, isActive: true },
    { enabled: enabled && canEdit },
  );
  const usedIds = useMemo(
    () => new Set(parametro.centerValues.map((cv) => cv.centerId)),
    [parametro.centerValues],
  );
  const availableCenters = (centrosData?.items ?? []).filter((c) => !usedIds.has(c.id));
  const error = validateParametroValue(parametro, value);

  const handleAdd = async () => {
    if (!centerId) return;
    try {
      await addValue.mutateAsync({ key: parametro.key, centerId: Number(centerId), value });
      toast.success("Valor del centro agregado");
      setCenterId("");
      setValue(parametro.generalValue);
    } catch (mutationError) {
      toast.error("No se pudo agregar", {
        description: getParametroErrorMessage(mutationError, "Error al agregar el valor del centro"),
      });
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-txt-muted">
        Los centros que no aparecen aquí usan el valor general (
        <strong>{formatParametroValue(parametro.valueType, parametro.generalValue)}</strong>).
      </p>

      {parametro.centerValues.length > 0 ? (
        <ul className="space-y-2">
          {parametro.centerValues.map((item) => (
            <CentroRow
              key={`${item.centerId}-${item.value}`}
              parametro={parametro}
              item={item}
              canEdit={canEdit}
            />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-txt-muted">Ningún centro tiene un valor propio.</p>
      )}

      {canEdit ? (
        <div className="grid gap-3 rounded-xl border border-dashed border-line-struct p-3 sm:grid-cols-[1fr_1.4fr_auto] sm:items-end">
          <div className="space-y-2">
            <Label htmlFor="param-nuevo-centro">Centro</Label>
            <Select value={centerId} onValueChange={setCenterId}>
              <SelectTrigger id="param-nuevo-centro">
                <SelectValue placeholder="Elegí un centro" />
              </SelectTrigger>
              <SelectContent>
                {availableCenters.map((c) => (
                  <SelectItem key={c.id} value={c.id.toString()}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="param-nuevo-valor">Valor</Label>
            <ParametroValueInput
              id="param-nuevo-valor"
              valueType={parametro.valueType}
              value={value}
              onChange={setValue}
              disabled={addValue.isPending}
              invalid={Boolean(error)}
            />
            {error ? <p className="text-xs text-status-critical">{error}</p> : null}
          </div>
          <Button
            type="button"
            size="sm"
            disabled={!centerId || Boolean(error) || addValue.isPending}
            onClick={() => void handleAdd()}
          >
            <Plus className="size-4" />
            Agregar
          </Button>
        </div>
      ) : null}
    </div>
  );
}
