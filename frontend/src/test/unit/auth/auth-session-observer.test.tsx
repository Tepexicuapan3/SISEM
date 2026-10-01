import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render } from "@testing-library/react";
import { SessionObserver } from "@/domains/auth-access/components/shared/SessionObserver";
import {
  applySessionExpiredState,
  expireSession,
} from "@/domains/auth-access/adapters/session-expiration";
import { subscribeSessionExpired } from "@/domains/auth-access/adapters/session-events";
import { authAPI } from "@api/resources/auth.api";
import { ApiError, ERROR_CODES } from "@api/utils/errors";
import { queryClient } from "@app/config/query-client";
import { authKeys } from "@/domains/auth-access/state/auth.keys";

const { navigateMock, toastErrorMock } = vi.hoisted(() => ({
  navigateMock: vi.fn(),
  toastErrorMock: vi.fn(),
}));
const applySessionExpiredStateMock = vi.mocked(applySessionExpiredState);
const expireSessionMock = vi.mocked(expireSession);
const subscribeSessionExpiredMock = vi.mocked(subscribeSessionExpired);

vi.mock("@api/resources/auth.api", () => ({
  authAPI: {
    verifyToken: vi.fn(),
  },
}));
const verifyTokenMock = vi.mocked(authAPI.verifyToken);

let currentLocation = { pathname: "/dashboard", search: "", hash: "" };
let sessionExpiredHandler: (() => void) | null = null;
let unsubscribeMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );

  return {
    ...actual,
    useNavigate: () => navigateMock,
    useLocation: () => currentLocation,
  };
});

vi.mock("sonner", () => ({
  toast: {
    error: toastErrorMock,
  },
}));

vi.mock("@/domains/auth-access/adapters/session-expiration", () => ({
  applySessionExpiredState: vi.fn(),
  expireSession: vi.fn(),
}));

vi.mock("@/domains/auth-access/adapters/session-events", () => ({
  subscribeSessionExpired: vi.fn((handler: () => void) => {
    sessionExpiredHandler = handler;
    return unsubscribeMock;
  }),
}));

describe("SessionObserver", () => {
  beforeEach(() => {
    currentLocation = { pathname: "/dashboard", search: "", hash: "" };
    sessionExpiredHandler = null;
    unsubscribeMock = vi.fn();
    navigateMock.mockReset();
    toastErrorMock.mockReset();
    applySessionExpiredStateMock.mockReset();
    expireSessionMock.mockReset();
    verifyTokenMock.mockReset();
    verifyTokenMock.mockResolvedValue({ valid: true });
    subscribeSessionExpiredMock.mockImplementation((handler: () => void) => {
      sessionExpiredHandler = handler;
      return unsubscribeMock;
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    queryClient.setQueryData(authKeys.session(), null);
  });

  it("fails closed by clearing auth state before redirecting to login", () => {
    render(<SessionObserver />);

    expect(sessionExpiredHandler).not.toBeNull();
    sessionExpiredHandler?.();

    expect(applySessionExpiredStateMock).toHaveBeenCalledTimes(1);
    expect(navigateMock).toHaveBeenCalledWith("/login", {
      replace: true,
      state: { from: currentLocation },
    });

    const clearOrder = applySessionExpiredStateMock.mock.invocationCallOrder[0];
    const navigateOrder = navigateMock.mock.invocationCallOrder[0];
    expect(clearOrder).toBeLessThan(navigateOrder);
  });

  it("shows the session-expired notice once with a stable toast id", () => {
    render(<SessionObserver />);

    sessionExpiredHandler?.();
    sessionExpiredHandler?.();

    expect(toastErrorMock).toHaveBeenCalledWith(
      "Tu sesión ha expirado. Por seguridad, inicia sesión nuevamente.",
      { id: "session-expired" },
    );
    // sonner deduplica por id: ambas llamadas comparten el mismo id.
    const ids = toastErrorMock.mock.calls.map(([, options]) => options?.id);
    expect(new Set(ids).size).toBe(1);
  });

  it("does not navigate or show toast when already on /login", () => {
    currentLocation = { pathname: "/login", search: "", hash: "" };
    render(<SessionObserver />);

    expect(sessionExpiredHandler).not.toBeNull();
    sessionExpiredHandler?.();

    expect(applySessionExpiredStateMock).toHaveBeenCalledTimes(1);
    expect(navigateMock).not.toHaveBeenCalled();
    expect(toastErrorMock).not.toHaveBeenCalled();
  });

  it("unsubscribes on unmount", () => {
    const { unmount } = render(<SessionObserver />);
    unmount();

    expect(unsubscribeMock).toHaveBeenCalledTimes(1);
  });

  describe("heartbeat de inactividad", () => {
    beforeEach(() => {
      vi.useFakeTimers();
      queryClient.setQueryData(authKeys.session(), { id_usuario: 1 });
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("renueva el TTL cuando hubo actividad real dentro de la ventana", () => {
      const { unmount } = render(<SessionObserver />);

      window.dispatchEvent(new Event("mousemove"));
      vi.advanceTimersByTime(60_000);

      expect(verifyTokenMock).toHaveBeenCalledTimes(1);
      unmount();
    });

    it("no renueva el TTL si no hubo actividad nueva en la ventana (deja expirar por inactividad)", async () => {
      const { unmount } = render(<SessionObserver />);

      // El montaje cuenta como actividad inicial: el primer tick renueva.
      await vi.advanceTimersByTimeAsync(60_000);
      expect(verifyTokenMock).toHaveBeenCalledTimes(1);

      // Sin ningun evento nuevo, el segundo tick NO debe renovar.
      await vi.advanceTimersByTimeAsync(60_000);
      expect(verifyTokenMock).toHaveBeenCalledTimes(1);

      unmount();
    });

    it("valida la sesion apenas el usuario vuelve de un periodo inactivo", async () => {
      const { unmount } = render(<SessionObserver />);

      await vi.advanceTimersByTimeAsync(60_000);
      await vi.advanceTimersByTimeAsync(60_000);
      expect(verifyTokenMock).toHaveBeenCalledTimes(1);

      window.dispatchEvent(new Event("mousemove"));
      await vi.advanceTimersByTimeAsync(0);

      expect(verifyTokenMock).toHaveBeenCalledTimes(2);
      unmount();
    });

    it("dispara la expiracion cuando verify confirma sesion invalida", async () => {
      verifyTokenMock.mockResolvedValue({ valid: false });
      const { unmount } = render(<SessionObserver />);

      await vi.advanceTimersByTimeAsync(60_000);

      expect(expireSessionMock).toHaveBeenCalledTimes(1);
      unmount();
    });

    it("no cierra sesion ante errores de red o 5xx del heartbeat", async () => {
      verifyTokenMock.mockRejectedValue(
        new ApiError(ERROR_CODES.SERVICE_UNAVAILABLE, "down", 503),
      );
      const { unmount } = render(<SessionObserver />);

      await vi.advanceTimersByTimeAsync(60_000);

      expect(verifyTokenMock).toHaveBeenCalledTimes(1);
      expect(expireSessionMock).not.toHaveBeenCalled();
      unmount();
    });

    it("deja de escuchar eventos de actividad al desmontar", () => {
      const { unmount } = render(<SessionObserver />);
      unmount();

      window.dispatchEvent(new Event("mousemove"));
      vi.advanceTimersByTime(60_000);

      expect(verifyTokenMock).not.toHaveBeenCalled();
    });
  });
});
