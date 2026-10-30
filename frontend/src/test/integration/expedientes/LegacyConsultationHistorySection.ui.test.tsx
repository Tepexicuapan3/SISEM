import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { LegacyConsultationHistorySection } from "@features/expedientes/components/LegacyConsultationHistorySection";
import { useLegacyConsultationsHistory } from "@features/expedientes/queries/useLegacyConsultationsHistory";
import type {
  LegacyConsultationHistoryResponse,
  LegacyConsultationItem,
} from "@api/types/legacy-consultation.types";

vi.mock("@features/expedientes/queries/useLegacyConsultationsHistory", () => ({
  useLegacyConsultationsHistory: vi.fn(),
}));

const nota = (folio: string, date: string, sourceDb: string): LegacyConsultationItem => ({
  id: `${sourceDb}:7:${folio}`,
  legacyFolio: folio,
  sourceDb,
  date,
  time: "10:00",
  doctorName: "PEREZ LOPEZ ANA",
  clinicName: "CLINICA 7",
  serviceName: "SERVICIO ESPECIAL",
  consultationType: "NORMAL",
  specialtyName: null,
  subjective: "TOS DE 3 DIAS",
  objective: "FARINGE HIPEREMICA",
  assessment: "CUADRO VIRAL",
  plan: "REPOSO",
  diagnosticImpression: "FARINGITIS",
  diagnoses: [{ codigo: "J02", descripcion: "FARINGITIS AGUDA" }],
  primaryCie: { codigo: "J02", descripcion: "FARINGITIS AGUDA" },
  medications: [
    {
      name: "PARACETAMOL 500 MG",
      activeIngredient: "PARACETAMOL",
      quantity: 2,
      instructions: "1 CADA 8 HORAS",
      dispensedOn: "2025-03-01",
      cancelled: false,
    },
  ],
  addendumLegacy: "SE AGREGA INCAPACIDAD",
  sickLeaves: [{ days: 7, cancelled: false }],
  nextAppointment: "2025-06-04",
  morbidityLegacy: "2",
  referralStudies: [
    {
      type: "GABINETE",
      name: "RX ARTICULACION RODILLA (2 PROYECCIONES)",
      note: "AP Y LATERAL CON INTERPRETACION",
      cancelled: false,
    },
    { type: "HOSPITAL", name: "SANATORIO DURANGO — ATENCIÓN EN URGENCIAS", note: null, cancelled: false },
  ],
  statusLegacy: "A",
  weightLegacy: "70",
  heightLegacy: null,
  bloodPressureLegacy: "120/80",
  pulseLegacy: null,
  temperatureLegacy: null,
});

const respuesta = (
  items: LegacyConsultationItem[],
  extra: Partial<LegacyConsultationHistoryResponse> = {},
): LegacyConsultationHistoryResponse => ({
  items,
  total: items.length,
  totalCount: items.length,
  disponible: true,
  ...extra,
});

const inicial = respuesta([nota("CC25-1", "2025-03-01", "legado_actual")], {
  base: "legado_actual",
  bases: [
    { sourceDb: "legado_actual", total: 1, from: "2025-03-01", to: "2025-03-01" },
    { sourceDb: "legado_2016", total: 4, from: "2016-01-08", to: "2016-05-02" },
  ],
});
const de2016 = respuesta([nota("CC16-9", "2016-05-02", "legado_2016")], { base: "legado_2016" });

describe("LegacyConsultationHistorySection", () => {
  beforeEach(() => {
    vi.mocked(useLegacyConsultationsHistory).mockImplementation(
      (_noExp, _pkNum, _enabled, base) =>
        ({ data: base === "legado_2016" ? de2016 : inicial, isLoading: false }) as never,
    );
  });

  it("muestra la fecha sin correrla un día, el servicio y los medicamentos con su detalle", async () => {
    render(<LegacyConsultationHistorySection noExp="40041" pkNum={0} />);
    await userEvent.click(screen.getByRole("button", { name: /Historial previo a SIRES/ }));

    expect(screen.getByText(/1 de marzo de 2025/)).toBeInTheDocument();
    expect(screen.getByText("Dr(a). PEREZ LOPEZ ANA · CLINICA 7")).toBeInTheDocument();
    expect(screen.getByText("SERVICIO ESPECIAL · NORMAL")).toBeInTheDocument();
    expect(screen.getByText(/Subsecuente de la enfermedad/)).toBeInTheDocument();
    expect(screen.getByText("PARACETAMOL")).toBeInTheDocument();
    expect(screen.queryByText(/PARACETAMOL 500 MG/)).not.toBeInTheDocument();
    // El detalle aparece solo al pedirlo.
    expect(screen.queryByText(/1 CADA 8 HORAS/)).not.toBeInTheDocument();
    expect(screen.queryByText("CUADRO VIRAL")).not.toBeInTheDocument();
    // Sin abrir el detalle: objetivo antes del diagnóstico.
    expect(screen.getByText("FARINGE HIPEREMICA")).toBeInTheDocument();
    expect(screen.queryByText("TOS DE 3 DIAS")).not.toBeInTheDocument();
    expect(screen.queryByText(/RX ARTICULACION RODILLA/)).not.toBeInTheDocument();
    expect(screen.queryByText("SE AGREGA INCAPACIDAD")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ver detalle" }));
    expect(screen.getByText(/1 CADA 8 HORAS/)).toBeInTheDocument();
    expect(screen.queryByText(/Surtido|Sin surtir/)).not.toBeInTheDocument();
    expect(screen.getByText("TOS DE 3 DIAS")).toBeInTheDocument();
    expect(screen.getByText("CUADRO VIRAL")).toBeInTheDocument();
    expect(screen.getByText("SE AGREGA INCAPACIDAD")).toBeInTheDocument();
    expect(screen.getByText("Complemento:")).toBeInTheDocument();
    expect(screen.getByText(/4 de junio de 2025/)).toBeInTheDocument();
    expect(screen.getByText("FARINGE HIPEREMICA")).toBeInTheDocument();
    expect(screen.getByText("Pases de gabinete:")).toBeInTheDocument();
    expect(screen.getByText("Pases a hospital:")).toBeInTheDocument();
    // Signos vitales sin dato: la etiqueta se ve igual.
    expect(screen.getByText("Glucosa capilar:")).toBeInTheDocument();
    expect(
      screen.getByText("RX ARTICULACION RODILLA (2 PROYECCIONES) — AP Y LATERAL CON INTERPRETACION"),
    ).toBeInTheDocument();
    // Orden del detalle: signos vitales primero y los pases al final.
    const texto = document.body.textContent ?? "";
    const orden = ["Estatura", "Subjetivo", "Objetivo", "Análisis", "Plan", "Diagnóstico", "Próxima cita",
      "Complemento", "Medicamentos", "Días de incapacidad", "Pases de gabinete"];
    const posiciones = orden.map((titulo) => texto.indexOf(`${titulo}:`));
    expect(posiciones.every((posicion) => posicion >= 0)).toBe(true);
    expect([...posiciones].sort((a, b) => a - b)).toEqual(posiciones);
    expect(screen.getByText("Días de incapacidad:")).toBeInTheDocument();
    expect(screen.getByText("70 Kg")).toBeInTheDocument();
    expect(screen.getByText("120/80 mmHg")).toBeInTheDocument();
  });

  it("el selector de año trae las notas de esa base", async () => {
    render(<LegacyConsultationHistorySection noExp="40041" pkNum={0} />);
    await userEvent.click(screen.getByRole("button", { name: /Historial previo a SIRES/ }));

    await userEvent.selectOptions(screen.getByLabelText("Año del legado"), "legado_2016");

    expect(screen.getByText("CC16-9 · Base 2016")).toBeInTheDocument();
    expect(screen.queryByText(/CC25-1/)).not.toBeInTheDocument();
    expect(vi.mocked(useLegacyConsultationsHistory)).toHaveBeenLastCalledWith(
      "40041", 0, true, "legado_2016",
    );
  });
});
