import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@shared/ui/card";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import type { CentroAtencionListItem } from "@api/types";
import { useEquivalenciasClinica } from "@features/admin/modules/catalogos/consultorio-familiar/queries/useConsultorioFamiliarConfig";
import {
  useActualizarEquivalencia,
  useCrearEquivalencia,
} from "@features/admin/modules/catalogos/consultorio-familiar/mutations/useConsultorioFamiliarMutations";
import { avisarError } from "@features/admin/modules/catalogos/consultorio-familiar/utils/consultorioFamiliar.feedback";

export const SELECT_CLASS = "h-9 w-full rounded-md border border-line-struct bg-background px-3 text-sm";

interface EquivalenciasSectionProps {
  centros: CentroAtencionListItem[];
}

/**
 * P-03 · Qué centro de SIRES corresponde a cada `cd_clinica` de SERMED.
 * Sin equivalencia activa, la búsqueda del expediente marca CLINICA_SIN_CENTRO.
 */
export const EquivalenciasSection = ({ centros }: EquivalenciasSectionProps) => {
  const { data, isLoading, isError } = useEquivalenciasClinica(true);
  const crear = useCrearEquivalencia();
  const actualizar = useActualizarEquivalencia();
  const [clave, setClave] = useState("");
  const [centroId, setCentroId] = useState("");

  const items = data?.items ?? [];

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await crear.mutateAsync({ claveClinicaSermed: clave.trim(), idCentroAtencion: Number(centroId) });
      toast.success("Equivalencia agregada");
      setClave("");
      setCentroId("");
    } catch (error) {
      avisarError("No se pudo agregar la equivalencia", error);
    }
  };

  const cambiarEstado = async (id: number, estaActivo: boolean) => {
    try {
      await actualizar.mutateAsync({ id, data: { estaActivo } });
    } catch (error) {
      avisarError("No se pudo cambiar la equivalencia", error);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Equivalencias de clínica</CardTitle>
        <CardDescription>
          La clave de clínica que trae el expediente de SERMED y el centro de SIRES que le corresponde.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={(e) => void onSubmit(e)} className="grid gap-3 sm:grid-cols-[1fr_2fr_auto] sm:items-end">
          <div className="space-y-1">
            <Label htmlFor="equivalencia-clave" className="text-xs">Clave de clínica SERMED</Label>
            <Input id="equivalencia-clave" value={clave} maxLength={10} onChange={(e) => setClave(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="equivalencia-centro" className="text-xs">Centro de la clave</Label>
            <select
              id="equivalencia-centro"
              className={SELECT_CLASS}
              value={centroId}
              onChange={(e) => setCentroId(e.target.value)}
            >
              <option value="">Selecciona un centro</option>
              {centros.map((centro) => (
                <option key={centro.id} value={centro.id}>{centro.name}</option>
              ))}
            </select>
          </div>
          <Button type="submit" disabled={crear.isPending || clave.trim() === "" || centroId === ""}>
            Agregar equivalencia
          </Button>
        </form>

        {isLoading ? (
          <p className="text-sm text-txt-muted">Cargando equivalencias...</p>
        ) : isError ? (
          <p className="text-sm text-status-critical">No se pudieron cargar las equivalencias.</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-txt-muted italic">Todavía no hay equivalencias.</p>
        ) : (
          <table aria-label="Equivalencias de clínica" className="w-full text-sm">
            <thead className="text-left text-xs text-txt-muted">
              <tr>
                <th className="py-2 font-medium">Clave SERMED</th>
                <th className="py-2 font-medium">Centro de SIRES</th>
                <th className="py-2 font-medium">Estado</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line-hairline">
              {items.map((item) => (
                <tr key={item.idClinicaCentro}>
                  <td className="py-2 font-mono">{item.claveClinicaSermed}</td>
                  <td className="py-2">{item.centro}</td>
                  <td className="py-2">
                    <Badge variant="outline">{item.estaActivo ? "Activa" : "Inactiva"}</Badge>
                  </td>
                  <td className="py-2 text-right">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      disabled={actualizar.isPending}
                      aria-label={`${item.estaActivo ? "Desactivar" : "Activar"} clave ${item.claveClinicaSermed}`}
                      onClick={() => void cambiarEstado(item.idClinicaCentro, !item.estaActivo)}
                    >
                      {item.estaActivo ? "Desactivar" : "Activar"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
};
