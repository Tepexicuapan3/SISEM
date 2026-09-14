import { usePatientConsultationsHistory } from "@features/expedientes/queries/usePatientConsultationsHistory";
import { ConsultationAddendaSection } from "@features/expedientes/components/ConsultationAddendaSection";
import { LegacyConsultationHistorySection } from "@features/expedientes/components/LegacyConsultationHistorySection";

interface ExpedienteHistorialTabProps {
  noExp: string;
  pkNum?: number;
}

const formatFecha = (fecha: string | null) => {
  if (!fecha) return "Sin fecha";
  try {
    return new Date(fecha).toLocaleDateString("es-MX", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return fecha;
  }
};

export function ExpedienteHistorialTab({
  noExp,
  pkNum = 0,
}: ExpedienteHistorialTabProps) {
  const { data, isLoading, isError } = usePatientConsultationsHistory(
    noExp,
    pkNum,
  );

  if (isLoading) {
    return (
      <p className="text-txt-muted text-sm py-12 text-center">
        Cargando historial de consultas...
      </p>
    );
  }

  if (isError) {
    return (
      <p className="text-status-critical text-sm py-12 text-center">
        No se pudo cargar el historial de consultas de este paciente.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {!data || data.items.length === 0 ? (
        <p className="text-txt-muted text-sm py-12 text-center">
          Este paciente todavía no tiene consultas cerradas registradas en SIRES.
        </p>
      ) : (
        data.items.map((consulta) => (
          <div
            key={consulta.visitId}
            className="p-4 bg-subtle rounded-lg hover:bg-bg-paper transition-colors"
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <p className="font-semibold text-txt-body">
                  {formatFecha(consulta.date)}
                </p>
                <p className="text-sm text-txt-muted">
                  {consulta.doctorName ?? "Médico sin identificar"}
                </p>
              </div>
            </div>
            <div className="text-sm space-y-1">
              <p className="text-txt-body">
                <strong>Diagnóstico:</strong> {consulta.primaryDiagnosis}
                {consulta.cieCode ? (
                  <span className="text-txt-muted">
                    {" "}
                    ({consulta.cieCode}
                    {consulta.cieDescription ? ` - ${consulta.cieDescription}` : ""})
                  </span>
                ) : null}
              </p>
              {consulta.prescriptionItems.length > 0 ? (
                <p className="text-txt-muted">
                  <strong>Receta:</strong> {consulta.prescriptionItems.join(", ")}
                </p>
              ) : null}
              {consulta.finalNote ? (
                <p className="text-txt-muted mt-1">
                  <strong>Nota:</strong> {consulta.finalNote}
                </p>
              ) : null}
            </div>
            <ConsultationAddendaSection visitId={consulta.visitId} />
          </div>
        ))
      )}

      <LegacyConsultationHistorySection noExp={noExp} pkNum={pkNum} />
    </div>
  );
}
