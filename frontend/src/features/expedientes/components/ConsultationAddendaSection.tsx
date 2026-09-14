import { useState } from "react";
import { Loader2, MessageSquarePlus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Textarea } from "@shared/ui/textarea";
import { useConsultationAddenda } from "@features/expedientes/queries/useConsultationAddenda";
import { useAddConsultationAddendum } from "@features/expedientes/mutations/useAddConsultationAddendum";
import { ApiError } from "@api/utils/errors";

interface Props {
  visitId: number;
}

const formatFechaHora = (iso: string) =>
  new Date(iso).toLocaleString("es-MX", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

/**
 * Notas de aclaración de una consulta ya cerrada (NOM-004/024): nunca
 * reemplazan la nota original ni entre sí -- se acumulan, cada una con su
 * fecha y autor. Si hace falta corregir una aclaración, se agrega otra
 * nueva, no se edita la existente (por eso no hay acción de editar/borrar
 * acá).
 */
export const ConsultationAddendaSection = ({ visitId }: Props) => {
  const [mostrarForm, setMostrarForm] = useState(false);
  const [texto, setTexto] = useState("");

  const { data, isLoading } = useConsultationAddenda(visitId, mostrarForm);
  const addMutation = useAddConsultationAddendum();

  const enviar = () => {
    const textoLimpio = texto.trim();
    if (!textoLimpio) return;

    addMutation.mutate(
      { visitId, text: textoLimpio },
      {
        onSuccess: () => {
          toast.success("Aclaración agregada");
          setTexto("");
          setMostrarForm(false);
        },
        onError: (error) => {
          toast.error(
            error instanceof ApiError ? error.message : "No se pudo agregar la aclaración",
          );
        },
      },
    );
  };

  return (
    <div className="mt-3 border-t border-line-struct pt-3">
      {data && data.items.length > 0 && (
        <div className="space-y-2 mb-2">
          <p className="text-xs font-semibold text-txt-muted uppercase tracking-wide">
            Aclaraciones ({data.total})
          </p>
          {data.items.map((addendum) => (
            <div key={addendum.id} className="rounded-md bg-subtle p-2 text-sm">
              <p className="text-txt-body whitespace-pre-wrap">{addendum.text}</p>
              <p className="text-xs text-txt-muted mt-1">
                {formatFechaHora(addendum.createdAt)}
              </p>
            </div>
          ))}
        </div>
      )}

      {isLoading && mostrarForm && (
        <p className="text-xs text-txt-muted">Cargando aclaraciones...</p>
      )}

      {!mostrarForm ? (
        <Button variant="ghost" size="sm" onClick={() => setMostrarForm(true)}>
          <MessageSquarePlus className="mr-2 size-4" />
          Ver / agregar aclaración
        </Button>
      ) : (
        <div className="space-y-2">
          <Textarea
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Aclará algo sobre esta consulta ya cerrada — no se puede editar la nota original."
            maxLength={4000}
            rows={2}
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={!texto.trim() || addMutation.isPending}
              onClick={enviar}
            >
              {addMutation.isPending && <Loader2 className="mr-2 size-4 animate-spin" />}
              Guardar aclaración
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setMostrarForm(false);
                setTexto("");
              }}
            >
              Cerrar
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
