import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen, within } from "@/test/utils";
import { AttendedTodayList } from "@features/consulta-medica/modules/atencion/components/AttendedTodayList";
import type { DoctorAttendedItem, DoctorAttendedPrescription } from "@api/types";

const rx = (overrides: Partial<DoctorAttendedPrescription> = {}): DoctorAttendedPrescription => ({
  folio: "RX-2026-31", medicationsCount: 2, hasControlled: false, authorization: null, printable: true,
  ...overrides,
});

const item = (overrides: Partial<DoctorAttendedItem> = {}): DoctorAttendedItem => ({
  visitId: 31, folio: "V-31", nombrePaciente: "PEREZ LOPEZ JUAN", noExp: "12345", pkNum: 0,
  attendedAt: "2026-11-13T16:10:00Z", prescription: rx(), ...overrides,
});

const row = (name: string) => screen.getByText(name).closest("li") as HTMLElement;

describe("Mi jornada: atendidas hoy", () => {
  it("imprime la receta lista para imprimir", async () => {
    const onPrint = vi.fn();
    const user = userEvent.setup();
    render(<AttendedTodayList items={[item()]} canPrint onPrint={onPrint} />);

    await user.click(within(row("PEREZ LOPEZ JUAN")).getByRole("button", { name: /Imprimir receta/ }));

    expect(onPrint).toHaveBeenCalledWith(31);
    expect(within(row("PEREZ LOPEZ JUAN")).getByText("RX-2026-31")).toBeInTheDocument();
  });

  it("pendiente de autorizacion: lo dice y no deja imprimir", () => {
    render(
      <AttendedTodayList
        items={[item({ prescription: rx({ printable: false, authorization: { status: "pendiente", rejectionReason: null } }) })]}
        canPrint
        onPrint={vi.fn()}
      />,
    );
    const li = row("PEREZ LOPEZ JUAN");
    expect(within(li).getByText(/Pendiente de autorización/)).toBeInTheDocument();
    expect(within(li).queryByRole("button", { name: /Imprimir receta/ })).toBeNull();
  });

  it("rechazada: muestra el motivo", () => {
    render(
      <AttendedTodayList
        items={[item({ prescription: rx({ printable: false, authorization: { status: "rechazada", rejectionReason: "Dosis excede" } }) })]}
        canPrint
        onPrint={vi.fn()}
      />,
    );
    expect(screen.getByText(/Rechazada/)).toBeInTheDocument();
    expect(screen.getByText("Dosis excede")).toBeInTheDocument();
  });

  it("sin receta y con controlado", () => {
    render(
      <AttendedTodayList
        items={[
          item({ visitId: 1, nombrePaciente: "SIN RECETA", prescription: null }),
          item({ visitId: 2, nombrePaciente: "CON CONTROLADO", prescription: rx({ hasControlled: true }) }),
        ]}
        canPrint
        onPrint={vi.fn()}
      />,
    );
    expect(within(row("SIN RECETA")).getByText("Sin receta")).toBeInTheDocument();
    expect(within(row("CON CONTROLADO")).getByText("(+ hoja de controlado)")).toBeInTheDocument();
  });

  it("sin permiso de impresion no ofrece imprimir", () => {
    render(<AttendedTodayList items={[item()]} canPrint={false} onPrint={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /Imprimir receta/ })).toBeNull();
  });

  it("lista vacia", () => {
    render(<AttendedTodayList items={[]} canPrint onPrint={vi.fn()} />);
    expect(screen.getByText(/Todavía no cerraste consultas hoy/)).toBeInTheDocument();
  });
});
