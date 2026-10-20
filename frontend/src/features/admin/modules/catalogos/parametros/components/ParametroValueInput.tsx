import { Input } from "@shared/ui/input";
import { Switch } from "@shared/ui/switch";
import { Textarea } from "@shared/ui/textarea";
import type { ParametroTipo } from "@api/types/catalogos/parameters.types";

interface ParametroValueInputProps {
  id: string;
  valueType: ParametroTipo;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  invalid?: boolean;
  ariaLabel?: string;
}

/** Campo de captura segun el tipo del parametro; siempre trabaja con texto canonico. */
export function ParametroValueInput({
  id,
  valueType,
  value,
  onChange,
  disabled = false,
  invalid = false,
  ariaLabel,
}: ParametroValueInputProps) {
  if (valueType === "BOOLEANO") {
    const checked = value.toLowerCase() === "true";
    return (
      <div className="flex min-h-9 items-center gap-3">
        <Switch
          id={id}
          checked={checked}
          disabled={disabled}
          aria-label={ariaLabel}
          onCheckedChange={(next) => onChange(next ? "true" : "false")}
        />
        <span className="text-sm text-txt-body">{checked ? "Sí" : "No"}</span>
      </div>
    );
  }

  if (valueType === "TEXTO") {
    return (
      <Textarea
        id={id}
        value={value}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-invalid={invalid || undefined}
        rows={2}
        maxLength={2000}
        onChange={(event) => onChange(event.target.value)}
      />
    );
  }

  return (
    <Input
      id={id}
      value={value}
      disabled={disabled}
      aria-label={ariaLabel}
      aria-invalid={invalid || undefined}
      inputMode={valueType === "ENTERO" ? "numeric" : "decimal"}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
