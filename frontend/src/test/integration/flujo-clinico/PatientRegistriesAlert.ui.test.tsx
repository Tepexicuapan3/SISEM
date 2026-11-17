import { describe, expect, it } from "vitest";
import { render, screen } from "@/test/utils";
import type { PadronEnrollment } from "@api/types/padrones.types";
import { PatientRegistriesAlert } from "@features/padrones/components/PatientRegistriesAlert";

// Alerta de padrones en el expediente (docs/plans/padrones-alerta-expediente.md).
const enrollment = (overrides: Partial<PadronEnrollment>): PadronEnrollment => ({
  id: 1,
  registry: "cronicos",
  noExp: "40488",
  pkNum: 0,
  patientName: "PACIENTE PRUEBA",
  item: { id: "E11", code: "E11", description: "DIABETES TIPO 2", restricted: false },
  center: { id: 1, name: "Clínica 1" },
  enrolledOn: "2026-11-01",
  enrolledBy: null,
  notes: null,
  source: "manual",
  program: { code: "DIABETES", name: "Diabetes mellitus" },
  lastControl: null,
  status: "activo",
  discharge: null,
  ...overrides,
});

describe("PatientRegistriesAlert", () => {
  it("muestra crónicos con programa y discapacidades", () => {
    render(
      <PatientRegistriesAlert
        cronicos={[enrollment({})]}
        discapacidad={[enrollment({
          id: 2, registry: "discapacidad", program: undefined,
          item: { id: 3, code: "B1", description: "FUNCIONES MENTALES", restricted: false },
        })]}
      />,
    );
    expect(screen.getByText("Padrón de crónicos")).toBeInTheDocument();
    expect(screen.getByText("Diabetes mellitus · E11")).toBeInTheDocument();
    expect(screen.getByText("Padrón de discapacidad")).toBeInTheDocument();
    expect(screen.getByText("FUNCIONES MENTALES")).toBeInTheDocument();
  });

  it("marca el control vencido y no delata un CIE restringido", () => {
    render(
      <PatientRegistriesAlert
        cronicos={[
          enrollment({
            lastControl: { controlOn: "2026-01-01", status: "controlado", nextControlOn: "2026-04-01", overdue: true },
          }),
          enrollment({
            id: 2, program: null,
            item: { id: null, code: null, description: "Diagnóstico restringido", restricted: true },
          }),
        ]}
        discapacidad={[]}
      />,
    );
    expect(screen.getByText("Diabetes mellitus · E11 · control vencido")).toBeInTheDocument();
    expect(screen.getByText("Diagnóstico restringido")).toBeInTheDocument();
    expect(screen.queryByText("Padrón de discapacidad")).not.toBeInTheDocument();
  });

  it("sin inscripciones no muestra nada", () => {
    const { container } = render(<PatientRegistriesAlert cronicos={[]} discapacidad={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
