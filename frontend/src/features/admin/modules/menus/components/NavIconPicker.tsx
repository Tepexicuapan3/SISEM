import { useMemo, useState } from "react";
import { ChevronsUpDown } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@shared/ui/popover";
import { cn } from "@shared/utils/styling/cn";
import {
  buildNavIconOptions,
  DEFAULT_NAV_ICON,
  NAV_ICONS,
  NAV_ICON_LABELS,
  resolveNavIcon,
  type NavIconOption,
} from "@/app/navigation/nav-icons";

interface NavIconPickerProps {
  /** Nombre kebab-case del icono seleccionado (clave de `NAV_ICONS`), o
   * `null` si todavia no se eligio ninguno -- el modulo cae al icono
   * default (`Circle`) via `resolveNavIcon`. */
  value: string | null;
  onChange: (name: string) => void;
  disabled?: boolean;
  className?: string;
}

/**
 * Grid visual de iconos -- UNICA superficie donde un admin elige el icono
 * de un modulo. Nunca expone el nombre kebab-case como input de texto
 * libre (mismo criterio que `MenuDestinationSelect` con los codigos de
 * permiso): se elige por LABEL humano y preview visual, el string plano
 * que viaja a `cat_modulos.icono` es un detalle de implementacion.
 *
 * Las opciones ofrecidas son EXACTAMENTE `Object.keys(NAV_ICONS)` -- el
 * test anti-drift (`nav-icons.test.ts`) lo verifica para que agregar un
 * icono a `NAV_ICONS` sin sumarlo acá (o viceversa) rompa CI en vez de
 * degradar en silencio.
 */
export function NavIconPicker({
  value,
  onChange,
  disabled = false,
  className,
}: NavIconPickerProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const options = useMemo(() => buildNavIconOptions(), []);
  const selectedLabel = value ? (NAV_ICON_LABELS[value] ?? value) : null;
  // Ver comentario en `ModuleTreeRow.tsx`/`NavMain.tsx`: se
  // envuelve en un objeto para no romper react-hooks/static-components con
  // `resolveNavIcon`.
  const selectedIcon = { Component: resolveNavIcon(value) };

  const normalizedSearch = search.trim().toLowerCase();
  const filtered =
    normalizedSearch.length === 0
      ? options
      : options.filter(
          (option) =>
            option.label.toLowerCase().includes(normalizedSearch) ||
            option.name.toLowerCase().includes(normalizedSearch),
        );

  const handleSelect = (option: NavIconOption) => {
    onChange(option.name);
    setOpen(false);
    setSearch("");
  };

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        if (!disabled) setOpen(next);
      }}
    >
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className={cn(
            "w-full justify-between font-normal",
            !selectedLabel && "text-txt-muted",
            className,
          )}
        >
          <span className="flex min-w-0 items-center gap-2">
            <selectedIcon.Component className="size-4 shrink-0" />
            <span className="truncate">
              {selectedLabel ?? "Selecciona un icono"}
            </span>
          </span>
          <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 p-2">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar icono..."
          className="mb-2 h-8 text-sm"
          autoFocus
        />
        <div className="max-h-64 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="py-4 text-center text-sm text-txt-muted">
              Sin resultados
            </p>
          ) : (
            <div className="grid grid-cols-5 gap-1">
              {filtered.map((option) => {
                // Mismo patron que `selectedIcon` arriba: envuelto en objeto
                // para no romper react-hooks/static-components.
                const icon = { Component: NAV_ICONS[option.name] ?? DEFAULT_NAV_ICON };
                const isSelected = value === option.name;
                return (
                  <button
                    key={option.name}
                    type="button"
                    onClick={() => handleSelect(option)}
                    title={option.label}
                    aria-label={option.label}
                    aria-pressed={isSelected}
                    className={cn(
                      "flex flex-col items-center gap-1 rounded-lg border border-transparent p-2 text-txt-muted transition-colors hover:border-line-struct/60 hover:bg-surface-hover hover:text-txt-body",
                      isSelected &&
                        "border-brand bg-surface-hover text-txt-body",
                    )}
                  >
                    <icon.Component className="size-4 shrink-0" />
                    <span className="w-full truncate text-center text-[10px] leading-tight">
                      {option.label}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
