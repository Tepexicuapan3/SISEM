import { useState, type FormEvent } from "react";
import { FileText, Search, User } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@shared/ui/card";
import { Button } from "@shared/ui/button";
import { Input } from "@shared/ui/input";
import { ExpedienteLicenciasTab } from "@features/expedientes/components/ExpedienteLicenciasTab";
import { usePatientLookupHistorico } from "@features/recepcion/modules/checkin/queries/usePatientLookup";

/**
 * Consulta (solo lectura) del historial de incapacidades de un paciente por
 * numero de expediente, desde Recepcion. La creacion de incapacidades sigue
 * siendo exclusiva del medico (EmitirIncapacidadButton en consulta medica).
 *
 * pkNum siempre 0: la regla de negocio LEAVE_TITULAR_ONLY (ver
 * medical_leave_usecase.py) impide que un familiar reciba una incapacidad,
 * asi que no hace falta selector de miembro del nucleo familiar.
 */
export function RecepcionIncapacidadPage() {
  const [noExpInput, setNoExpInput] = useState("");
  const [noExpBuscado, setNoExpBuscado] = useState("");

  // Solo informativo: si este lookup falla por permisos (requiere
  // flow.visits.queue.read), el historial de incapacidades se muestra
  // igual mas abajo -- son 2 queries independientes.
  const { data: lookup, isFetching: isLookupFetching } =
    usePatientLookupHistorico(noExpBuscado);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNoExpBuscado(noExpInput.trim());
  };

  return (
    <section className="space-y-5 p-6">
      <header className="flex flex-col gap-3 rounded-xl border border-line-struct bg-paper p-5">
        <div className="inline-flex items-center gap-2 rounded-full border border-line-hairline bg-subtle px-3 py-1 text-xs font-medium text-txt-muted w-fit">
          <FileText className="size-3.5" />
          Consulta de incapacidades
        </div>
        <h1 className="text-2xl font-semibold text-txt-body">
          Historial de incapacidades
        </h1>
        <p className="max-w-xl text-sm text-txt-muted">
          Buscá por número de expediente para ver las incapacidades médicas
          registradas del titular. Solo el titular puede recibir
          incapacidades — no aplica a familiares.
        </p>
      </header>

      <Card>
        <CardContent className="pt-6">
          <form
            onSubmit={handleSubmit}
            className="flex flex-wrap items-end gap-3"
          >
            <div className="flex-1 min-w-[220px] space-y-1">
              <p className="text-xs font-medium text-txt-muted">
                Número de expediente
              </p>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-txt-muted pointer-events-none" />
                <Input
                  value={noExpInput}
                  onChange={(e) => setNoExpInput(e.target.value)}
                  placeholder="Ej. 12345"
                  className="pl-9 h-9"
                />
              </div>
            </div>
            <Button type="submit" size="sm">
              Buscar
            </Button>
          </form>

          {noExpBuscado && (
            <div className="mt-4 flex items-center gap-2 text-sm text-txt-muted">
              <User className="size-4" />
              {isLookupFetching ? (
                <span>Buscando paciente...</span>
              ) : lookup?.titular ? (
                <span>
                  <span className="font-semibold text-txt-body">
                    {lookup.titular.nombre}
                  </span>{" "}
                  · Exp. {noExpBuscado}
                </span>
              ) : (
                <span>
                  No se encontró información del titular para el expediente{" "}
                  {noExpBuscado} (el historial de incapacidades se muestra
                  igual si existe).
                </span>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Incapacidades</CardTitle>
          <CardDescription>
            Historial de licencias médicas del titular, más recientes primero
          </CardDescription>
        </CardHeader>
        <CardContent>
          {noExpBuscado ? (
            <ExpedienteLicenciasTab noExp={noExpBuscado} pkNum={0} />
          ) : (
            <p className="text-txt-muted text-sm py-12 text-center">
              Ingresá un número de expediente para ver su historial de
              incapacidades.
            </p>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

export default RecepcionIncapacidadPage;
