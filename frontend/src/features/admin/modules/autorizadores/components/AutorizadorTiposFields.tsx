import { useState } from "react";
import { ChevronRight, MapPin } from "lucide-react";
import type { ClaveTipoAutorizacion } from "@api/types/autorizaciones/autorizadores.types";
import { Badge } from "@shared/ui/badge";
import { Checkbox } from "@shared/ui/checkbox";
import { Label } from "@shared/ui/label";
import { cn } from "@shared/utils/styling/cn";
import { DesignacionAlcanceFields } from "@features/admin/modules/catalogos/designacion-autorizadores/components/DesignacionAlcanceFields";
import type { TipoFormValue } from "@features/admin/modules/autorizadores/domain/autorizador.schemas";
import {
  alternarTipo,
  cambiarAlcance,
  unificarAlcance,
} from "@features/admin/modules/autorizadores/domain/autorizador.tipos";

interface CentroOpcion {
  id: number;
  name: string;
}

interface AutorizadorTiposFieldsProps {
  value: TipoFormValue[];
  onChange: (next: TipoFormValue[]) => void;
  tiposCatalogo: { clave: ClaveTipoAutorizacion; nombre: string }[];
  centers: CentroOpcion[];
  /** `admin:autorizadores:global` */
  canGrantGlobal: boolean;
  disabled?: boolean;
  /** Error general (ningun tipo elegido). */
  errorMessage?: string;
  /** Error de alcance por tipo. */
  erroresPorClave?: Partial<Record<ClaveTipoAutorizacion, string>>;
}

/** Resumen corto del alcance para la tarjeta del tipo. */
const resumenAlcance = (tipo: TipoFormValue): string => {
  const { centros, tiposCentro, global } = tipo.alcance;
  if (global) return "Todos los centros";
  const partes = [];
  if (tiposCentro.length > 0) partes.push(`${tiposCentro.length} tipo(s) de centro`);
  if (centros.length > 0) partes.push(`${centros.length} centro(s)`);
  return partes.join(" · ");
};

/**
 * Tipos de autorizacion (permisos independientes) y los centros de cada uno.
 * Vista dividida: a la izquierda los tipos, a la derecha los centros del tipo
 * que se esta editando. Se edita un tipo a la vez: el selector de alcance
 * reutilizado de designaciones usa ids fijos y no puede repetirse.
 */
export function AutorizadorTiposFields({
  value,
  onChange,
  tiposCatalogo,
  centers,
  canGrantGlobal,
  disabled = false,
  errorMessage,
  erroresPorClave = {},
}: AutorizadorTiposFieldsProps) {
  const [mismosCentros, setMismosCentros] = useState(false);
  const [abierto, setAbierto] = useState<ClaveTipoAutorizacion | null>(
    () => value.find((tipo) => tipo.seleccionado)?.clave ?? null,
  );

  const nombreDe = (clave: ClaveTipoAutorizacion) =>
    tiposCatalogo.find((tipo) => tipo.clave === clave)?.nombre ?? clave;

  const tipoAbierto = value.find((tipo) => tipo.clave === abierto && tipo.seleccionado);
  const elegidos = value.filter((tipo) => tipo.seleccionado);

  const alternar = (clave: ClaveTipoAutorizacion, seleccionado: boolean) => {
    const siguiente = alternarTipo(value, clave, seleccionado, { mismosCentros });
    onChange(siguiente);
    if (seleccionado) {
      setAbierto(clave);
    } else if (abierto === clave) {
      setAbierto(siguiente.find((tipo) => tipo.seleccionado)?.clave ?? null);
    }
  };

  return (
    <div className="space-y-3" data-testid="autorizador-tipos">
      <p className="text-xs text-txt-muted">
        Cada tipo es un permiso independiente con sus propios centros. Marca los tipos que puede
        autorizar y, para cada uno, elige los centros.
      </p>

      {/* Vista dividida solo si el formulario (@container) es ancho; si no, se apila. */}
      <div className="grid gap-4 @2xl:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
        {/* Columna de tipos */}
        <div className="space-y-2">
          {value.map((tipo) => {
            const id = `aut-tipo-${tipo.clave}`;
            const resumen = resumenAlcance(tipo);
            const activo = abierto === tipo.clave && tipo.seleccionado;
            const error = tipo.seleccionado ? erroresPorClave[tipo.clave] : undefined;
            return (
              <div
                key={tipo.clave}
                className={cn(
                  "rounded-xl border px-3 py-2.5 transition-colors",
                  activo ? "border-brand bg-surface-hover" : "border-line-struct",
                  error && "border-status-critical",
                )}
              >
                <div className="flex items-center gap-3">
                  <Checkbox
                    id={id}
                    checked={tipo.seleccionado}
                    disabled={disabled}
                    onCheckedChange={(checked) => alternar(tipo.clave, checked === true)}
                  />
                  <Label htmlFor={id} className="flex-1 cursor-pointer font-medium">
                    {nombreDe(tipo.clave)}
                  </Label>
                  {tipo.seleccionado && !activo ? (
                    <button
                      type="button"
                      onClick={() => setAbierto(tipo.clave)}
                      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-txt-muted hover:bg-surface-hover hover:text-txt-body"
                      aria-label={`Editar centros de ${nombreDe(tipo.clave)}`}
                    >
                      <MapPin className="size-3.5" />
                      Centros
                      <ChevronRight className="size-3.5" />
                    </button>
                  ) : null}
                </div>
                {tipo.seleccionado ? (
                  <p
                    className={cn(
                      "mt-1 pl-7 text-xs",
                      resumen ? "text-txt-muted" : "text-status-critical",
                    )}
                  >
                    {resumen || "Sin centros asignados"}
                  </p>
                ) : null}
                {error ? (
                  <p role="alert" className="mt-1 pl-7 text-xs text-status-critical">
                    {error}
                  </p>
                ) : null}
              </div>
            );
          })}

          {elegidos.length > 1 ? (
            <div className="flex items-start gap-2 rounded-xl bg-surface-hover px-3 py-2.5">
              <Checkbox
                id="aut-mismos-centros"
                checked={mismosCentros}
                disabled={disabled}
                className="mt-0.5"
                onCheckedChange={(checked) => {
                  const activar = checked === true;
                  setMismosCentros(activar);
                  if (activar && abierto) onChange(unificarAlcance(value, abierto));
                }}
              />
              <Label htmlFor="aut-mismos-centros" className="text-sm font-normal leading-snug">
                Usar los mismos centros en todos los tipos
              </Label>
            </div>
          ) : null}
        </div>

        {/* Panel de centros del tipo abierto */}
        <div className="min-w-0 rounded-2xl border border-line-struct p-4">
          {tipoAbierto ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-txt-body">
                  {mismosCentros
                    ? "Centros donde autoriza (todos los tipos elegidos)"
                    : `Centros donde autoriza ${nombreDe(tipoAbierto.clave)}`}
                </p>
                {mismosCentros ? (
                  <div className="flex flex-wrap gap-1">
                    {elegidos.map((tipo) => (
                      <Badge key={tipo.clave} variant="outline">
                        {nombreDe(tipo.clave)}
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>
              <DesignacionAlcanceFields
                value={tipoAbierto.alcance}
                centers={centers}
                canGrantGlobal={canGrantGlobal || tipoAbierto.alcance.global}
                disabled={disabled}
                errorMessage={erroresPorClave[tipoAbierto.clave]}
                onChange={(alcance) =>
                  onChange(cambiarAlcance(value, tipoAbierto.clave, alcance, { mismosCentros }))
                }
              />
            </div>
          ) : (
            <div className="flex h-full min-h-40 flex-col items-center justify-center gap-2 text-center text-sm text-txt-muted">
              <MapPin className="size-6" />
              <p>Marca un tipo de autorización para asignarle sus centros.</p>
            </div>
          )}
        </div>
      </div>

      {errorMessage ? (
        <p role="alert" className="text-sm text-status-critical">
          {errorMessage}
        </p>
      ) : null}
    </div>
  );
}
