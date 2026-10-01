export const SESSION_EXPIRED_EVENT = "sisem:session-expired";
const SESSION_EXPIRED_STORAGE_KEY = "sisem:session-expired";
const SESSION_EXPIRED_CHANNEL = "sisem:session-expired";

// BroadcastChannel tambien entrega el mensaje a otras instancias del canal
// dentro de la MISMA pestaña; con este id la pestaña emisora lo ignora (ya
// recibio el CustomEvent local) y no se duplica aviso/redireccion.
const TAB_ID =
  typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

const hasBroadcastChannel = () => typeof BroadcastChannel !== "undefined";

export const emitSessionExpired = () => {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));

  if (hasBroadcastChannel()) {
    const channel = new BroadcastChannel(SESSION_EXPIRED_CHANNEL);
    channel.postMessage({ type: SESSION_EXPIRED_EVENT, sourceTabId: TAB_ID });
    channel.close();
    return;
  }

  // Fallback para navegadores sin BroadcastChannel.
  try {
    window.localStorage.setItem(
      SESSION_EXPIRED_STORAGE_KEY,
      Date.now().toString(),
    );
    window.localStorage.removeItem(SESSION_EXPIRED_STORAGE_KEY);
  } catch {
    // localStorage puede estar bloqueado en algunos entornos.
  }
};

export const subscribeSessionExpired = (handler: () => void) => {
  if (typeof window === "undefined") return () => {};

  window.addEventListener(SESSION_EXPIRED_EVENT, handler);

  if (hasBroadcastChannel()) {
    const channel = new BroadcastChannel(SESSION_EXPIRED_CHANNEL);
    channel.addEventListener("message", (event) => {
      if (
        event.data?.type === SESSION_EXPIRED_EVENT &&
        event.data?.sourceTabId !== TAB_ID
      ) {
        handler();
      }
    });

    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
      channel.close();
    };
  }

  const handleStorage = (event: StorageEvent) => {
    if (event.key === SESSION_EXPIRED_STORAGE_KEY && event.newValue) {
      handler();
    }
  };
  window.addEventListener("storage", handleStorage);

  return () => {
    window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
    window.removeEventListener("storage", handleStorage);
  };
};
