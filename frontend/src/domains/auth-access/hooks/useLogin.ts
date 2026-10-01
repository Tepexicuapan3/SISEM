import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { authAPI } from "@api/resources/auth.api";
import type { LoginRequest } from "@api/types";
import { ApiError, ERROR_CODES } from "@api/utils/errors";
import {
  getAuthErrorMessage,
  loginErrorMessages,
} from "@/domains/auth-access/types/auth.messages";
import { invalidateAuthSessionAndCapabilities } from "@/domains/auth-access/adapters/auth-query-invalidation";
import { setAuthSession } from "@/domains/auth-access/adapters/auth-cache";
import { resolvePostLoginRedirect } from "@/domains/auth-access/adapters/login-redirect";

type LoginMutationVariables = LoginRequest & { rememberMe: boolean };

const normalizeLoginErrorCode = (code?: string): string | undefined => {
  if (!code) return undefined;
  if (code === ERROR_CODES.USER_NOT_FOUND) {
    return ERROR_CODES.INVALID_CREDENTIALS;
  }

  return code;
};

const getLoginMessage = (code?: string) =>
  getAuthErrorMessage(loginErrorMessages, normalizeLoginErrorCode(code));

/**
 * Mutation de login.
 *
 * Razon empresarial:
 * - Centraliza el flujo post-login (session + navegacion).
 * - Evita que cada pantalla gestione su propia sesion.
 */
export const useLogin = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      rememberMe,
      ...credentials
    }: LoginMutationVariables) => {
      void rememberMe;
      return authAPI.login(credentials);
    },
    onSuccess: (data, variables) => {
      if (variables.rememberMe) {
        localStorage.setItem("saved_username", variables.username);
      } else {
        localStorage.removeItem("saved_username");
      }

      setAuthSession(queryClient, data.user);
      invalidateAuthSessionAndCapabilities(queryClient);

      if (data.requiresOnboarding) {
        toast.info("Configuracion inicial requerida", {
          description: "Por favor completa tu perfil para continuar.",
        });
        navigate("/onboarding");
        return;
      }

      toast.success(`Bienvenido, ${data.user.fullName}`, {
        description: "Has iniciado sesion correctamente",
      });

      // Si la sesion expiro estando en una ruta, volvemos ahi.
      const landingRoute =
        resolvePostLoginRedirect(location.state) ||
        data.user.landingRoute ||
        "/dashboard";
      navigate(landingRoute);
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const normalizedCode = normalizeLoginErrorCode(error.code);

        if (error.code === ERROR_CODES.RATE_LIMIT_EXCEEDED) {
          toast.error("Acceso bloqueado temporalmente", {
            description: getLoginMessage(error.code) || error.message,
            duration: 6000,
          });
          return;
        }

        const description =
          getLoginMessage(normalizedCode) ||
          error.message ||
          "Error al iniciar sesion";
        toast.error("Error de autenticacion", { description });
        return;
      }

      toast.error("Error de autenticacion", {
        description: "Error al iniciar sesion",
      });
    },
  });
};
