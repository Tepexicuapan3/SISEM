import { useState } from "react";
import { Badge } from "@shared/ui/badge";
import { Input } from "@shared/ui/input";
import { useUsersList } from "@/domains/auth-access/hooks/rbac/users/useUsersList";
import { useDebounce } from "@shared/hooks/useDebounce";

interface Props {
  /** id (SyUsuario) seleccionado, o null/undefined si no hay selección. */
  value: number | null | undefined;
  onChange: (usuarioId: number) => void;
  /** Evita consultar la lista mientras el contenedor (diálogo) está cerrado. */
  enabled?: boolean;
}

/**
 * Buscador de usuarios con tipo de personal Médico, usado por el alta de
 * médico (`MedicoCreateDialog`). El estado de búsqueda es local: se reinicia
 * cuando el contenedor se desmonta.
 */
export function MedicoUsuarioPicker({ value, onChange, enabled = true }: Props) {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounce(search, 350);

  const { data: usersData, isFetching: isSearching } = useUsersList(
    { search: debouncedSearch, pageSize: 20, page: 1 },
    { enabled: enabled && debouncedSearch.length >= 2 },
  );
  const medicoUsers = (usersData?.items ?? []).filter(
    (u) => (u.tipoPersonal?.name ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase() === "MEDICO",
  );

  return (
    <div className="space-y-2">
      <Input
        placeholder="Escribe nombre o usuario..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      {search.length > 0 && search.length < 2 ? (
        <p className="text-xs text-txt-muted">Escribe al menos 2 caracteres para buscar.</p>
      ) : null}
      {debouncedSearch.length >= 2 && (
        <div className="rounded-xl border border-line-struct bg-subtle/20 divide-y divide-line-struct/50 max-h-44 overflow-y-auto">
          {isSearching ? (
            <p className="px-3 py-2 text-xs text-txt-muted">Buscando...</p>
          ) : medicoUsers.length === 0 ? (
            <p className="px-3 py-2 text-xs text-txt-muted">
              Sin usuarios médicos para "{debouncedSearch}"
            </p>
          ) : (
            medicoUsers.map((u) => {
              const selected = value === u.id;
              const displayName = u.fullname || u.username;
              const initials = displayName.slice(0, 2).toUpperCase();
              return (
                <button
                  key={u.id} type="button"
                  className={`flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-subtle/40 ${selected ? "bg-primary/5 border-l-2 border-primary" : ""}`}
                  onClick={() => onChange(u.id)}
                >
                  <div className={`flex size-7 shrink-0 items-center justify-center rounded-lg text-xs font-semibold select-none ${selected ? "bg-primary text-primary-foreground" : "bg-primary/10 text-primary"}`}>
                    {initials}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{displayName}</p>
                    <p className="text-xs text-txt-muted">{u.username}</p>
                  </div>
                  {selected && <Badge variant="stable" className="text-xs shrink-0">✓ Seleccionado</Badge>}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
