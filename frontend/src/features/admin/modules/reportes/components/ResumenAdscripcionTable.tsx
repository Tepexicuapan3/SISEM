import { useState } from "react";
import { ChevronDown, ChevronRight, Eye } from "lucide-react";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Card, CardContent } from "@shared/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@shared/ui/table";
import { cn } from "@shared/utils/styling/cn";
import {
  ocupacionConsultorio,
  type NivelOcupacion,
} from "@features/admin/modules/reportes/domain/adscripcionOcupacion";
import { etiquetaConsultorio } from "@features/admin/modules/reportes/domain/consultorioEtiqueta";
import type { ResumenCentro, ResumenConsultorio } from "@api/types";

export function ConsultorioCell({ numero, nombre }: { numero: number | null; nombre: string }) {
  return (
    <div className="min-w-0">
      <p className="font-medium text-txt-body">{etiquetaConsultorio(numero, nombre)}</p>
      {numero != null ? <p className="text-xs text-txt-muted">{nombre}</p> : null}
    </div>
  );
}

const COLOR_NIVEL: Record<NivelOcupacion, string> = {
  normal: "bg-status-info",
  alto: "bg-status-alert",
  lleno: "bg-status-critical",
};

function Ocupacion({ total, tope, consultorio }: { total: number; tope: number | null; consultorio: string }) {
  const ocupacion = ocupacionConsultorio(total, tope);
  return (
    <div className="flex items-center justify-end gap-2">
      {ocupacion ? (
        <div
          role="progressbar"
          aria-label={`Ocupación de ${consultorio}`}
          aria-valuenow={ocupacion.porcentaje}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-2 w-24 overflow-hidden rounded-full bg-line-struct/60"
        >
          <div
            className={cn("h-full rounded-full", COLOR_NIVEL[ocupacion.nivel])}
            style={{ width: `${Math.min(ocupacion.porcentaje, 100)}%` }}
          />
        </div>
      ) : null}
      <span className="tabular-nums">{`${total} / ${tope ?? "sin tope"}`}</span>
    </div>
  );
}

interface ResumenAdscripcionTableProps {
  centros: ResumenCentro[];
  turnoId: number | null;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  onVerConsultorio: (consultorio: ResumenConsultorio, centro: ResumenCentro) => void;
}

const COLUMNAS = 7;

/** P-03 · Resumen del padrón agrupado por centro; cada centro se contrae. */
export function ResumenAdscripcionTable({
  centros,
  turnoId,
  isLoading,
  isError,
  onRetry,
  onVerConsultorio,
}: ResumenAdscripcionTableProps) {
  const [contraidos, setContraidos] = useState<Set<number>>(new Set());

  const alternar = (idCentro: number) =>
    setContraidos((prev) => {
      const next = new Set(prev);
      if (next.has(idCentro)) next.delete(idCentro);
      else next.add(idCentro);
      return next;
    });

  const mensaje = isLoading
    ? "Cargando resumen..."
    : isError
      ? "No se pudo cargar el resumen."
      : centros.length === 0
        ? "Sin consultorios familiares configurados."
        : null;

  return (
    <Card>
      <CardContent>
        <Table aria-label="Resumen por consultorio" className="min-w-[900px]">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>Consultorio</TableHead>
              <TableHead>Turno</TableHead>
              <TableHead>Médico</TableHead>
              <TableHead className="text-right">Titulares</TableHead>
              <TableHead className="text-right">Familiares</TableHead>
              <TableHead className="text-right">Ocupación</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {mensaje ? (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={COLUMNAS} className="py-6 text-center text-txt-muted">
                  {mensaje}
                  {isError ? (
                    <Button variant="link" size="sm" onClick={onRetry}>Reintentar</Button>
                  ) : null}
                </TableCell>
              </TableRow>
            ) : (
              centros.flatMap((centro) => {
                const abierto = !contraidos.has(centro.idCentroAtencion);
                const consultorios = centro.consultorios.filter((c) => turnoId == null || c.turnoId === turnoId);
                const encabezado = (
                  <TableRow key={`centro-${centro.idCentroAtencion}`} className="bg-line-struct/20 hover:bg-line-struct/30">
                    <TableCell colSpan={COLUMNAS} className="py-2">
                      <button
                        type="button"
                        aria-expanded={abierto}
                        onClick={() => alternar(centro.idCentroAtencion)}
                        className="inline-flex items-center gap-2 font-semibold text-txt-body"
                      >
                        {abierto ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                        <span>{centro.centro}</span>
                        <span className="font-normal text-txt-muted">
                          — {centro.total} adscritos · {centro.titulares} titulares · {centro.familiares} familiares
                        </span>
                      </button>
                    </TableCell>
                  </TableRow>
                );
                if (!abierto) return [encabezado];
                return [
                  encabezado,
                  ...consultorios.map((c) => (
                    <TableRow key={c.consultorioId}>
                      <TableCell>
                        <span className="inline-flex items-center gap-2">
                          <ConsultorioCell numero={c.numero} nombre={c.consultorio} />
                          {!c.estaActivo ? <Badge variant="outline">Inactivo</Badge> : null}
                        </span>
                      </TableCell>
                      <TableCell>{c.turno}</TableCell>
                      <TableCell>
                        {c.medicos.length ? (
                          c.medicos.join(", ")
                        ) : (
                          <span className="text-status-alert">Sin médico activo</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{c.titulares}</TableCell>
                      <TableCell className="text-right tabular-nums">{c.familiares}</TableCell>
                      <TableCell>
                        <Ocupacion
                          total={c.total}
                          tope={c.capacidadMaxima}
                          consultorio={etiquetaConsultorio(c.numero, c.consultorio)}
                        />
                      </TableCell>
                      <TableCell className="text-center">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Ver adscritos de ${etiquetaConsultorio(c.numero, c.consultorio)}`}
                          title="Ver adscritos"
                          onClick={() => onVerConsultorio(c, centro)}
                        >
                          <Eye className="size-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  )),
                ];
              })
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
