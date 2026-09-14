import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Calendar, Loader2, LogOut, MapPin, Plus, X } from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@shared/ui/alert-dialog";
import { Badge } from "@shared/ui/badge";
import { Button } from "@shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@shared/ui/card";
import { portalCitasAPI, portalNucleoAPI } from "@api/resources/portal.api";
import { usePortalSessionStore } from "@app/state/portal/portalSessionStore";
import { ApiError } from "@api/utils/errors";
import type { PortalEstatusCita } from "@api/types/portal.types";

const ESTATUS_LABEL: Record<PortalEstatusCita, string> = {
  agendada: "Agendada",
  confirmada: "Confirmada",
  atendida: "Atendida",
  cancelada: "Cancelada",
  no_asistio: "No asistió",
};

const ESTATUS_VARIANT: Record<
  PortalEstatusCita,
  "outline" | "stable" | "alert" | "secondary" | "critical"
> = {
  agendada: "outline",
  confirmada: "stable",
  atendida: "secondary",
  cancelada: "critical",
  no_asistio: "critical",
};

const formatFechaHora = (iso: string) =>
  new Date(iso).toLocaleString("es-MX", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });

export const PortalMisCitasPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const clearSession = usePortalSessionStore((s) => s.clearSession);
  const [folioACancelar, setFolioACancelar] = useState<string | null>(null);

  const { data: nucleoData } = useQuery({
    queryKey: ["portal", "nucleo"],
    queryFn: () => portalNucleoAPI.get(),
  });

  const {
    data: citasData,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["portal", "citas"],
    queryFn: () => portalCitasAPI.getAll(),
  });

  const cancelarMutation = useMutation({
    mutationFn: (folio: string) => portalCitasAPI.cancelar(folio, {}),
    onSuccess: () => {
      toast.success("Cita cancelada");
      queryClient.invalidateQueries({ queryKey: ["portal", "citas"] });
      setFolioACancelar(null);
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : "No se pudo cancelar la cita");
      setFolioACancelar(null);
    },
  });

  const cerrarSesion = () => {
    clearSession();
    navigate("/portal/login", { replace: true });
  };

  return (
    <div className="min-h-screen bg-app p-4 md:p-8">
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-txt-body">Mis Citas</h1>
            {nucleoData && (
              <p className="text-sm text-txt-muted">
                {nucleoData.nucleo.length > 1
                  ? `Núcleo familiar: ${nucleoData.nucleo.map((m) => m.nombreVisible).join(", ")}`
                  : nucleoData.nucleo[0]?.nombreVisible}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => navigate("/portal/reservar")}>
              <Plus className="mr-2 size-4" />
              Nueva cita
            </Button>
            <Button variant="outline" size="sm" onClick={cerrarSesion}>
              <LogOut className="mr-2 size-4" />
              Salir
            </Button>
          </div>
        </div>

        {isLoading && (
          <p className="text-txt-muted text-sm text-center py-12">Cargando tus citas...</p>
        )}

        {isError && (
          <p className="text-status-critical text-sm text-center py-12">
            No se pudieron cargar tus citas. Intentá de nuevo más tarde.
          </p>
        )}

        {citasData && citasData.citas.length === 0 && (
          <Card>
            <CardContent className="py-12 text-center text-txt-muted">
              <Calendar className="size-10 mx-auto mb-3 opacity-50" />
              <p>Todavía no tenés citas agendadas.</p>
            </CardContent>
          </Card>
        )}

        {citasData?.citas.map((cita) => (
          <Card key={cita.folio}>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base capitalize">
                    {formatFechaHora(cita.fechaHora)}
                  </CardTitle>
                  {cita.paraQuien && (
                    <CardDescription>Para: {cita.paraQuien}</CardDescription>
                  )}
                </div>
                <Badge variant={ESTATUS_VARIANT[cita.estatus]}>
                  {ESTATUS_LABEL[cita.estatus]}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-1 text-sm text-txt-muted">
              {cita.consultorioNombre && (
                <p className="flex items-center gap-2">
                  <MapPin className="size-4" />
                  {cita.consultorioNombre}
                </p>
              )}
              <p className="font-mono text-xs">Folio: {cita.folio}</p>
              {cita.cancelable && (
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2 text-status-critical hover:text-status-critical"
                  onClick={() => setFolioACancelar(cita.folio)}
                >
                  <X className="mr-2 size-4" />
                  Cancelar cita
                </Button>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <AlertDialog open={folioACancelar !== null} onOpenChange={(open) => !open && setFolioACancelar(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>¿Cancelar esta cita?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta acción no se puede deshacer. El horario quedará libre para otro paciente.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={cancelarMutation.isPending}>
              No, mantener
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={cancelarMutation.isPending}
              onClick={() => folioACancelar && cancelarMutation.mutate(folioACancelar)}
            >
              {cancelarMutation.isPending && <Loader2 className="mr-2 size-4 animate-spin" />}
              Sí, cancelar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default PortalMisCitasPage;
