import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@shared/ui/card";
import { Label } from "@shared/ui/label";
import { Textarea } from "@shared/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@shared/ui/select";
import { portalCatalogosAPI, portalCitasAPI, portalNucleoAPI } from "@api/resources/portal.api";
import { ApiError } from "@api/utils/errors";

const hoyISO = () => new Date().toISOString().slice(0, 10);

export const PortalReservarCitaPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: nucleoData } = useQuery({
    queryKey: ["portal", "nucleo"],
    queryFn: () => portalNucleoAPI.get(),
  });

  const [miembroId, setMiembroId] = useState<string>("");
  const [centroId, setCentroId] = useState<string>("");
  const [consultorioId, setConsultorioId] = useState<string>("");
  const [fecha, setFecha] = useState<string>("");
  const [slotId, setSlotId] = useState<number | null>(null);
  const [motivo, setMotivo] = useState("");

  // Si solo hay un miembro (titular sin núcleo), lo pre-selecciona.
  const nucleo = nucleoData?.nucleo ?? [];
  const miembroSeleccionado = miembroId || (nucleo.length === 1 ? nucleo[0].miembroId : "");

  const { data: centrosData } = useQuery({
    queryKey: ["portal", "centros"],
    queryFn: () => portalCatalogosAPI.getCentros(),
  });

  const { data: consultoriosData } = useQuery({
    queryKey: ["portal", "consultorios", centroId],
    queryFn: () =>
      portalCatalogosAPI.getConsultorios(centroId ? Number(centroId) : undefined),
  });

  const { data: slotsData, isFetching: cargandoSlots } = useQuery({
    queryKey: ["portal", "slots", fecha, consultorioId],
    queryFn: () => portalCatalogosAPI.getSlots(fecha, Number(consultorioId)),
    enabled: Boolean(fecha) && Boolean(consultorioId),
  });

  const slotsDisponibles = useMemo(
    () => (slotsData?.slots ?? []).filter((s) => s.estado === "disponible"),
    [slotsData],
  );

  const reservarMutation = useMutation({
    mutationFn: () =>
      portalCitasAPI.reservar({
        miembroId: miembroSeleccionado,
        slotId: slotId as number,
        motivo: motivo.trim() || undefined,
      }),
    onSuccess: (data) => {
      toast.success(`Cita agendada — folio ${data.folio}`);
      queryClient.invalidateQueries({ queryKey: ["portal", "citas"] });
      navigate("/portal/mis-citas", { replace: true });
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : "No se pudo agendar la cita");
    },
  });

  const puedeReservar =
    Boolean(miembroSeleccionado) && Boolean(consultorioId) && Boolean(fecha) && slotId !== null;

  return (
    <div className="min-h-screen bg-app p-4 md:p-8">
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => navigate("/portal/mis-citas")}>
            <ArrowLeft className="mr-2 size-4" />
            Volver
          </Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Nueva Cita</CardTitle>
            <CardDescription>Elegí para quién, dónde y cuándo.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {nucleo.length > 1 && (
              <div className="space-y-1">
                <Label>¿Para quién es la cita?</Label>
                <Select value={miembroId} onValueChange={setMiembroId}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Elegí un integrante del núcleo familiar" />
                  </SelectTrigger>
                  <SelectContent>
                    {nucleo.map((m) => (
                      <SelectItem key={m.miembroId} value={m.miembroId}>
                        {m.nombreVisible}
                        {m.esMenor ? " (menor)" : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-1">
              <Label>Clínica</Label>
              <Select
                value={centroId}
                onValueChange={(v) => {
                  setCentroId(v);
                  setConsultorioId("");
                  setSlotId(null);
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Todas las clínicas" />
                </SelectTrigger>
                <SelectContent>
                  {(centrosData?.centros ?? []).map((c) => (
                    <SelectItem key={c.centroId} value={String(c.centroId)}>
                      {c.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label>Consultorio</Label>
              <Select
                value={consultorioId}
                onValueChange={(v) => {
                  setConsultorioId(v);
                  setSlotId(null);
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Elegí un consultorio" />
                </SelectTrigger>
                <SelectContent>
                  {(consultoriosData?.consultorios ?? []).map((c) => (
                    <SelectItem key={c.consultorioId} value={String(c.consultorioId)}>
                      #{c.numero} — {c.nombre}
                      {c.centroNombre ? ` (${c.centroNombre})` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label htmlFor="fecha">Fecha</Label>
              <input
                id="fecha"
                type="date"
                min={hoyISO()}
                value={fecha}
                onChange={(e) => {
                  setFecha(e.target.value);
                  setSlotId(null);
                }}
                disabled={!consultorioId}
                className="w-full h-9 rounded-xl border border-line-struct bg-transparent px-3 text-sm disabled:opacity-50"
              />
            </div>

            {fecha && consultorioId && (
              <div className="space-y-2">
                <Label>Horarios disponibles</Label>
                {cargandoSlots && (
                  <p className="text-sm text-txt-muted">Buscando horarios...</p>
                )}
                {!cargandoSlots && slotsDisponibles.length === 0 && (
                  <p className="text-sm text-txt-muted">
                    No hay horarios disponibles ese día para este consultorio.
                  </p>
                )}
                <div className="flex flex-wrap gap-2">
                  {slotsDisponibles.map((slot) => (
                    <button
                      key={slot.slotId}
                      type="button"
                      onClick={() => setSlotId(slot.slotId)}
                      className={[
                        "rounded-lg border px-3 py-2 text-sm transition-colors",
                        slotId === slot.slotId
                          ? "border-brand bg-brand/10 text-brand font-semibold"
                          : "border-line-struct hover:bg-subtle/40",
                      ].join(" ")}
                    >
                      {slot.hora}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="space-y-1">
              <Label htmlFor="motivo">Motivo (opcional)</Label>
              <Textarea
                id="motivo"
                value={motivo}
                onChange={(e) => setMotivo(e.target.value)}
                placeholder="Contanos brevemente el motivo de tu consulta"
                maxLength={255}
              />
            </div>

            <Button
              className="w-full"
              disabled={!puedeReservar || reservarMutation.isPending}
              onClick={() => reservarMutation.mutate()}
            >
              {reservarMutation.isPending && <Loader2 className="mr-2 size-4 animate-spin" />}
              Confirmar cita
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default PortalReservarCitaPage;
