import { useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import type { UsuarioElegible } from "@api/types/autorizaciones/autorizadores.types";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@shared/ui/popover";
import { useDebounce } from "@shared/hooks/useDebounce";
import { cn } from "@shared/utils/styling/cn";
import { useUsuariosElegibles } from "@features/admin/modules/autorizadores/queries/useAutorizadores";

interface AutorizadorUsuarioSelectProps {
  value: number;
  onChange: (usuario: UsuarioElegible) => void;
  disabled?: boolean;
}

/**
 * Usuarios existentes de SIRES que todavia no son autorizadores (el backend
 * excluye inactivos y ya registrados). La cedula se captura en Usuarios; aqui
 * solo se avisa si falta.
 */
export function AutorizadorUsuarioSelect({ value, onChange, disabled = false }: AutorizadorUsuarioSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [elegido, setElegido] = useState<UsuarioElegible | null>(null);
  const debouncedSearch = useDebounce(search, 300);

  const { data, isLoading, isError } = useUsuariosElegibles(debouncedSearch.trim(), open);
  const items = data?.items ?? [];

  return (
    <Popover open={open} onOpenChange={(next) => !disabled && setOpen(next)}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label="Usuario"
          disabled={disabled}
          className={cn("w-full justify-between font-normal", !value && "text-txt-muted")}
        >
          <span className="truncate" title={value && elegido ? elegido.nombreCompleto : undefined}>
            {value && elegido ? elegido.nombreCompleto : "Selecciona un usuario"}
          </span>
          <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] min-w-80 max-w-[calc(100vw-2rem)] p-2">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar por nombre o usuario..."
          className="mb-2 h-8 text-sm"
          autoFocus
        />
        <div className="max-h-52 overflow-y-auto">
          {isLoading ? (
            <p className="py-4 text-center text-sm text-txt-muted">Buscando...</p>
          ) : isError ? (
            <p className="py-4 text-center text-sm text-txt-muted">No se pudo consultar los usuarios.</p>
          ) : items.length === 0 ? (
            <p className="py-4 text-center text-sm text-txt-muted">
              Sin resultados. Solo aparecen usuarios activos que aún no son autorizadores.
            </p>
          ) : (
            items.map((usuario) => (
              <button
                key={usuario.id}
                type="button"
                onClick={() => {
                  setElegido(usuario);
                  onChange(usuario);
                  setOpen(false);
                  setSearch("");
                }}
                className={cn(
                  "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-surface-hover",
                  value === usuario.id && "bg-surface-hover font-medium",
                )}
              >
                <Check className={cn("size-4 shrink-0", value === usuario.id ? "opacity-100" : "opacity-0")} />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="break-words">{usuario.nombreCompleto}</span>
                  <span className="truncate text-xs text-txt-muted">{usuario.usuario}</span>
                </span>
                {!usuario.tieneCedula ? (
                  <Badge variant="alert" className="shrink-0 whitespace-nowrap">
                    Sin cédula
                  </Badge>
                ) : null}
              </button>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
