import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@shared/ui/card";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import type { CentroAtencionListItem, ConsultorioFamiliar } from "@api/types";
import { useConsultoriosList } from "@features/admin/modules/catalogos/consultorios/queries/useConsultoriosList";
import { useConsultoriosFamiliaresConfig } from "@features/admin/modules/catalogos/consultorio-familiar/queries/useConsultorioFamiliarConfig";
import {
  useActualizarConsultorioFamiliar,
  useCrearConsultorioFamiliar,
} from "@features/admin/modules/catalogos/consultorio-familiar/mutations/useConsultorioFamiliarMutations";
import {
  avisarError,
  leerCapacidad,
} from "@features/admin/modules/catalogos/consultorio-familiar/utils/consultorioFamiliar.feedback";
import { SELECT_CLASS } from "@features/admin/modules/catalogos/consultorio-familiar/components/EquivalenciasSection";

const CAPACIDAD_INVALIDA = "La capacidad debe ser un entero mayor a cero, o vacía para no tener tope.";

const FilaConsultorio = ({ item }: { item: ConsultorioFamiliar }) => {
  const actualizar = useActualizarConsultorioFamiliar();
  const [capacidad, setCapacidad] = useState(item.capacidadMaxima?.toString() ?? "");

  const guardarCapacidad = async () => {
    const valor = leerCapacidad(capacidad);
    if (valor === "invalida") {
      toast.error(CAPACIDAD_INVALIDA);
      return;
    }
    try {
      await actualizar.mutateAsync({ id: item.idAdscripcionConsultorio, data: { capacidadMaxima: valor } });
      toast.success("Capacidad actualizada");
    } catch (error) {
      avisarError("No se pudo cambiar la capacidad", error);
    }
  };

  const cambiarEstado = async () => {
    try {
      await actualizar.mutateAsync({ id: item.idAdscripcionConsultorio, data: { estaActivo: !item.estaActivo } });
    } catch (error) {
      avisarError("No se pudo cambiar el consultorio", error);
    }
  };

  return (
    <tr>
      <td className="py-2">
        <p className="font-medium text-txt-body">{item.consultorio}</p>
        <p className="text-xs text-txt-muted">{item.turno}</p>
      </td>
      <td className="py-2 tabular-nums">
        {item.carga ?? 0} / {item.capacidadMaxima ?? "sin tope"}
      </td>
      <td className="py-2">
        <div className="flex items-center gap-1.5">
          <Input
            type="number"
            min={1}
            aria-label={`Capacidad de ${item.consultorio}`}
            placeholder="Sin tope"
            value={capacidad}
            onChange={(e) => setCapacidad(e.target.value)}
            className="h-8 w-24"
          />
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={actualizar.isPending}
            aria-label={`Guardar capacidad de ${item.consultorio}`}
            onClick={() => void guardarCapacidad()}
          >
            Guardar
          </Button>
        </div>
      </td>
      <td className="py-2">
        <Badge variant="outline">{item.estaActivo ? "Activo" : "Inactivo"}</Badge>
      </td>
      <td className="py-2 text-right">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={actualizar.isPending}
          aria-label={`${item.estaActivo ? "Desactivar" : "Activar"} ${item.consultorio}`}
          onClick={() => void cambiarEstado()}
        >
          {item.estaActivo ? "Desactivar" : "Activar"}
        </Button>
      </td>
    </tr>
  );
};

interface ConsultoriosFamiliaresSectionProps {
  centros: CentroAtencionListItem[];
}

/**
 * P-03 · Qué consultorios de un centro reciben adscripciones y con qué tope.
 * La carga es el número de pacientes con adscripción ACTIVA en el consultorio.
 */
export const ConsultoriosFamiliaresSection = ({ centros }: ConsultoriosFamiliaresSectionProps) => {
  const [centroId, setCentroId] = useState<number | null>(null);
  const [nuevoId, setNuevoId] = useState("");
  const [nuevaCapacidad, setNuevaCapacidad] = useState("");

  const { data, isLoading, isError } = useConsultoriosFamiliaresConfig(centroId, true);
  const { data: delCentro } = useConsultoriosList(
    { idCenter: centroId ?? undefined, isActive: true, pageSize: 500 },
    { enabled: centroId != null },
  );
  const crear = useCrearConsultorioFamiliar();

  const items = data?.items ?? [];
  const yaFamiliares = new Set(items.map((item) => item.consultorioId));
  const disponibles = (delCentro?.items ?? []).filter((c) => !yaFamiliares.has(c.id));

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const capacidadMaxima = leerCapacidad(nuevaCapacidad);
    if (capacidadMaxima === "invalida") {
      toast.error(CAPACIDAD_INVALIDA);
      return;
    }
    try {
      await crear.mutateAsync({ consultorioId: Number(nuevoId), capacidadMaxima });
      toast.success("Consultorio familiar agregado");
      setNuevoId("");
      setNuevaCapacidad("");
    } catch (error) {
      avisarError("No se pudo agregar el consultorio", error);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Consultorios familiares</CardTitle>
        <CardDescription>
          Consultorios de medicina general que reciben pacientes adscritos, con su carga y su tope.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="max-w-sm space-y-1">
          <Label htmlFor="familiares-centro" className="text-xs">Centro de los consultorios</Label>
          <select
            id="familiares-centro"
            className={SELECT_CLASS}
            value={centroId ?? ""}
            onChange={(e) => {
              setCentroId(e.target.value ? Number(e.target.value) : null);
              setNuevoId("");
            }}
          >
            <option value="">Selecciona un centro</option>
            {centros.map((centro) => (
              <option key={centro.id} value={centro.id}>{centro.name}</option>
            ))}
          </select>
        </div>

        {centroId == null ? null : (
          <>
            <form onSubmit={(e) => void onSubmit(e)} className="grid gap-3 sm:grid-cols-[2fr_1fr_auto] sm:items-end">
              <div className="space-y-1">
                <Label htmlFor="familiares-nuevo" className="text-xs">Consultorio por agregar</Label>
                <select
                  id="familiares-nuevo"
                  className={SELECT_CLASS}
                  value={nuevoId}
                  onChange={(e) => setNuevoId(e.target.value)}
                >
                  <option value="">Selecciona un consultorio</option>
                  {disponibles.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}{c.turnName ? ` · ${c.turnName}` : ""}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="familiares-capacidad" className="text-xs">Capacidad del consultorio nuevo</Label>
                <Input
                  id="familiares-capacidad"
                  type="number"
                  min={1}
                  placeholder="Sin tope"
                  value={nuevaCapacidad}
                  onChange={(e) => setNuevaCapacidad(e.target.value)}
                />
              </div>
              <Button type="submit" disabled={crear.isPending || nuevoId === ""}>
                Agregar consultorio
              </Button>
            </form>

            {isLoading ? (
              <p className="text-sm text-txt-muted">Cargando consultorios...</p>
            ) : isError ? (
              <p className="text-sm text-status-critical">No se pudieron cargar los consultorios.</p>
            ) : items.length === 0 ? (
              <p className="text-sm text-txt-muted italic">Este centro todavía no tiene consultorios familiares.</p>
            ) : (
              <table aria-label="Consultorios familiares" className="w-full text-sm">
                <thead className="text-left text-xs text-txt-muted">
                  <tr>
                    <th className="py-2 font-medium">Consultorio</th>
                    <th className="py-2 font-medium">Carga / tope</th>
                    <th className="py-2 font-medium">Capacidad</th>
                    <th className="py-2 font-medium">Estado</th>
                    <th className="py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-line-hairline">
                  {items.map((item) => (
                    <FilaConsultorio key={`${item.idAdscripcionConsultorio}-${item.capacidadMaxima}`} item={item} />
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
};
