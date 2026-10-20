import { useState } from "react";
import { Check, Search } from "lucide-react";
import { Input } from "@shared/ui/input";
import { useDebounce } from "@shared/hooks/useDebounce";
import { cn } from "@shared/utils/styling/cn";
import { usePadronOptions } from "@features/padrones/queries/usePadrones";
import type { PadronOption, PadronRegistry } from "@api/types/padrones.types";

interface PadronOptionFieldProps {
  id: string;
  registry: PadronRegistry;
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}

const PLACEHOLDER: Record<PadronRegistry, string> = {
  cronicos: "Buscar CIE-10 por código o descripción (mín. 2 letras)",
  discapacidad: "Buscar discapacidad por clave o nombre (mín. 2 letras)",
};

/** Busca en el endpoint de opciones del padrón (permiso propio del padrón). */
export function PadronOptionField({ id, registry, value, onChange, disabled = false }: PadronOptionFieldProps) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<PadronOption | null>(null);
  const debounced = useDebounce(search, 300);
  const { data, isFetching } = usePadronOptions(registry, debounced, !disabled);
  const items = data?.items ?? [];

  const pick = (option: PadronOption) => {
    setSelected(option);
    onChange(String(option.id));
  };

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-txt-muted" />
        <Input
          id={id}
          className="pl-9"
          value={search}
          disabled={disabled}
          placeholder={PLACEHOLDER[registry]}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      {selected && value === String(selected.id) ? (
        <p className="text-sm text-txt-body">
          Seleccionado: <strong>{selected.code}</strong> — {selected.description}
        </p>
      ) : null}
      {debounced.trim().length >= 2 ? (
        <ul className="max-h-48 overflow-y-auto rounded-xl border border-line-hairline" role="listbox">
          {items.length === 0 ? (
            <li className="px-3 py-2 text-sm text-txt-muted">
              {isFetching ? "Buscando..." : "Sin resultados"}
            </li>
          ) : (
            items.map((option) => {
              const isSelected = value === String(option.id);
              return (
                <li key={String(option.id)}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    className={cn(
                      "flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-subtle",
                      isSelected && "bg-subtle font-medium",
                    )}
                    onClick={() => pick(option)}
                  >
                    {isSelected ? <Check className="size-4 shrink-0" /> : <span className="size-4 shrink-0" />}
                    <span className="font-mono text-xs text-txt-muted">{option.code}</span>
                    <span>{option.description}</span>
                  </button>
                </li>
              );
            })
          )}
        </ul>
      ) : null}
    </div>
  );
}
