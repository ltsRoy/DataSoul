/**
 * DataSoul Session Hook
 * ======================
 * Manages the active session ID and filename in sessionStorage.
 * Persists across page navigations within the same tab.
 */

"use client";

import { useState, useEffect, useCallback } from "react";

const SESSION_KEY = "datasoul_session_id";
const FILENAME_KEY = "datasoul_filename";

interface Session {
  sessionId: string | null;
  filename: string | null;
}

export function useSession() {
  const [session, setSessionState] = useState<Session>({
    sessionId: null,
    filename: null,
  });

  // Read from sessionStorage on mount
  useEffect(() => {
    const id = sessionStorage.getItem(SESSION_KEY);
    const filename = sessionStorage.getItem(FILENAME_KEY);
    if (id) {
      setSessionState({ sessionId: id, filename });
    }
  }, []);

  const setSession = useCallback((id: string, filename: string) => {
    sessionStorage.setItem(SESSION_KEY, id);
    sessionStorage.setItem(FILENAME_KEY, filename);
    setSessionState({ sessionId: id, filename });
  }, []);

  const clearSession = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(FILENAME_KEY);
    setSessionState({ sessionId: null, filename: null });
  }, []);

  return {
    sessionId: session.sessionId,
    filename: session.filename,
    setSession,
    clearSession,
  };
}

/**
 * Read session ID from URL search params or sessionStorage.
 * Useful for pages that receive the session via query params.
 */
export function getSessionFromParams(
  searchParams: URLSearchParams
): string | null {
  const fromUrl = searchParams.get("session");
  if (fromUrl) {
    // Also store in sessionStorage for subsequent pages
    sessionStorage.setItem(SESSION_KEY, fromUrl);
    return fromUrl;
  }
  return sessionStorage.getItem(SESSION_KEY);
}
