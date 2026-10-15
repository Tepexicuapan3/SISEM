import { useState } from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@shared/ui/popover";
import { cn } from "@shared/utils/styling/cn";
import { useDebounce } from "@shared/hooks/useDebounce";
import { useUsersList } from "@/domains/auth-access/hooks/rbac/users/useUsersList";

interface DesignacionUserSelectProps {
  value: number;
  /** Nombre del usuario ya designado (edicion): se muestra sin consultar el listado. */
  selectedLabel?: string | null;
  onChange: (userId: number, label: string, adscripcion: string | null) => void;
  disabled?: boolean;
}

/**
 * Selector de usuario con busqueda en servidor (el listado de usuarios es
 * paginado). La adscripcion (centro del usuario) se muestra como dato de
 * referencia, distinto del alcance de la designacion.
 */
export function DesignacionUserSelect({
  value,
  selectedLabel,
  onChange,
  disabled = false,
}: DesignacionUserSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [pickedLabel, setPickedLabel] = useState<string | null>(null);
  const debouncedSearch = useDebounce(search, 300);

  const { data, isLoading, isError } = useUsersList(
    { page: 1, pageSize: 20, isActive: true, search: debouncedSearch.trim() || undefined },
    { enabled: open },
  );

  const items = data?.items ?? [];
  const label = pickedLabel ?? selectedLabel ?? null;

  return (
    <Popover open={open} onOpenChange={(next) => !disabled && setOpen(next)}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          className={cn("w-full justify-between font-normal", !value && "text-txt-muted")}
        >
          <span className="truncate">{value && label ? label : "Selecciona un usuario"}</span>
          <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] p-2">
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
            <p className="py-4 text-center text-sm text-txt-muted">
              No se pudo consultar usuarios. Verifica que tengas acceso al listado de usuarios.
            </p>
          ) : items.length === 0 ? (
            <p className="py-4 text-center text-sm text-txt-muted">Sin resultados</p>
          ) : (
            items.map((user) => {
              const name = user.fullname || user.username;
              return (
                <button
                  key={user.id}
                  type="button"
                  onClick={() => {
                    setPickedLabel(name);
                    onChange(user.id, name, user.clinic?.name ?? null);
                    setOpen(false);
                    setSearch("");
                  }}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-surface-hover",
                    value === user.id && "bg-surface-hover font-medium",
                  )}
                >
                  <Check
                    className={cn(
                      "size-4 shrink-0",
                      value === user.id ? "opacity-100" : "opacity-0",
                    )}
                  />
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate">{name}</span>
                    <span className="truncate text-xs text-txt-muted">
                      {user.username}
                      {user.clinic ? ` · Adscrito a ${user.clinic.name}` : ""}
                    </span>
                  </span>
                </button>
              );
            })
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
