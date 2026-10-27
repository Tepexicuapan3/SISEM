import { History } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Skeleton } from "@shared/ui/skeleton";
import { useAutorizadorHistorial } from "@features/admin/modules/autorizadores/queries/useAutorizadores";
import { formatFecha, MOVIMIENTOS } from "@features/admin/modules/autorizadores/utils/autorizador.format";

interface AutorizadorHistorialProps {
  idAutorizador: number;
  enabled: boolean;
}

const formatFechaHora = (valor: string) =>
  new Date(valor).toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" });

const RESUMEN_CAMPOS: Record<string, string> = {
  cargo: "Cargo",
  numeroOficio: "Oficio",
  fechaFinVigencia: "Fin de vigencia",
  fechaInicioVigencia: "Inicio de vigencia",
  clave: "Tipo",
  tipoAlcance: "Alcance",
  centroId: "Centro",
  tipoCentro: "Tipo de centro",
};

const mostrar = (valor: unknown) => {
  if (valor === null || valor === undefined || valor === "") return "—";
  const texto = String(valor);
  return /^\d{4}-\d{2}-\d{2}$/.test(texto) ? formatFecha(texto) : texto;
};

/** Muestra solo los campos simples que cambiaron; el detalle completo vive en la bitacora. */
const describirCambio = (
  antes: Record<string, unknown> | null,
  despues: Record<string, unknown> | null,
): string[] =>
  Object.keys(RESUMEN_CAMPOS)
    .filter((clave) => (antes && clave in antes) || (despues && clave in despues))
    .map((clave) => {
      const anterior = antes?.[clave];
      const nuevo = despues?.[clave];
      if (typeof anterior === "object" && anterior !== null) return null;
      if (typeof nuevo === "object" && nuevo !== null) return null;
      if (antes && despues && anterior !== nuevo) {
        return `${RESUMEN_CAMPOS[clave]}: ${mostrar(anterior)} → ${mostrar(nuevo)}`;
      }
      return `${RESUMEN_CAMPOS[clave]}: ${mostrar(nuevo ?? anterior)}`;
    })
    .filter((linea): linea is string => Boolean(linea));

export function AutorizadorHistorial({ idAutorizador, enabled }: AutorizadorHistorialProps) {
  const { data, isLoading, isError, refetch } = useAutorizadorHistorial(idAutorizador, enabled);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, indice) => (
          <Skeleton key={`hist-${indice}`} className="h-14" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="text-center text-sm text-txt-muted">
        No se pudo cargar el historial.{" "}
        <button type="button" className="underline" onClick={() => void refetch()}>
          Reintentar
        </button>
      </div>
    );
  }

  const movimientos = data?.items ?? [];
  if (movimientos.length === 0) {
    return <p className="text-center text-sm text-txt-muted">Sin movimientos registrados.</p>;
  }

  return (
    <ol className="space-y-3" aria-label="Historial del autorizador">
      {movimientos.map((movimiento) => (
        <li key={movimiento.id} className="rounded-xl border border-line-struct p-3">
          <div className="flex flex-wrap items-center gap-2">
            <History className="size-4 text-txt-muted" />
            <Badge variant="outline">{MOVIMIENTOS[movimiento.tipoMovimiento]}</Badge>
            <span className="text-sm text-txt-body">{movimiento.responsable?.name || "Proceso automático"}</span>
            <span className="ml-auto text-xs text-txt-muted">{formatFechaHora(movimiento.fechaMovimiento)}</span>
          </div>
          {movimiento.motivo ? (
            <p className="mt-2 text-sm text-txt-body">
              Motivo: {movimiento.motivo.descripcion}
              {movimiento.descripcionMotivo ? ` — ${movimiento.descripcionMotivo}` : ""}
            </p>
          ) : null}
          {/* El alta y los cambios de estatus guardan la foto completa; solo se resumen los cambios puntuales. */}
          {["EDICION", "RENOVACION", "ALTA_TIPO", "BAJA_TIPO", "ALTA_CENTRO", "BAJA_CENTRO"].includes(
            movimiento.tipoMovimiento,
          )
            ? describirCambio(movimiento.datosAnteriores, movimiento.datosNuevos).map((linea) => (
                <p key={linea} className="mt-1 text-xs text-txt-muted">
                  {linea}
                </p>
              ))
            : null}
        </li>
      ))}
    </ol>
  );
}
