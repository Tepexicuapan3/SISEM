import axios, { AxiosError } from "axios";
import type { AxiosAdapter, AxiosResponse } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { emitSessionExpiredMock } = vi.hoisted(() => ({
  emitSessionExpiredMock: vi.fn(),
}));

vi.mock("@/domains/auth-access/adapters/session-events", () => ({
  emitSessionExpired: emitSessionExpiredMock,
  subscribeSessionExpired: vi.fn(() => () => {}),
}));

import { setupErrorInterceptor } from "@/infrastructure/api/interceptors/error.interceptor";
import {
  isSessionExpired,
  markSessionAlive,
} from "@/domains/auth-access/adapters/session-expiration";
import { ApiError } from "@/infrastructure/api/utils/errors";
import { queryClient } from "@app/config/query-client";
import { authKeys } from "@/domains/auth-access/state/auth.keys";

/**
 * Ciclo de vida de sesion contra un cliente Axios real con el interceptor
 * real. Las respuestas del backend se simulan con un adapter; /auth/refresh
 * sale por fetch (igual que en produccion) y se simula con un stub.
 */

type Responder = (url: string, attempt: number) => number | Promise<number>;

const setCsrfCookie = (value: string) => {
  document.cookie = `csrf_token=${value}; path=/`;
};

const clearCsrfCookie = () => {
  document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
};

const createClient = (respond: Responder) => {
  const calls: string[] = [];

  const adapter: AxiosAdapter = async (config) => {
    const url = config.url ?? "";
    calls.push(url);
    const attempt = calls.filter((call) => call === url).length;
    const status = await respond(url, attempt);

    const response: AxiosResponse = {
      data: status === 401 ? { code: "TOKEN_EXPIRED", message: "expirado" } : {},
      status,
      statusText: "",
      headers: {},
      config,
      request: {},
    };

    if (status >= 200 && status < 300) return response;
    throw new AxiosError("Request failed", "ERR_BAD_RESPONSE", config, {}, response);
  };

  const client = axios.create({ adapter, baseURL: "http://localhost/api/v1" });
  setupErrorInterceptor(client);

  return { client, calls };
};

const fetchMock = vi.fn();

/** Simula POST /auth/refresh; en 200 rota la cookie CSRF como el backend. */
const mockRefresh = (status: number, { delayMs = 0 } = {}) => {
  fetchMock.mockImplementation(async () => {
    if (delayMs) await new Promise((resolve) => setTimeout(resolve, delayMs));
    if (status === 200) setCsrfCookie(`csrf-rotated-${fetchMock.mock.calls.length}`);
    return { ok: status >= 200 && status < 300, status } as Response;
  });
};

const seedAuthenticatedCache = () => {
  queryClient.setQueryData(authKeys.session(), { id_usuario: 1 });
  queryClient.setQueryData(["expedientes", "list"], [{ id: 1 }]);
};

describe("auth session refresh lifecycle", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
    emitSessionExpiredMock.mockReset();
    markSessionAlive();
    queryClient.clear();
    setCsrfCookie("csrf-initial");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearCsrfCookie();
    queryClient.clear();
    markSessionAlive();
  });

  it("caso 1: access valido → /me 200 sin refresh", async () => {
    const { client } = createClient(() => 200);

    const response = await client.get("/auth/me");

    expect(response.status).toBe(200);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(emitSessionExpiredMock).not.toHaveBeenCalled();
  });

  it("caso 2: /me 401 → /refresh 200 → /me 200, el usuario sigue conectado", async () => {
    seedAuthenticatedCache();
    mockRefresh(200);
    const { client, calls } = createClient((url, attempt) =>
      url === "/auth/me" && attempt === 1 ? 401 : 200,
    );

    const response = await client.get("/auth/me");

    expect(response.status).toBe(200);
    expect(calls).toEqual(["/auth/me", "/auth/me"]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(emitSessionExpiredMock).not.toHaveBeenCalled();
    expect(isSessionExpired()).toBe(false);
    expect(queryClient.getQueryData(authKeys.session())).toEqual({ id_usuario: 1 });
  });

  it("caso 3: /me 401 → /refresh 401 → limpia sesion y notifica una vez", async () => {
    seedAuthenticatedCache();
    mockRefresh(401);
    const { client } = createClient(() => 401);

    await expect(client.get("/auth/me")).rejects.toMatchObject({ status: 401 });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(emitSessionExpiredMock).toHaveBeenCalledTimes(1);
    expect(isSessionExpired()).toBe(true);
    expect(queryClient.getQueryData(authKeys.session())).toBeNull();
    // Datos clinicos de la sesion anterior no quedan en memoria.
    expect(queryClient.getQueryData(["expedientes", "list"])).toBeUndefined();
  });

  it("caso 4: varios 401 simultaneos comparten un unico refresh", async () => {
    mockRefresh(200, { delayMs: 20 });
    const { client } = createClient((_url, attempt) => (attempt === 1 ? 401 : 200));

    const responses = await Promise.all([
      client.get("/auth/me"),
      client.get("/expedientes"),
      client.get("/auth/capabilities"),
    ]);

    expect(responses.map((response) => response.status)).toEqual([200, 200, 200]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(emitSessionExpiredMock).not.toHaveBeenCalled();
  });

  it("caso 4b: un 401 que llega despues de la rotacion reintenta sin otro refresh", async () => {
    mockRefresh(200);
    let releaseSlow: () => void = () => {};
    const slowGate = new Promise<void>((resolve) => {
      releaseSlow = resolve;
    });

    const { client } = createClient(async (url, attempt) => {
      if (url === "/expedientes" && attempt === 1) {
        await slowGate; // salio con la cookie vieja, responde tarde
        return 401;
      }
      return url === "/auth/me" && attempt === 1 ? 401 : 200;
    });

    const slowRequest = client.get("/expedientes");
    await client.get("/auth/me"); // dispara y completa el refresh
    releaseSlow();

    await expect(slowRequest).resolves.toMatchObject({ status: 200 });
    // Con BLACKLIST_AFTER_ROTATION un segundo refresh usaria un token revocado.
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("caso 5: /refresh 401 no se reintenta y bloquea requests autenticados posteriores", async () => {
    seedAuthenticatedCache();
    mockRefresh(401);
    const { client, calls } = createClient(() => 401);

    await expect(client.get("/auth/me")).rejects.toMatchObject({ status: 401 });
    await expect(client.get("/auth/me")).rejects.toMatchObject({ status: 401 });
    await expect(client.get("/expedientes")).rejects.toMatchObject({
      code: "SESSION_EXPIRED",
      status: 401,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(emitSessionExpiredMock).toHaveBeenCalledTimes(1);
    // /expedientes ni siquiera salio a la red.
    expect(calls).not.toContain("/expedientes");
  });

  it("caso 5b: si el reintento tras un refresh exitoso vuelve a dar 401, expira sin loop", async () => {
    seedAuthenticatedCache();
    mockRefresh(200);
    const { client, calls } = createClient(() => 401);

    await expect(client.get("/auth/me")).rejects.toMatchObject({ status: 401 });

    expect(calls).toEqual(["/auth/me", "/auth/me"]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(emitSessionExpiredMock).toHaveBeenCalledTimes(1);
  });

  it("caso 6a: /refresh 500 no cierra la sesion", async () => {
    seedAuthenticatedCache();
    mockRefresh(500);
    const { client } = createClient(() => 401);

    const error = await client.get("/auth/me").catch((err: unknown) => err);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "SERVICE_UNAVAILABLE", status: 503 });
    expect(emitSessionExpiredMock).not.toHaveBeenCalled();
    expect(isSessionExpired()).toBe(false);
    expect(queryClient.getQueryData(authKeys.session())).toEqual({ id_usuario: 1 });
  });

  it("caso 6b: error de red durante el refresh no cierra la sesion", async () => {
    seedAuthenticatedCache();
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const { client } = createClient(() => 401);

    await expect(client.get("/auth/me")).rejects.toMatchObject({ status: 503 });

    expect(emitSessionExpiredMock).not.toHaveBeenCalled();
    expect(isSessionExpired()).toBe(false);
  });

  it("caso 6c: un 500 de negocio no intenta refresh ni cierra sesion", async () => {
    seedAuthenticatedCache();
    const { client } = createClient(() => 500);

    await expect(client.get("/expedientes")).rejects.toMatchObject({ status: 500 });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(emitSessionExpiredMock).not.toHaveBeenCalled();
  });

  it("sin cookie CSRF ni usuario en cache: limpia en silencio (visita sin sesion)", async () => {
    clearCsrfCookie();
    const { client } = createClient(() => 401);

    await expect(client.get("/auth/me")).rejects.toMatchObject({ status: 401 });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(emitSessionExpiredMock).not.toHaveBeenCalled();
    expect(isSessionExpired()).toBe(true);
  });

  it("sin cookie CSRF pero con usuario en cache: expira y notifica (fail-closed)", async () => {
    clearCsrfCookie();
    seedAuthenticatedCache();
    const { client } = createClient(() => 401);

    await expect(client.get("/auth/me")).rejects.toMatchObject({ status: 401 });

    expect(emitSessionExpiredMock).toHaveBeenCalledTimes(1);
    expect(queryClient.getQueryData(authKeys.session())).toBeNull();
  });

  it("no intenta refresh en endpoints publicos de auth (ej. login con credenciales invalidas)", async () => {
    const { client } = createClient(() => 401);

    await expect(
      client.post("/auth/login", { username: "x", password: "y" }),
    ).rejects.toMatchObject({ status: 401 });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(emitSessionExpiredMock).not.toHaveBeenCalled();
  });

  it("un login exitoso libera el latch de sesion expirada", async () => {
    seedAuthenticatedCache();
    mockRefresh(401);
    const { client } = createClient((url) => (url === "/auth/login" ? 200 : 401));

    await expect(client.get("/auth/me")).rejects.toBeDefined();
    expect(isSessionExpired()).toBe(true);

    await client.post("/auth/login", { username: "x", password: "y" });

    expect(isSessionExpired()).toBe(false);
  });
});
