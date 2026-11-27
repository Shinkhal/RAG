export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "rag-theme";

const VALID_PREFERENCES: ThemePreference[] = ["light", "dark", "system"];

let activePreference: ThemePreference = "system";
let systemListenerAttached = false;

function systemPrefersDark(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference === "system") {
    return systemPrefersDark() ? "dark" : "light";
  }
  return preference;
}

function paint(theme: ResolvedTheme): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.dataset.themePreference = activePreference;
  root.style.colorScheme = theme;
}

function ensureSystemListener(): void {
  if (systemListenerAttached || typeof window === "undefined") return;
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (activePreference === "system") paint(resolveTheme("system"));
  });
  systemListenerAttached = true;
}

/** Apply a preference to the document and remember it for system changes. */
export function applyTheme(preference: ThemePreference): ResolvedTheme {
  activePreference = preference;
  const theme = resolveTheme(preference);
  ensureSystemListener();
  paint(theme);
  return theme;
}

export function getStoredTheme(): ThemePreference {
  if (typeof window === "undefined") return "system";
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (stored && VALID_PREFERENCES.includes(stored as ThemePreference)) {
      return stored as ThemePreference;
    }
  } catch {
    // Storage may be unavailable (private mode, hardened browser settings).
  }
  return "system";
}

export function storeTheme(preference: ThemePreference): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Ignore storage failures; the theme still applies for this session.
  }
}

/** Apply the locally remembered theme before the app renders. */
export function applyStoredTheme(): ResolvedTheme {
  return applyTheme(getStoredTheme());
}

/** Use the server-side preference once the account is available. */
export function syncThemeFromPreferences(
  preferences?: { theme?: ThemePreference } | null
): void {
  const preference = preferences?.theme;
  if (!preference || !VALID_PREFERENCES.includes(preference)) return;
  storeTheme(preference);
  applyTheme(preference);
}
