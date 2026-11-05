import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { ExpedienteHistorialTab } from "@features/expedientes/components/ExpedienteHistorialTab";
import { usePermissionDependencies } from "@/domains/auth-access/hooks/usePermissionDependencies";
import { usePatientConsultationsHistory } from "@features/expedientes/queries/usePatientConsultationsHistory";
import type { PatientConsultationHistoryItem } from "@api/types";

vi.mock("@/domains/auth-access/hooks/usePermissionDependencies", () => ({
  usePermissionDependencies: vi.fn(),
}));
vi.mock("@features/expedientes/queries/usePatientConsultationsHistory", () => ({
  usePatientConsultationsHistory: vi.fn(),
}));
vi.mock("@features/expedientes/components/ConsultationAddendaSection", () => ({
  ConsultationAddendaSection: () => null,
}));
vi.mock("@features/expedientes/components/LegacyConsultationHistorySection", () => ({
  LegacyConsultationHistorySection: () => null,
}));
vi.mock("@features/expedientes/components/CancelarNotaDialog", () => ({
  CancelarNotaDialog: ({ open, visitId }: { open: boolean; visitId: number }) =>
    open ? <div data-testid="cancelar-dialog">visit {visitId}</div> : null,
}));

const buildItem = (
  visitId: number,
  visitStatus: string,
  overrides: Partial<PatientConsultationHistoryItem> = {},
): PatientConsultationHistoryItem => ({
  visitId,
  visitStatus,
  date: "2026-10-01T10:00:00Z",
  doctorId: 1,
  doctorName: "Dra. Prueba",
  serviceType: "medicina_general",
  primaryDiagnosis: "Faringitis",
  cieCode: "J02",
  cieDescription: "Faringitis aguda",
  finalNote: "ok",
  prescriptionItems: [],
  prescriptionMedications: [],
  restricted: false,
  ...overrides,
});

function setup({
  capability,
  items,
}: {
  capability: boolean;
  items: PatientConsultationHistoryItem[];
}) {
  const hasCapability = vi.fn(() => capability);
  vi.mocked(usePermissionDependencies).mockReturnValue({
    hasCapability,
  } as unknown as ReturnType<typeof usePermissionDependencies>);
  vi.mocked(usePatientConsultationsHistory).mockReturnValue({
    data: { items, total: items.length, redactedVisitIds: [] },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof usePatientConsultationsHistory>);
  return { hasCapability };
}

describe("ExpedienteHistorialTab - cancelar nota (S40/S41)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("consulta la capability clinico.notas.cancel con fallback al permiso crudo", () => {
    const { hasCapability } = setup({ capability: true, items: [buildItem(1, "cerrada")] });
    render(<ExpedienteHistorialTab noExp="100" />);
    expect(hasCapability).toHaveBeenCalledWith("clinico.notas.cancel", {
      allOf: ["clinico:notas:cancel"],
    });
  });

  it("muestra el boton Cancelar nota solo en notas cerradas cuando hay capability", () => {
    setup({
      capability: true,
      items: [buildItem(1, "cerrada"), buildItem(2, "cancelada")],
    });
    render(<ExpedienteHistorialTab noExp="100" />);
    expect(screen.getAllByRole("button", { name: "Cancelar nota" })).toHaveLength(1);
  });

  it("no muestra el boton sin capability aunque la nota este cerrada", () => {
    setup({ capability: false, items: [buildItem(1, "cerrada")] });
    render(<ExpedienteHistorialTab noExp="100" />);
    expect(screen.queryByRole("button", { name: "Cancelar nota" })).toBeNull();
  });

  it("muestra el badge Cancelada y oculta el boton en notas canceladas", () => {
    setup({ capability: true, items: [buildItem(2, "cancelada")] });
    render(<ExpedienteHistorialTab noExp="100" />);
    expect(screen.getByText("Cancelada")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancelar nota" })).toBeNull();
  });

  it("muestra el badge Cancelada tambien sin capability (es informativo)", () => {
    setup({ capability: false, items: [buildItem(2, "cancelada")] });
    render(<ExpedienteHistorialTab noExp="100" />);
    expect(screen.getByText("Cancelada")).toBeInTheDocument();
  });

  it("abre el dialogo con el visitId de la nota elegida", async () => {
    setup({ capability: true, items: [buildItem(7, "cerrada")] });
    render(<ExpedienteHistorialTab noExp="100" />);
    expect(screen.queryByTestId("cancelar-dialog")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Cancelar nota" }));
    expect(screen.getByTestId("cancelar-dialog")).toHaveTextContent("visit 7");
  });
});

describe("ExpedienteHistorialTab - imprimir receta", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const printButton = () => screen.queryByRole("button", { name: "Imprimir receta" });

  it("muestra el boton con medicamentos aunque no haya indicaciones libres", () => {
    setup({
      capability: true,
      items: [buildItem(1, "cerrada", { prescriptionMedications: ["Paracetamol 500mg"] })],
    });
    render(<ExpedienteHistorialTab noExp="100" />);
    expect(printButton()).toBeInTheDocument();
  });

  it("no muestra el boton si solo hay indicaciones libres (la receta daria 409)", () => {
    setup({
      capability: true,
      items: [buildItem(1, "cerrada", { prescriptionItems: ["Tomar liquidos"] })],
    });
    render(<ExpedienteHistorialTab noExp="100" />);
    expect(printButton()).toBeNull();
  });

  it("no muestra el boton si la nota esta cancelada", () => {
    setup({
      capability: true,
      items: [buildItem(1, "cancelada", { prescriptionMedications: ["Paracetamol 500mg"] })],
    });
    render(<ExpedienteHistorialTab noExp="100" />);
    expect(printButton()).toBeNull();
  });

  it("lista los medicamentos y aparte las indicaciones", () => {
    setup({
      capability: true,
      items: [
        buildItem(1, "cerrada", {
          prescriptionMedications: ["Paracetamol 500mg", "Ibuprofeno 400mg"],
          prescriptionItems: ["Tomar liquidos"],
        }),
      ],
    });
    render(<ExpedienteHistorialTab noExp="100" />);
    expect(screen.getByText(/Paracetamol 500mg, Ibuprofeno 400mg/)).toBeInTheDocument();
    expect(screen.getByText(/Tomar liquidos/)).toBeInTheDocument();
  });
});
