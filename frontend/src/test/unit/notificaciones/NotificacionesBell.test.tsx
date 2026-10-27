import { beforeEach, describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { render, screen } from "@/test/utils";
import { NotificacionesBell } from "@features/notificaciones/components/NotificacionesBell";

const marcarLeida = vi.fn();
const marcarTodas = vi.fn();
const navegar = vi.fn();

vi.mock("react-router-dom", async (original) => ({
  ...(await original<typeof import("react-router-dom")>()),
  useNavigate: () => navegar,
}));

vi.mock("@features/notificaciones/realtime/useNotificacionesRealtime", () => ({
  useNotificacionesRealtime: vi.fn(),
}));

vi.mock("@features/notificaciones/queries/useNotificaciones", () => ({
  useContadorNotificaciones: () => ({ data: { noLeidas: 3 } }),
  useNotificacionesList: () => ({
    data: {
      items: [
        {
          id: 11,
          categoria: "AUT_SOLICITADA",
          titulo: "Solicitud de autorización pendiente",
          cuerpo: "AUT-2026-000123 · Recetas · Clínica Norte",
          tipoRecurso: "solicitud_autorizacion",
          referenciaRecurso: "6f1c",
          urlAccion: "/clinico/autorizaciones/6f1c",
          prioridad: "NORMAL",
          fechaCreacion: "2026-10-27T10:00:00Z",
          fechaLectura: null,
        },
      ],
    },
    isLoading: false,
  }),
}));

vi.mock("@features/notificaciones/mutations/useNotificacionMutations", () => ({
  useMarcarLeida: () => ({ mutate: marcarLeida }),
  useMarcarTodasLeidas: () => ({ mutate: marcarTodas, isPending: false }),
}));

describe("NotificacionesBell", () => {
  beforeEach(() => {
    marcarLeida.mockReset();
    navegar.mockReset();
  });

  it("muestra cuantas no leidas hay", () => {
    render(<NotificacionesBell />);
    expect(screen.getByRole("button", { name: /3 notificaciones sin leer/i })).toBeVisible();
  });

  it("al abrir una notificacion la marca leida y navega a su enlace", async () => {
    const user = userEvent.setup();
    render(<NotificacionesBell />);

    await user.click(screen.getByRole("button", { name: /notificaciones sin leer/i }));
    await user.click(await screen.findByText("Solicitud de autorización pendiente"));

    expect(marcarLeida).toHaveBeenCalledWith(11);
    expect(navegar).toHaveBeenCalledWith("/clinico/autorizaciones/6f1c");
  });

  it("marcar todas como leidas", async () => {
    const user = userEvent.setup();
    render(<NotificacionesBell />);
    await user.click(screen.getByRole("button", { name: /notificaciones sin leer/i }));
    await user.click(await screen.findByRole("button", { name: /Marcar todas como leídas/i }));
    expect(marcarTodas).toHaveBeenCalled();
  });
});
