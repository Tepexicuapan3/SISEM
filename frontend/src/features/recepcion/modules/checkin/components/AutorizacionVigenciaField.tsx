import { ShieldAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@shared/ui/alert";
import { Label } from "@shared/ui/label";
import { Textarea } from "@shared/ui/textarea";

interface AutorizacionVigenciaFieldProps {
  id: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

/**
 * Paciente sin vigencia: la cita no se cancela, pero el check-in solo se
 * confirma si Capital Humano ordena atenderlo. Recepción registra el motivo
 * u oficio; el backend guarda quién lo aceptó (`PACIENTE_SIN_VIGENCIA` en
 * `qr_checkin_usecase.py`).
 */
export function AutorizacionVigenciaField({
  id,
  value,
  onChange,
  disabled,
}: AutorizacionVigenciaFieldProps) {
  return (
    <div className="space-y-3">
      <Alert variant="warning">
        <ShieldAlert className="size-4" />
        <AlertTitle>Paciente sin vigencia</AlertTitle>
        <AlertDescription>
          Solo se puede atender si Capital Humano lo autoriza. Registra el
          motivo o el número de oficio para confirmar el check-in.
        </AlertDescription>
      </Alert>
      <div className="space-y-2">
        <Label htmlFor={id}>Motivo u oficio de Capital Humano</Label>
        <Textarea
          id={id}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Ej. Oficio CH-123/2026, autorizó Lic. ..."
          maxLength={500}
          disabled={disabled}
        />
      </div>
    </div>
  );
}
