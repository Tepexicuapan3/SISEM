import { useState } from "react";
import { ClipboardList, Loader2 } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import type { SeguimientoPendienteItem } from "@api/types";
import { useSeguimientosPendientes } from "@features/recepcion/modules/citas/queries/useSeguimientosPendientes";
import { AgendarSeguimientoDialog } from "./AgendarSeguimientoDialog";

const PAGE_SIZE = 25;

const formatFecha = (fecha: string): string =>
  new Date(`${fecha}T00:00:00`).toLocaleDateString("es-MX", { weekday: "short", day: "2-digit", month: "short" });

/**
 * Seguimientos que indicó el médico al cerrar la nota y todavía no tienen
 * cita: no eligió horario, o el paciente tiene otro consultorio familiar y
 * la cita la agenda recepción. Incluye los atrasados de hasta 30 días.
 */
export function SeguimientosPorAgendar({ enabled }: { enabled: boolean }) {
  const [page, setPage] = useState(1);
  const [aAgendar, setAAgendar] = useState<SeguimientoPendienteItem | null>(null);
  const { data, isLoading, isError, refetch } = useSeguimientosPendientes(
    { page, pageSize: PAGE_SIZE },
    { enabled },
  );
  const items = data?.items ?? [];
  const totalPages = data?.totalPages ?? 0;

  return (
    <section className="space-y-3 rounded-xl border border-line-struct bg-paper p-4">
      <header className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="flex items-center gap-2 text-base font-semibold text-txt-body">
            <ClipboardList className="size-4" aria-hidden="true" /> Seguimientos por agendar
          </h2>
          <p className="text-xs text-txt-muted">
            El médico indicó cuándo debe volver el paciente, pero no quedó cita.
          </p>
        </div>
        {data ? <span className="text-xs text-txt-muted">{data.total}</span> : null}
      </header>

      {isLoading ? (
        <p className="flex items-center gap-2 text-sm text-txt-muted">
          <Loader2 className="size-4 animate-spin" /> Cargando seguimientos...
        </p>
      ) : isError ? (
        <div className="flex items-center gap-3 text-sm text-status-critical">
          <span>No se pudieron cargar los seguimientos.</span>
          <Button type="button" size="sm" variant="outline" onClick={() => void refetch()}>
            Reintentar
          </Button>
        </div>
      ) : items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line-struct p-4 text-center text-sm text-txt-muted">
          No hay seguimientos por agendar.
        </p>
      ) : (
        <ul className="divide-y divide-line-hairline">
          {items.map((item) => (
            <li
              key={item.visitId}
              className="grid grid-cols-[5.5rem_1fr_auto] items-center gap-3 py-2"
            >
              <div className="text-xs">
                <p className="font-semibold text-txt-body first-letter:uppercase">{formatFecha(item.fechaSeguimiento)}</p>
                {item.vencido ? <Badge variant="alert" className="mt-0.5">Atrasado</Badge> : null}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-txt-body">{item.pacienteNombre || `Exp. ${item.noExp}`}</p>
                <p className="truncate text-xs text-txt-muted">
                  Exp. {item.noExp}
                  {item.pkNum ? ` · Fam. ${item.pkNum}` : ""} · {item.visitFolio} · Indicó: {item.medicoNombre}
                </p>
              </div>
              <Button type="button" size="sm" onClick={() => setAAgendar(item)}>
                Agendar
              </Button>
            </li>
          ))}
        </ul>
      )}

      {totalPages > 1 ? (
        <div className="flex items-center justify-end gap-2 text-xs text-txt-muted">
          <Button type="button" size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            Anterior
          </Button>
          <span>Página {page} de {totalPages}</span>
          <Button type="button" size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
            Siguiente
          </Button>
        </div>
      ) : null}

      <AgendarSeguimientoDialog
        seguimiento={aAgendar}
        onOpenChange={(open) => {
          if (!open) setAAgendar(null);
        }}
      />
    </section>
  );
}
