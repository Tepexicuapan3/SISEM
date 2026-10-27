import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, CheckCheck } from "lucide-react";
import type { Notificacion } from "@api/types/notificaciones/notificaciones.types";
import { Button } from "@shared/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@shared/ui/popover";
import { cn } from "@shared/utils/styling/cn";
import { useMarcarLeida, useMarcarTodasLeidas } from "@features/notificaciones/mutations/useNotificacionMutations";
import { useContadorNotificaciones, useNotificacionesList } from "@features/notificaciones/queries/useNotificaciones";
import { useNotificacionesRealtime } from "@features/notificaciones/realtime/useNotificacionesRealtime";

const haceCuanto = (fecha: string) => {
  const minutos = Math.max(0, Math.round((Date.now() - new Date(fecha).getTime()) / 60000));
  if (minutos < 1) return "ahora";
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  return `hace ${Math.floor(horas / 24)} d`;
};

/** Campana del header: contador, ultimas notificaciones y conexion en vivo. */
export function NotificacionesBell() {
  const [abierta, setAbierta] = useState(false);
  const navegar = useNavigate();
  useNotificacionesRealtime();

  const { data: contador } = useContadorNotificaciones();
  const { data, isLoading } = useNotificacionesList({ page: 1, pageSize: 8 }, abierta);
  const marcarLeida = useMarcarLeida();
  const marcarTodas = useMarcarTodasLeidas();

  const noLeidas = contador?.noLeidas ?? 0;
  const items = data?.items ?? [];

  const abrir = (notificacion: Notificacion) => {
    if (!notificacion.fechaLectura) marcarLeida.mutate(notificacion.id);
    setAbierta(false);
    navegar(notificacion.urlAccion);
  };

  return (
    <Popover open={abierta} onOpenChange={setAbierta}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative shrink-0"
          aria-label={noLeidas > 0 ? `${noLeidas} notificaciones sin leer` : "Notificaciones, sin pendientes"}
        >
          <Bell className="size-5" />
          {noLeidas > 0 ? (
            <span className="absolute -top-0.5 -right-0.5 flex min-w-4 items-center justify-center rounded-full bg-status-critical px-1 text-[10px] font-semibold leading-4 text-white">
              {noLeidas > 99 ? "99+" : noLeidas}
            </span>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(24rem,calc(100vw-2rem))] p-0">
        <div className="flex items-center justify-between gap-2 border-b border-line-hairline px-4 py-3">
          <p className="text-sm font-semibold text-txt-body">Notificaciones</p>
          {noLeidas > 0 ? (
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              disabled={marcarTodas.isPending}
              onClick={() => marcarTodas.mutate()}
            >
              <CheckCheck className="size-3.5" />
              Marcar todas como leídas
            </Button>
          ) : null}
        </div>

        <div className="max-h-96 overflow-y-auto">
          {isLoading ? (
            <p className="px-4 py-6 text-center text-sm text-txt-muted">Cargando...</p>
          ) : items.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-txt-muted">No tienes notificaciones.</p>
          ) : (
            items.map((notificacion) => (
              <button
                key={notificacion.id}
                type="button"
                onClick={() => abrir(notificacion)}
                className={cn(
                  "flex w-full gap-3 border-b border-line-hairline px-4 py-3 text-left transition-colors last:border-0 hover:bg-surface-hover",
                  !notificacion.fechaLectura && "bg-surface-hover/60",
                )}
              >
                <span
                  className={cn(
                    "mt-1.5 size-2 shrink-0 rounded-full",
                    notificacion.fechaLectura ? "bg-transparent" : "bg-status-info",
                  )}
                  aria-hidden
                />
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-txt-body">{notificacion.titulo}</span>
                  <span className="block break-words text-xs text-txt-muted">{notificacion.cuerpo}</span>
                  <span className="mt-1 block text-[11px] text-txt-muted">{haceCuanto(notificacion.fechaCreacion)}</span>
                </span>
              </button>
            ))
          )}
        </div>

        <div className="border-t border-line-hairline px-4 py-2 text-center">
          <button
            type="button"
            className="text-xs text-txt-muted hover:text-txt-body hover:underline"
            onClick={() => {
              setAbierta(false);
              navegar("/notificaciones");
            }}
          >
            Ver todas
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
