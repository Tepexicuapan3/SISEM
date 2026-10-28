import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@shared/ui/select";
import { Textarea } from "@shared/ui/textarea";
import { useMotivosCancelacion } from "@features/recepcion/modules/citas/queries/useMotivosCancelacion";

interface MotivoCancelacionFieldsProps {
  /** Prefijo de los ids de los campos (dos dialogos pueden convivir en la pagina). */
  idPrefix:   string;
  motivoId:   string;
  onMotivoId: (value: string) => void;
  detalle:    string;
  onDetalle:  (value: string) => void;
  disabled?:  boolean;
  /** Pide el catalogo solo cuando el dialogo esta abierto. */
  enabled?:   boolean;
}

/**
 * Motivo de cancelacion de una cita o ficha de recepcion: motivo tipificado
 * del catalogo MotivoCita (obligatorio, es lo que exige la maquina de
 * estados del backend) y un detalle libre opcional.
 */
export function MotivoCancelacionFields({
  idPrefix,
  motivoId,
  onMotivoId,
  detalle,
  onDetalle,
  disabled,
  enabled = true,
}: MotivoCancelacionFieldsProps) {
  const { data, isLoading, isError } = useMotivosCancelacion({ enabled });
  const motivos = data?.results ?? [];
  const sinMotivos = !isLoading && !isError && motivos.length === 0;

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <label htmlFor={`${idPrefix}-motivo`} className="text-sm font-medium text-txt-body">
          Motivo de la cancelacion <span className="text-status-critical">*</span>
        </label>
        <Select value={motivoId} onValueChange={onMotivoId} disabled={disabled || motivos.length === 0}>
          <SelectTrigger id={`${idPrefix}-motivo`} className="w-full" aria-invalid={!motivoId}>
            <SelectValue placeholder={isLoading ? "Cargando motivos..." : "Selecciona un motivo"} />
          </SelectTrigger>
          <SelectContent>
            {motivos.map((motivo) => (
              <SelectItem key={motivo.id} value={String(motivo.id)}>{motivo.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {isError ? (
          <p className="text-xs text-status-critical">No se pudieron cargar los motivos.</p>
        ) : sinMotivos ? (
          <p className="text-xs text-status-critical">
            No hay motivos de cancelacion activos en el catalogo.
          </p>
        ) : null}
      </div>

      <div className="space-y-1.5">
        <label htmlFor={`${idPrefix}-detalle`} className="text-sm font-medium text-txt-body">
          Detalle (opcional)
        </label>
        <Textarea
          id={`${idPrefix}-detalle`}
          rows={3}
          maxLength={255}
          value={detalle}
          onChange={(e) => onDetalle(e.target.value)}
          disabled={disabled}
          placeholder="Ej. el paciente solicito reagendar, se resolvio por otro medio..."
        />
      </div>
    </div>
  );
}
