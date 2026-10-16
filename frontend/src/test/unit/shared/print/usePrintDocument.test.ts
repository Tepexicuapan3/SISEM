import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { toast } from "sonner";
import { impresionAPI } from "@api/resources/impresion.api";
import { usePrintDocument } from "@shared/hooks/usePrintDocument";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));
vi.mock("@api/resources/impresion.api", () => ({
  impresionAPI: { print: vi.fn() },
}));

const okResult = {
  blob: new Blob(["%PDF"], { type: "application/pdf" }),
  filename: "ficha_X.pdf",
  copy: 1,
  type: "ORIGINAL",
  logId: 9,
};

const blobError = (body: unknown) => ({
  response: { data: new Blob([JSON.stringify(body)], { type: "application/json" }) },
});

describe("usePrintDocument", () => {
  const fakeTab = { closed: false, close: vi.fn(), location: { href: "" } };

  beforeEach(() => {
    fakeTab.close.mockClear();
    fakeTab.location.href = "";
    vi.spyOn(window, "open").mockReturnValue(fakeTab as unknown as Window);
    URL.createObjectURL = vi.fn(() => "blob:mock");
    URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it("abre la pestania de forma sincrona y luego le asigna la URL del blob", async () => {
    let resolveApi!: (v: typeof okResult) => void;
    vi.mocked(impresionAPI.print).mockReturnValue(
      new Promise((r) => { resolveApi = r; }),
    );
    const { result } = renderHook(() => usePrintDocument("ficha"));

    let pending!: Promise<boolean>;
    act(() => { pending = result.current.print(5); });

    // window.open ocurrio antes de que la API resolviera
    expect(window.open).toHaveBeenCalledWith("", "_blank");
    expect(fakeTab.location.href).toBe("");
    expect(result.current.isPrinting).toBe(true);

    await act(async () => { resolveApi(okResult); await pending; });

    expect(impresionAPI.print).toHaveBeenCalledWith("ficha", 5);
    expect(fakeTab.location.href).toBe("blob:mock");
    expect(result.current.isPrinting).toBe(false);
  });

  it("ignora un segundo click mientras hay una impresion en curso", async () => {
    let resolveApi!: (v: typeof okResult) => void;
    vi.mocked(impresionAPI.print).mockReturnValue(
      new Promise((r) => { resolveApi = r; }),
    );
    const { result } = renderHook(() => usePrintDocument("ficha"));

    let first!: Promise<boolean>;
    act(() => { first = result.current.print(5); });
    let second = true;
    await act(async () => { second = await result.current.print(5); });
    expect(second).toBe(false);
    expect(impresionAPI.print).toHaveBeenCalledTimes(1);

    await act(async () => { resolveApi(okResult); await first; });
  });

  it("si el popup fue bloqueado descarga el PDF", async () => {
    vi.mocked(window.open).mockReturnValue(null);
    vi.mocked(impresionAPI.print).mockResolvedValue(okResult);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const { result } = renderHook(() => usePrintDocument("ficha"));

    await act(async () => { await result.current.print(5); });

    expect(click).toHaveBeenCalled();
  });

  it("parsea el Blob JSON de error, cierra la pestania y muestra toast", async () => {
    vi.mocked(impresionAPI.print).mockRejectedValue(
      blobError({ code: "DOCUMENT_NOT_PRINTABLE", message: "x", status: 409 }),
    );
    const { result } = renderHook(() => usePrintDocument("ficha"));

    let ok = true;
    await act(async () => { ok = await result.current.print(5); });

    expect(ok).toBe(false);
    expect(fakeTab.close).toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith(
      "Este documento todavía no se puede imprimir.",
    );
    expect(result.current.isPrinting).toBe(false);
  });

  it("usa el message del backend para codigos desconocidos y fallback si no es JSON", async () => {
    vi.mocked(impresionAPI.print).mockRejectedValueOnce(
      blobError({ code: "OTRO", message: "Mensaje del servidor" }),
    );
    const { result } = renderHook(() => usePrintDocument("ficha"));
    await act(async () => { await result.current.print(1); });
    expect(toast.error).toHaveBeenLastCalledWith("Mensaje del servidor");

    vi.mocked(impresionAPI.print).mockRejectedValueOnce(new Error("network"));
    await act(async () => { await result.current.print(1); });
    expect(toast.error).toHaveBeenLastCalledWith("No se pudo generar el PDF.");
  });
});
