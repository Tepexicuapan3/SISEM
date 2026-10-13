import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { DisponibilidadView } from "@features/recepcion/modules/agenda/components/DisponibilidadView";
import { MedicoDisponibleCard } from "@features/recepcion/modules/agenda/components/RecepcionQuickCheckinDialog";
import {
  buildDoctorFilterOptions,
  SIN_USUARIO_HINT,
} from "@features/recepcion/modules/agenda/pages/RecepcionAgendaPage.helpers";
import type { MedicoDisponible, MedicoListItem } from "@api/types/medicos.types";

// IDs DIVERGENTES a propósito: No. Médico (512) != id de usuario (7).
const MEDICO_ID = 512;
const USUARIO_ID = 7;

vi.mock("@features/recepcion/modules/citas/components/SlotCalendar", () => ({
  SlotCalendar: ({
    medicoId,
    onSlotClick,
  }: {
    medicoId: number;
    onSlotClick: (fecha: string, slot: Record<string, unknown>) => void;
  }) => (
    <button
      type="button"
      onClick={() => onSlotClick("2026-10-14", { hora: "09:00", consultorioId: 3 })}
    >
      slot-medico-{medicoId}
    </button>
  ),
}));

vi.mock(
  "@features/recepcion/modules/agenda/components/DisponibilidadMedicoCard",
  () => ({ DisponibilidadMedicoCard: () => null }),
);

const medico = (over: Partial<MedicoListItem>): MedicoListItem =>
  ({
    id: MEDICO_ID,
    usuarioId: USUARIO_ID,
    nombreCompleto: "Dra. Divergente",
    centros: [],
    ...over,
  }) as unknown as MedicoListItem;

const renderView = (calMedicoId: number, allMedicos: MedicoListItem[], onOpen = vi.fn()) => {
  render(
    <DisponibilidadView
      centroOptions={[]}
      calCentroId={null}
      setCalCentroId={vi.fn()}
      calMedicoId={calMedicoId}
      setCalMedicoId={vi.fn()}
      calWeekStart="2026-10-12"
      setCalWeekStart={vi.fn()}
      medicoSearch=""
      setMedicoSearch={vi.fn()}
      disponibilidadMedicos={allMedicos}
      allMedicos={allMedicos}
      onOpenQuickCheckin={onOpen}
    />,
  );
  return onOpen;
};

describe("Recepción: espacios de identidad médico vs usuario", () => {
  beforeEach(() => vi.clearAllMocks());

  it("DisponibilidadView manda doctorId = usuarioId y la agenda usa medicoId", async () => {
    const user = userEvent.setup();
    const onOpen = renderView(MEDICO_ID, [medico({})]);

    await user.click(screen.getByRole("button", { name: `slot-medico-${MEDICO_ID}` }));

    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onOpen.mock.calls[0][0].doctorId).toBe(USUARIO_ID);
    expect(onOpen.mock.calls[0][0].doctorId).not.toBe(MEDICO_ID);
  });

  it("DisponibilidadView no abre check-in para un médico sin usuario y avisa", async () => {
    const user = userEvent.setup();
    const onOpen = renderView(MEDICO_ID, [medico({ usuarioId: null })]);

    expect(screen.getByRole("status")).toHaveTextContent(SIN_USUARIO_HINT);
    await user.click(screen.getByRole("button", { name: `slot-medico-${MEDICO_ID}` }));

    expect(onOpen).not.toHaveBeenCalled();
  });

  it("el filtro de médico usa usuarioId y excluye médicos sin usuario", () => {
    const options = buildDoctorFilterOptions([
      medico({}),
      medico({ id: 600, usuarioId: null, nombreCompleto: "Sin usuario" }),
    ]);

    expect(options).toEqual([{ id: USUARIO_ID, nombre: "Dra. Divergente" }]);

    // Una visita con doctorId (espacio usuario) coincide con la opción por usuarioId.
    const visit = { doctorId: USUARIO_ID };
    expect(options.some((o) => visit.doctorId === o.id)).toBe(true);
    expect(options.some((o) => o.id === MEDICO_ID)).toBe(false);
  });

  it("la tarjeta del check-in rápido deshabilita médicos sin usuario", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const base: MedicoDisponible = {
      medicoId: MEDICO_ID,
      usuarioId: null,
      nombreCompleto: "Dr. Sin Usuario",
      servicio: null,
      tipoMedico: "general",
      disponible: true,
    } as MedicoDisponible;

    const { rerender } = render(
      <MedicoDisponibleCard medico={base} selected={false} onSelect={onSelect} />,
    );

    const btn = screen.getByRole("button", { name: /Dr\. Sin Usuario/ });
    expect(btn).toBeDisabled();
    expect(screen.getByText(SIN_USUARIO_HINT)).toBeVisible();
    await user.click(btn);
    expect(onSelect).not.toHaveBeenCalled();

    rerender(
      <MedicoDisponibleCard
        medico={{ ...base, usuarioId: USUARIO_ID }}
        selected={false}
        onSelect={onSelect}
      />,
    );
    expect(screen.getByRole("button", { name: /Dr\. Sin Usuario/ })).toBeEnabled();
  });
});
