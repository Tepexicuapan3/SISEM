import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Mail } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@shared/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@shared/ui/card";
import { Input } from "@shared/ui/input";
import { Label } from "@shared/ui/label";
import { OtpInput } from "@shared/ui/OtpInput";
import { portalAuthAPI } from "@api/resources/portal.api";
import { usePortalSessionStore } from "@app/state/portal/portalSessionStore";
import { ApiError } from "@api/utils/errors";

type Paso = "identidad" | "correo" | "codigo";

interface Identidad {
  noExp: string;
  nombreCompleto: string;
  fechaNacimiento: string;
}

export const PortalLoginPage = () => {
  const navigate = useNavigate();
  const setSession = usePortalSessionStore((s) => s.setSession);

  const [paso, setPaso] = useState<Paso>("identidad");
  const [identidad, setIdentidad] = useState<Identidad>({
    noExp: "",
    nombreCompleto: "",
    fechaNacimiento: "",
  });
  const [correo, setCorreo] = useState("");
  const [correoEnmascarado, setCorreoEnmascarado] = useState<string | null>(null);
  const [codigo, setCodigo] = useState("");

  const iniciarSesionMutation = useMutation({
    mutationFn: () => portalAuthAPI.iniciarSesion(identidad),
    onSuccess: (data) => {
      if (data.requiereCorreo) {
        setPaso("correo");
      } else {
        setCorreoEnmascarado(data.correoEnmascarado ?? null);
        setPaso("codigo");
      }
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : "No se pudo verificar tu identidad");
    },
  });

  const capturarCorreoMutation = useMutation({
    mutationFn: () => portalAuthAPI.capturarCorreo({ ...identidad, correo }),
    onSuccess: (data) => {
      setCorreoEnmascarado(data.correoEnmascarado);
      setPaso("codigo");
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : "No se pudo enviar el código");
    },
  });

  const verificarCodigoMutation = useMutation({
    mutationFn: () => portalAuthAPI.verificarCodigo({ ...identidad, codigo }),
    onSuccess: (data) => {
      setSession(data.accessToken, data.expiraEn);
      navigate("/portal/mis-citas", { replace: true });
    },
    onError: (error) => {
      toast.error(error instanceof ApiError ? error.message : "Código incorrecto");
      setCodigo("");
    },
  });

  const identidadCompleta =
    identidad.noExp.trim().length > 0 &&
    identidad.nombreCompleto.trim().length > 0 &&
    identidad.fechaNacimiento.length > 0;

  return (
    <div className="min-h-screen flex items-center justify-center bg-app p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Citas en Línea</CardTitle>
          <CardDescription>
            {paso === "identidad" && "Ingresá tus datos para iniciar sesión"}
            {paso === "correo" && "Es tu primera vez — necesitamos tu correo"}
            {paso === "codigo" && "Ingresá el código que te enviamos"}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {paso === "identidad" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                iniciarSesionMutation.mutate();
              }}
              className="space-y-4"
            >
              <div className="space-y-1">
                <Label htmlFor="noExp">Número de expediente</Label>
                <Input
                  id="noExp"
                  value={identidad.noExp}
                  onChange={(e) => setIdentidad((s) => ({ ...s, noExp: e.target.value }))}
                  placeholder="Ej. 33267"
                  required
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="nombreCompleto">Nombre completo</Label>
                <Input
                  id="nombreCompleto"
                  value={identidad.nombreCompleto}
                  onChange={(e) =>
                    setIdentidad((s) => ({ ...s, nombreCompleto: e.target.value }))
                  }
                  placeholder="Tal como aparece en tu expediente"
                  required
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="fechaNacimiento">Fecha de nacimiento</Label>
                <Input
                  id="fechaNacimiento"
                  type="date"
                  value={identidad.fechaNacimiento}
                  onChange={(e) =>
                    setIdentidad((s) => ({ ...s, fechaNacimiento: e.target.value }))
                  }
                  required
                />
              </div>
              <Button
                type="submit"
                className="w-full"
                disabled={!identidadCompleta || iniciarSesionMutation.isPending}
              >
                {iniciarSesionMutation.isPending && (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                )}
                Continuar
              </Button>
            </form>
          )}

          {paso === "correo" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                capturarCorreoMutation.mutate();
              }}
              className="space-y-4"
            >
              <div className="space-y-1">
                <Label htmlFor="correo">Correo electrónico</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-txt-muted" />
                  <Input
                    id="correo"
                    type="email"
                    value={correo}
                    onChange={(e) => setCorreo(e.target.value)}
                    placeholder="tu@correo.com"
                    className="pl-9"
                    required
                  />
                </div>
                <p className="text-xs text-txt-muted">
                  Te vamos a mandar un código para verificarlo.
                </p>
              </div>
              <Button
                type="submit"
                className="w-full"
                disabled={!correo || capturarCorreoMutation.isPending}
              >
                {capturarCorreoMutation.isPending && (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                )}
                Enviar código
              </Button>
            </form>
          )}

          {paso === "codigo" && (
            <div className="space-y-4">
              {correoEnmascarado && (
                <p className="text-sm text-txt-muted text-center">
                  Enviamos un código a <strong>{correoEnmascarado}</strong>
                </p>
              )}
              <OtpInput
                value={codigo}
                onChange={setCodigo}
                onComplete={() => verificarCodigoMutation.mutate()}
                disabled={verificarCodigoMutation.isPending}
                hasError={verificarCodigoMutation.isError}
              />
              <Button
                type="button"
                className="w-full"
                disabled={codigo.length !== 6 || verificarCodigoMutation.isPending}
                onClick={() => verificarCodigoMutation.mutate()}
              >
                {verificarCodigoMutation.isPending && (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                )}
                Verificar
              </Button>
              <Button
                type="button"
                variant="ghost"
                className="w-full"
                onClick={() => {
                  setCodigo("");
                  setPaso("identidad");
                }}
              >
                Volver a empezar
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default PortalLoginPage;
