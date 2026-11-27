import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { Logo } from "./Logo";
import { Button } from "./Button";
import { api, type Account } from "../api";
import { applyTheme, getStoredTheme, storeTheme, type ThemePreference } from "../theme";

const THEME_CYCLE: ThemePreference[] = ["system", "light", "dark"];
const THEME_LABELS: Record<ThemePreference, string> = {
  system: "System",
  light: "Light",
  dark: "Dark",
};

interface TopbarProps {
  account: Account | null | undefined;
  signingOut: boolean;
  onSignOut: () => void;
  onAccountUpdate?: (account: Account) => void;
}

export function Topbar({ account, signingOut, onSignOut, onAccountUpdate }: TopbarProps) {
  const displayName = account
    ? account.first_name || account.last_name
      ? `${account.first_name} ${account.last_name}`.trim()
      : account.email
    : "";
  const initials = account
    ? `${account.first_name.charAt(0)}${account.last_name.charAt(0)}`.toUpperCase() || account.email.charAt(0).toUpperCase()
    : "";

  const [theme, setTheme] = useState<ThemePreference>(
    account?.preferences?.theme ?? getStoredTheme()
  );
  const [savingTheme, setSavingTheme] = useState(false);

  useEffect(() => {
    const preference = account?.preferences?.theme;
    if (preference) setTheme(preference);
  }, [account?.preferences?.theme]);

  async function cycleTheme() {
    if (savingTheme) return;
    const next = THEME_CYCLE[(THEME_CYCLE.indexOf(theme) + 1) % THEME_CYCLE.length];
    setTheme(next);
    storeTheme(next);
    applyTheme(next);
    if (!account) return;

    setSavingTheme(true);
    try {
      const updated = await api.updatePreferences({ theme: next });
      onAccountUpdate?.({ ...account, preferences: updated });
    } catch {
      // Keep the local choice even if the preference could not be saved.
    } finally {
      setSavingTheme(false);
    }
  }

  const ThemeIcon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;

  return (
    <header className="topbar">
      <a className="topbar__brand" href="/">
        <Logo size="md" />
      </a>
      {account && (
        <div className="topbar__account">
          <button
            type="button"
            className="topbar__theme"
            onClick={cycleTheme}
            disabled={savingTheme}
            aria-label={`Switch color mode (currently ${THEME_LABELS[theme]})`}
            title={`Color mode: ${THEME_LABELS[theme]}`}
          >
            <ThemeIcon size={17} aria-hidden="true" />
          </button>
          <a className="topbar__user" href="/profile" title="Account settings">
            <span className="topbar__avatar" aria-hidden="true">{initials}</span>
            <span className="topbar__email">{displayName}</span>
          </a>
          <Button
            variant="secondary"
            size="sm"
            loading={signingOut}
            onClick={onSignOut}
          >
            Sign out
          </Button>
        </div>
      )}
    </header>
  );
}
