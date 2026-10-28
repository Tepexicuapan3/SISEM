import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";

interface CampoNumeroProps {
  id: string;
  label: string;
  value: number | null;
  onChange: (valor: number | null) => void;
  error?: string;
  ayuda?: string;
  /** Texto cuando queda vacio (null): p. ej. el valor heredado del tipo. */
  placeholder?: string;
  disabled?: boolean;
}

/** Entero opcional: vacio = null. */
export function CampoNumero({ id, label, value, onChange, error, ayuda, placeholder, disabled }: CampoNumeroProps) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="number"
        inputMode="numeric"
        min={1}
        value={value ?? ""}
        placeholder={placeholder}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        onChange={(event) => {
          const texto = event.target.value.trim();
          onChange(texto === "" ? null : Number(texto));
        }}
      />
      {error ? <p className="text-xs text-status-critical">{error}</p> : null}
      {!error && ayuda ? <p className="text-xs text-txt-muted">{ayuda}</p> : null}
    </div>
  );
}
