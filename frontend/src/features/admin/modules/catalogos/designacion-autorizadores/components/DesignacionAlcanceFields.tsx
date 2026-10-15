import { useState } from "react";
import { ChevronsUpDown, X } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Checkbox } from "@shared/ui/checkbox";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@shared/ui/popover";
import type { CentroTipoDesignacion } from "@api/types";
import {
  setGlobalScope,
  toggleCentro,
  toggleTipoCentro,
  type ScopeSelection,
} from "@features/admin/modules/catalogos/designacion-autorizadores/domain/designacion.scope";

interface CenterOption {
  id: number;
  name: string;
}

interface DesignacionAlcanceFieldsProps {
  value: ScopeSelection;
  onChange: (next: ScopeSelection) => void;
  centers: CenterOption[];
  /** `admin.catalogs.designacionAutorizadores.global`: sin el, "Todos los centros" no se muestra. */
  canGrantGlobal: boolean;
  /** Si la designacion editada ya es global y el usuario no puede tocarla, se bloquea el alcance. */
  disabled?: boolean;
  errorMessage?: string;
}

const TIPO_OPTIONS: { tipo: CentroTipoDesignacion; label: string }[] = [
  { tipo: "CLINICA", label: "Todas las clínicas" },
  { tipo: "HOSPITAL", label: "Todos los hospitales" },
  { tipo: "INSTITUTO", label: "Todos los institutos" },
];

export function DesignacionAlcanceFields({
  value,
  onChange,
  centers,
  canGrantGlobal,
  disabled = false,
  errorMessage,
}: DesignacionAlcanceFieldsProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const scopeLocked = value.global || disabled;
  const filtered = centers.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase()),
  );
  const selectedCenters = value.centros.map((id) => ({
    id,
    name: centers.find((c) => c.id === id)?.name ?? `Centro ${id}`,
  }));

  return (
    <div className="space-y-4" data-testid="designacion-alcance">
      <div className="space-y-2">
        <Label>Alcance de la designación</Label>

        <div className="grid gap-2 sm:grid-cols-2">
          {TIPO_OPTIONS.map(({ tipo, label }) => {
            const id = `alcance-tipo-${tipo}`;
            return (
              <div key={tipo} className="flex items-center gap-2">
                <Checkbox
                  id={id}
                  checked={value.tiposCentro.includes(tipo)}
                  disabled={scopeLocked}
                  onCheckedChange={(checked) =>
                    onChange(toggleTipoCentro(value, tipo, checked === true))
                  }
                />
                <Label htmlFor={id} className="font-normal">
                  {label}
                </Label>
              </div>
            );
          })}

          {canGrantGlobal ? (
            <div className="flex items-center gap-2">
              <Checkbox
                id="alcance-global"
                checked={value.global}
                disabled={disabled}
                onCheckedChange={(checked) => onChange(setGlobalScope(checked === true))}
              />
              <Label htmlFor="alcance-global" className="font-normal">
                Todos los centros
              </Label>
            </div>
          ) : null}
        </div>

        <p className="text-xs text-txt-muted">
          Marcar &quot;Todas las clínicas&quot; (u hospitales / institutos) incluye también las que se
          den de alta en el futuro. Elegir centros uno por uno congela la lista: un centro nuevo no
          quedará cubierto hasta que edites la designación.
        </p>
        {value.global ? (
          <p className="text-xs text-txt-muted">
            &quot;Todos los centros&quot; cubre cualquier centro y exige fecha fin de vigencia. Para
            elegir centros o tipos desmárcalo primero.
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label>Centros específicos</Label>
        <Popover open={open} onOpenChange={(next) => !scopeLocked && setOpen(next)}>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="outline"
              role="combobox"
              aria-expanded={open}
              disabled={scopeLocked}
              className="w-full justify-between font-normal text-txt-muted"
            >
              <span className="truncate">
                {value.centros.length > 0
                  ? `${value.centros.length} centro(s) seleccionado(s)`
                  : "Selecciona uno o más centros"}
              </span>
              <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] p-2">
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar centro..."
              className="mb-2 h-8 text-sm"
              autoFocus
            />
            <div className="max-h-52 overflow-y-auto">
              {filtered.length === 0 ? (
                <p className="py-4 text-center text-sm text-txt-muted">Sin resultados</p>
              ) : (
                filtered.map((center) => {
                  const id = `alcance-centro-${center.id}`;
                  return (
                    <div
                      key={center.id}
                      className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-surface-hover"
                    >
                      <Checkbox
                        id={id}
                        checked={value.centros.includes(center.id)}
                        onCheckedChange={(checked) =>
                          onChange(toggleCentro(value, center.id, checked === true))
                        }
                      />
                      <Label htmlFor={id} className="flex-1 cursor-pointer font-normal">
                        {center.name}
                      </Label>
                    </div>
                  );
                })
              )}
            </div>
          </PopoverContent>
        </Popover>

        {selectedCenters.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {selectedCenters.map((center) => (
              <Badge key={center.id} variant="outline" className="gap-1">
                {center.name}
                <button
                  type="button"
                  aria-label={`Quitar ${center.name}`}
                  disabled={scopeLocked}
                  onClick={() => onChange(toggleCentro(value, center.id, false))}
                >
                  <X className="size-3" />
                </button>
              </Badge>
            ))}
          </div>
        ) : null}
      </div>

      {errorMessage ? (
        <p role="alert" className="text-sm text-status-critical">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
