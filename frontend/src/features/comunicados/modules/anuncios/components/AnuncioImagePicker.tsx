import { useEffect, useId, useMemo } from "react";
import { FileText, ImageIcon, X } from "lucide-react";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Button } from "@shared/ui/button";
import { cn } from "@shared/utils/styling/cn";

interface AnuncioFilePickerProps {
  label: string;
  hint?: string;
  accept: string;
  kind: "image" | "file";
  value: File | null;
  existingUrl?: string | null;
  onChange: (file: File | null) => void;
  error?: string;
}

/**
 * Input de archivo oculto + label estilizado + preview.
 * Molde: `catalogos/cies/components/CiesUploadForm.tsx`.
 *
 * Sirve tanto para la imagen (preview de miniatura) como para el PDF
 * adjunto (solo muestra el nombre del archivo, sin preview visual).
 */
export function AnuncioImagePicker({
  label,
  hint,
  accept,
  kind,
  value,
  existingUrl,
  onChange,
  error,
}: AnuncioFilePickerProps) {
  const inputId = useId();
  // La URL del archivo elegido se deriva de él; el efecto solo la libera.
  const objectUrl = useMemo(() => (value ? URL.createObjectURL(value) : null), [value]);

  useEffect(() => {
    if (!objectUrl) return;
    return () => URL.revokeObjectURL(objectUrl);
  }, [objectUrl]);

  const previewUrl = objectUrl ?? existingUrl ?? null;
  const displayName = useMemo(() => {
    if (value) return value.name;
    if (existingUrl) return existingUrl.split("/").pop() ?? existingUrl;
    return null;
  }, [value, existingUrl]);

  return (
    <div className="space-y-2">
      <Label htmlFor={inputId}>{label}</Label>
      <label
        htmlFor={inputId}
        className={cn(
          "group flex cursor-pointer items-center gap-3 rounded-2xl border border-dashed border-line-struct bg-subtle/40 px-4 py-3 transition-colors",
          "hover:border-brand/60 hover:bg-brand/5",
          value && "border-brand/50 bg-brand/5",
          error && "border-status-critical/60",
        )}
      >
        {kind === "image" && previewUrl ? (
          <img
            src={previewUrl}
            alt=""
            className="size-10 shrink-0 rounded-lg object-cover"
          />
        ) : kind === "image" ? (
          <ImageIcon className="size-4 shrink-0 text-txt-muted transition-colors group-hover:text-brand" />
        ) : (
          <FileText className="size-4 shrink-0 text-txt-muted transition-colors group-hover:text-brand" />
        )}

        <span className="truncate text-sm text-txt-body">
          {displayName ?? "Seleccionar archivo"}
        </span>

        <Input
          id={inputId}
          type="file"
          accept={accept}
          className="sr-only"
          onChange={(event) => onChange(event.target.files?.[0] ?? null)}
        />

        {value ? (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            className="ml-auto shrink-0"
            aria-label={`Quitar ${label.toLowerCase()}`}
            onClick={(event) => {
              event.preventDefault();
              onChange(null);
            }}
          >
            <X className="size-4" />
          </Button>
        ) : null}
      </label>

      {hint ? <p className="text-xs text-txt-muted">{hint}</p> : null}
      {error ? <p className="text-xs text-status-critical">{error}</p> : null}
    </div>
  );
}
