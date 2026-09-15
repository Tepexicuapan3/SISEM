/**
 * Vista Detallada de Expediente
 * Expediente clínico completo del paciente
 */

import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  FileText,
  User,
  AlertCircle,
  Heart,
  History,
  Pill,
  FileSignature,
  ClipboardList,
  CalendarOff,
  Smile,
  Grid3x3,
  Download,
  Edit,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@shared/ui/card";
import { Button } from "@shared/ui/button";
import { Badge } from "@shared/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@shared/ui/tabs";
import { Loader2 } from "lucide-react";
import { ExpedienteGeneralesTab } from "@features/expedientes/components/ExpedienteGeneralesTab";
import { ExpedienteEstomatologiaTab } from "@features/expedientes/components/ExpedienteEstomatologiaTab";
import { ExpedienteOdontogramaTab } from "@features/expedientes/components/ExpedienteOdontogramaTab";
import { ExpedienteHistorialTab } from "@features/expedientes/components/ExpedienteHistorialTab";
import { ExpedienteLicenciasTab } from "@features/expedientes/components/ExpedienteLicenciasTab";
import { ExpedienteEstudiosTab } from "@features/expedientes/components/ExpedienteEstudiosTab";
import { usePatientGeneralInfo } from "@features/expedientes/queries/usePatientGeneralInfo";

const SIN_DATO = "No disponible";

export const ExpedienteDetailPage = () => {
  // El folio (no_exp) SI es real -- viene de la URL /clinico/expedientes/:folio.
  const { folio: folioParam } = useParams<{ folio: string }>();
  const folioReal = folioParam ?? "";

  const { data: lookup, isLoading: isLoadingFicha } =
    usePatientGeneralInfo(folioReal);

  // pkNum=0 es el titular (trabajador); pkNum>0 es un derechohabiente
  // (familiar) -- mismo criterio que el legado (tp_paciente) y que ya usa
  // Recepcion (HistorialView.tsx). El historial clinico, consultas,
  // licencias, etc. de un derechohabiente son datos DISTINTOS a los del
  // titular, por eso hay que poder elegir a quien se esta consultando en
  // vez de fijarlo siempre en el titular.
  const [pkNum, setPkNum] = useState(0);

  // Si se navega de un expediente a otro, no arrastrar el derechohabiente
  // seleccionado del expediente anterior -- siempre arranca en el titular.
  useEffect(() => {
    setPkNum(0);
  }, [folioReal]);

  const members = useMemo(() => {
    if (!lookup) return [];
    return [
      ...(lookup.titular ? [lookup.titular] : []),
      ...lookup.dependientes,
    ];
  }, [lookup]);

  const selectedMember = members.find((m) => m.pkNum === pkNum);

  // Datos reales via /visits/patient-lookup (mismo endpoint que Recepcion).
  // CURP ya se expone (ver buscar_expediente.py / _build_member); sexo/tipo
  // de sangre/telefono/email/direccion siguen sin existir en ningun modelo
  // del backend hoy -- se muestran como SIN_DATO en vez de inventar un
  // valor. No hay fuente estructurada de alergias/padecimientos
  // cronicos/medicamentos habituales todavia (ClinicalHistory.allergies es
  // texto libre, no una lista), asi que esa tarjeta queda sin datos por ahora.
  const expediente = {
    folio: folioReal || SIN_DATO,
    paciente: selectedMember?.nombre ?? SIN_DATO,
    parentesco: pkNum === 0 ? "Titular" : (selectedMember?.parentesco ?? "Familiar"),
    curp: selectedMember?.curp ?? SIN_DATO,
    fecha_nacimiento: selectedMember?.fechaNac ?? SIN_DATO,
    edad: selectedMember?.edad ?? null,
    sexo: SIN_DATO,
    tipo_sangre: SIN_DATO,
    telefono: SIN_DATO,
    email: SIN_DATO,
    direccion: SIN_DATO,
    status: selectedMember?.estatus ?? SIN_DATO,
    alergias: [] as string[],
    padecimientos_cronicos: [] as string[],
    medicamentos_habituales: [] as string[],
  };

  return (
    <div className="min-h-screen bg-app p-6 md:p-10">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-brand/10 rounded-lg">
              <FileText className="size-6 text-brand" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-txt-body">
                Expediente Clínico
              </h1>
              <p className="text-txt-muted">Folio: {expediente.folio}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline">
              <Download className="mr-2 size-4" />
              Exportar
            </Button>
            <Button variant="outline">
              <Edit className="mr-2 size-4" />
              Editar
            </Button>
          </div>
        </div>

        {/* Datos del Paciente */}
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center gap-2">
              <User className="size-5 text-brand" />
              <CardTitle>Datos del Paciente</CardTitle>
              {isLoadingFicha && (
                <Loader2 className="size-4 animate-spin text-txt-muted" />
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-start gap-6">
              <div className="size-24 rounded-full bg-brand/10 flex items-center justify-center flex-shrink-0 overflow-hidden">
                {selectedMember?.foto ? (
                  <img
                    src={selectedMember.foto}
                    alt={`Foto de ${expediente.paciente}`}
                    className="size-full object-cover"
                  />
                ) : (
                  <User className="size-12 text-brand" />
                )}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <h2 className="text-2xl font-bold text-txt-body">
                    {expediente.paciente}
                  </h2>
                  <Badge variant={expediente.status === "activo" ? "stable" : "secondary"}>
                    {expediente.status}
                  </Badge>
                  <Badge variant="outline">{expediente.parentesco}</Badge>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2 text-sm">
                  <div>
                    <span className="text-txt-muted">CURP:</span>{" "}
                    <span className="font-mono text-txt-body">
                      {expediente.curp}
                    </span>
                  </div>
                  <div>
                    <span className="text-txt-muted">Folio:</span>{" "}
                    <span className="font-mono text-txt-body">
                      {expediente.folio}
                    </span>
                  </div>
                  <div>
                    <span className="text-txt-muted">Fecha de Nacimiento:</span>{" "}
                    <span className="text-txt-body">
                      {expediente.fecha_nacimiento}
                      {expediente.edad !== null ? ` (${expediente.edad} años)` : ""}
                    </span>
                  </div>
                  <div>
                    <span className="text-txt-muted">Sexo:</span>{" "}
                    <span className="text-txt-body">{expediente.sexo}</span>
                  </div>
                  <div>
                    <span className="text-txt-muted">Tipo de Sangre:</span>{" "}
                    <span className="text-txt-body">
                      {expediente.tipo_sangre}
                    </span>
                  </div>
                  <div>
                    <span className="text-txt-muted">Teléfono:</span>{" "}
                    <span className="text-txt-body">
                      {expediente.telefono}
                    </span>
                  </div>
                  <div className="md:col-span-2">
                    <span className="text-txt-muted">Email:</span>{" "}
                    <span className="text-txt-body">
                      {expediente.email}
                    </span>
                  </div>
                  <div className="md:col-span-2">
                    <span className="text-txt-muted">Dirección:</span>{" "}
                    <span className="text-txt-body">
                      {expediente.direccion}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Núcleo familiar — quién se está consultando (titular o derechohabiente) */}
        {members.length > 1 && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-base">Núcleo familiar</CardTitle>
              <CardDescription>
                El historial, consultas, licencias y estudios son distintos
                para cada miembro — elegí a quién estás consultando.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-3">
                {members.map((member) => {
                  const selected = member.pkNum === pkNum;
                  return (
                    <button
                      key={member.pkNum}
                      type="button"
                      onClick={() => setPkNum(member.pkNum)}
                      className={[
                        "flex items-start gap-3 rounded-xl border px-4 py-3 text-left transition-colors",
                        selected
                          ? "border-brand bg-brand/5"
                          : "border-line-struct hover:bg-subtle/40",
                      ].join(" ")}
                    >
                      <div
                        className={[
                          "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full border-2",
                          selected ? "border-brand bg-brand" : "border-line-struct",
                        ].join(" ")}
                      >
                        {selected && <span className="size-1.5 rounded-full bg-white" />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-txt-body">
                          {member.nombre}
                        </p>
                        <p className="text-xs text-txt-muted">
                          {member.pkNum === 0
                            ? "Titular"
                            : (member.parentesco ?? "Familiar")}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Alertas Médicas */}
        {(expediente.alergias.length > 0 ||
          expediente.padecimientos_cronicos.length > 0) && (
          <Card className="mb-6 border-status-alert/50 bg-status-alert/5">
            <CardHeader>
              <div className="flex items-center gap-2">
                <AlertCircle className="size-5 text-status-alert" />
                <CardTitle className="text-status-alert">
                  Alertas Médicas
                </CardTitle>
              </div>
              <CardDescription>
                Información crítica para atención médica
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {expediente.alergias.length > 0 && (
                <div>
                  <p className="text-sm font-semibold text-txt-body mb-2">
                    ⚠️ Alergias
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {expediente.alergias.map((alergia, idx) => (
                      <Badge key={idx} variant="critical">
                        {alergia}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {expediente.padecimientos_cronicos.length > 0 && (
                <div>
                  <p className="text-sm font-semibold text-txt-body mb-2">
                    🩺 Padecimientos Crónicos
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {expediente.padecimientos_cronicos.map((pad, idx) => (
                      <Badge key={idx} variant="alert">
                        {pad}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
              {expediente.medicamentos_habituales.length > 0 && (
                <div>
                  <p className="text-sm font-semibold text-txt-body mb-2">
                    💊 Medicamentos Habituales
                  </p>
                  <ul className="list-disc list-inside text-sm text-txt-muted space-y-1">
                    {expediente.medicamentos_habituales.map((med, idx) => (
                      <li key={idx}>{med}</li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Tabs de Información */}
        <Tabs defaultValue="generales" className="w-full">
          <TabsList className="grid w-full grid-cols-8">
            <TabsTrigger value="generales">
              <ClipboardList className="mr-2 size-4" />
              Generales
            </TabsTrigger>
            <TabsTrigger value="estomatologia">
              <Smile className="mr-2 size-4" />
              Estomatología
            </TabsTrigger>
            <TabsTrigger value="odontograma">
              <Grid3x3 className="mr-2 size-4" />
              Odontograma
            </TabsTrigger>
            <TabsTrigger value="historial">
              <History className="mr-2 size-4" />
              Historial
            </TabsTrigger>
            <TabsTrigger value="licencias">
              <CalendarOff className="mr-2 size-4" />
              Licencias
            </TabsTrigger>
            <TabsTrigger value="recetas">
              <Pill className="mr-2 size-4" />
              Recetas
            </TabsTrigger>
            <TabsTrigger value="estudios">
              <FileSignature className="mr-2 size-4" />
              Estudios
            </TabsTrigger>
            <TabsTrigger value="signos">
              <Heart className="mr-2 size-4" />
              Signos Vitales
            </TabsTrigger>
          </TabsList>

          <TabsContent value="generales" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Historia Clínica General</CardTitle>
                <CardDescription>
                  Datos sociodemográficos, antecedentes, exploración física y
                  manejo del paciente. Se captura de forma incremental — no
                  hace falta llenar todo de una vez.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {folioReal ? (
                  <ExpedienteGeneralesTab noExp={folioReal} pkNum={pkNum} />
                ) : (
                  <p className="text-txt-muted text-sm py-8 text-center">
                    No se encontró el número de expediente en la URL.
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="estomatologia" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Historia Clínica de Estomatología</CardTitle>
                <CardDescription>
                  Antecedentes heredofamiliares, patológicos, no
                  patológicos, quirúrgicos, traumáticos y alérgicos. Se
                  captura de forma incremental.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {folioReal ? (
                  <ExpedienteEstomatologiaTab noExp={folioReal} pkNum={pkNum} />
                ) : (
                  <p className="text-txt-muted text-sm py-8 text-center">
                    No se encontró el número de expediente en la URL.
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="odontograma" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Odontograma</CardTitle>
                <CardDescription>
                  Condición por pieza dental — hacé clic en un diente para
                  editarlo
                </CardDescription>
              </CardHeader>
              <CardContent>
                {folioReal ? (
                  <ExpedienteOdontogramaTab noExp={folioReal} pkNum={pkNum} />
                ) : (
                  <p className="text-txt-muted text-sm py-8 text-center">
                    No se encontró el número de expediente en la URL.
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="historial" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Historial de Consultas</CardTitle>
                <CardDescription>
                  Consultas médicas cerradas de este paciente, más recientes
                  primero
                </CardDescription>
              </CardHeader>
              <CardContent>
                {folioReal ? (
                  <ExpedienteHistorialTab noExp={folioReal} pkNum={pkNum} />
                ) : (
                  <p className="text-txt-muted text-sm py-8 text-center">
                    No se encontró el número de expediente en la URL.
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="licencias" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Licencias Médicas</CardTitle>
                <CardDescription>
                  Incapacidades emitidas a este paciente, más recientes
                  primero
                </CardDescription>
              </CardHeader>
              <CardContent>
                {folioReal ? (
                  <ExpedienteLicenciasTab noExp={folioReal} pkNum={pkNum} />
                ) : (
                  <p className="text-txt-muted text-sm py-8 text-center">
                    No se encontró el número de expediente en la URL.
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="recetas" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Recetas Médicas</CardTitle>
                <CardDescription>Historial de prescripciones</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-12 text-txt-muted">
                  <Pill className="size-12 mx-auto mb-4 opacity-50" />
                  <p>Módulo de recetas en desarrollo</p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="estudios" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Estudios y Laboratorios</CardTitle>
                <CardDescription>
                  Resultados de estudios clínicos, más recientes primero
                </CardDescription>
              </CardHeader>
              <CardContent>
                {folioReal ? (
                  <ExpedienteEstudiosTab noExp={folioReal} pkNum={pkNum} />
                ) : (
                  <p className="text-txt-muted text-sm py-8 text-center">
                    No se encontró el número de expediente en la URL.
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="signos" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Evolución de Signos Vitales</CardTitle>
                <CardDescription>
                  Gráficas y tendencias de signos vitales
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-center py-12 text-txt-muted">
                  <Heart className="size-12 mx-auto mb-4 opacity-50" />
                  <p>Gráficas de signos vitales en desarrollo</p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default ExpedienteDetailPage;
