import { useState } from "react";
import { toast } from "sonner";
import { ChevronDown, ChevronUp, ClipboardCheck } from "lucide-react";
import { Button } from "@shared/ui/button";
import { ApiError } from "@api/utils/errors";
import { useLegacyReview } from "@features/expedientes/queries/useLegacyReview";
import { useConfirmLegacyReview } from "@features/expedientes/mutations/useConfirmLegacyReview";
import type { LegacyReviewSection as Seccion } from "@api/types/legacy-review.types";

interface Props {
  noExp: string;
  pkNum: number;
}

/**
 * Datos del legado (alergias, antecedentes, hábitos) que el médico revisa
 * antes de que pasen a SIRES. Se confirma por sección: lo marcado se agrega
 * al expediente y lo que se deja sin marcar se descarta. Ninguno de los dos
 * vuelve a aparecer.
 */
export const LegacyReviewSection = ({ noExp, pkNum }: Props) => {
  const [abierto, setAbierto] = useState(false);
  const { data, isLoading } = useLegacyReview(noExp, pkNum, abierto);
  const pendientes = data?.secciones.reduce((total, s) => total + s.items.length, 0) ?? 0;

  return (
    <div className="mt-6 rounded-lg border border-line-struct">
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-subtle/40 transition-colors"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-txt-body">
          <ClipboardCheck className="size-4 text-txt-muted" />
          Datos del sistema anterior por revisar
          {data?.disponible && pendientes > 0 ? ` (${pendientes})` : ""}
        </span>
        {abierto ? <ChevronUp className="size-4 text-txt-muted" /> : <ChevronDown className="size-4 text-txt-muted" />}
      </button>

      {abierto && (
        <div className="border-t border-line-struct p-4 space-y-4">
          {isLoading && <p className="text-txt-muted text-sm text-center py-6">Buscando datos del sistema anterior...</p>}
          {data?.disponible === false && <p className="text-txt-muted text-sm text-center py-6">{data.mensaje}</p>}
          {data?.disponible && data.secciones.length === 0 && (
            <p className="text-txt-muted text-sm text-center py-6">No hay datos pendientes de revisar.</p>
          )}
          {data?.disponible && data.secciones.length > 0 && (
            <>
              <p className="text-xs text-txt-muted">
                Marcá lo que corresponde y confirmá cada sección. Lo que dejes sin marcar se descarta y no vuelve a
                aparecer.
              </p>
              {data.secciones.map((seccion) => (
                <SeccionRevision key={seccion.seccion} noExp={noExp} pkNum={pkNum} seccion={seccion} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
};

const SeccionRevision = ({ noExp, pkNum, seccion }: Props & { seccion: Seccion }) => {
  const [marcados, setMarcados] = useState<Set<string>>(() => new Set(seccion.items.map((i) => i.ref)));
  const confirmar = useConfirmLegacyReview();

  const alternar = (ref: string) =>
    setMarcados((actual) => {
      const siguiente = new Set(actual);
      if (siguiente.has(ref)) siguiente.delete(ref);
      else siguiente.add(ref);
      return siguiente;
    });

  const enviar = () =>
    confirmar.mutate(
      { noExp, pkNum, data: { seccion: seccion.seccion, aceptar: [...marcados] } },
      {
        onSuccess: ({ confirmados, descartados }) =>
          toast.success(`${seccion.titulo}: ${confirmados} agregados, ${descartados} descartados.`),
        onError: (error) =>
          toast.error(error instanceof ApiError ? error.message : "No se pudo confirmar la sección."),
      },
    );

  return (
    <fieldset className="rounded-md bg-subtle p-3 space-y-2">
      <legend className="text-sm font-semibold text-txt-body px-1">{seccion.titulo}</legend>
      {seccion.items.map((item) => (
        <label key={item.ref} className="flex items-start gap-2 text-sm text-txt-body cursor-pointer">
          <input
            id={`legado-${item.ref}`}
            type="checkbox"
            className="mt-1"
            checked={marcados.has(item.ref)}
            onChange={() => alternar(item.ref)}
          />
          <span>
            {item.texto}
            <span className="block text-xs text-txt-muted">
              {item.fecha ? `${item.fecha} · ` : ""}
              {item.origen}
            </span>
          </span>
        </label>
      ))}
      <div className="flex justify-end">
        <Button size="sm" onClick={enviar} disabled={confirmar.isPending}>
          {confirmar.isPending ? "Confirmando..." : `Confirmar ${marcados.size} de ${seccion.items.length}`}
        </Button>
      </div>
    </fieldset>
  );
};
