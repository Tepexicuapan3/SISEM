import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@/test/utils";
import type { PadronEnrollment, PatientRegistriesResponse } from "@api/types/padrones.types";
import { PatientRegistryFlags } from "@features/padrones/components/PatientRegistryFlags";
import { usePatientRegistries } from "@features/padrones/queries/usePadrones";

// Distintivos junto al nombre del paciente (docs/plans/padrones-alerta-expediente.md).
vi.mock("@features/padrones/queries/usePadrones", () => ({ usePatientRegistries: vi.fn() }));

const enrollment = (overrides: Partial<PadronEnrollment>): PadronEnrollment => ({
  id: 1,
  registry: "cronicos",
  noExp: "40488",
  pkNum: 0,
  patientName: null,
  item: { id: "E11", code: "E11", description: "DIABETES TIPO 2", restricted: false },
  center: { id: 1, name: "Clínica 1" },
  enrolledOn: "2026-11-01",
  enrolledBy: null,
  notes: null,
  program: { code: "DIABETES", name: "Diabetes mellitus" },
  lastControl: null,
  status: "activo",
  discharge: null,
  ...overrides,
});

const withData = (data: PatientRegistriesResponse | undefined) =>
  vi.mocked(usePatientRegistries).mockReturnValue({ data } as ReturnType<typeof usePatientRegistries>);

describe("PatientRegistryFlags", () => {
  beforeEach(() => vi.clearAllMocks());

  it("un distintivo por padecimiento, el vencido resaltado, y la discapacidad", () => {
    withData({
      cronicos: [
        enrollment({}),
        enrollment({
          id: 2, item: { id: "I10", code: "I10", description: "HIPERTENSION", restricted: false },
          program: { code: "HIPERTENSION", name: "Hipertensión arterial" },
          lastControl: { controlOn: "2026-01-01", status: "controlado", nextControlOn: "2026-04-01", overdue: true },
        }),
      ],
      discapacidad: [enrollment({
        id: 3, registry: "discapacidad", program: undefined,
        item: { id: 3, code: "B1", description: "FUNCIONES MENTALES", restricted: false },
      })],
    });
    render(<PatientRegistryFlags noExp="40488" pkNum={1} />);

    expect(usePatientRegistries).toHaveBeenCalledWith("40488", 1);
    const flags = within(screen.getByRole("list", { name: "Padrones del paciente" })).getAllByRole("listitem");
    expect(flags.map((flag) => flag.textContent)).toEqual([
      "Crónico: Diabetes mellitus",
      "Crónico: Hipertensión arterial · control vencido",
      "Discapacidad: FUNCIONES MENTALES",
    ]);
    expect(flags[1]).toHaveAttribute("data-overdue", "true");
  });

  it("un CIE restringido solo dice Crónico", () => {
    withData({
      cronicos: [enrollment({
        program: null, item: { id: null, code: null, description: "Diagnóstico restringido", restricted: true },
      })],
      discapacidad: [],
    });
    render(<PatientRegistryFlags noExp="40488" pkNum={0} />);
    expect(screen.getByRole("listitem")).toHaveTextContent(/^Crónico$/);
  });

  it("sin padrones (o sin permiso) no ocupa lugar", () => {
    withData(undefined);
    const { container } = render(<PatientRegistryFlags noExp="40488" pkNum={0} />);
    expect(container).toBeEmptyDOMElement();
  });
});
