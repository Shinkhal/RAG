import { Logo } from "./Logo";
import { Button } from "./Button";
import type { Account } from "../api";

interface TopbarProps {
  account: Account | null | undefined;
  signingOut: boolean;
  onSignOut: () => void;
}

export function Topbar({ account, signingOut, onSignOut }: TopbarProps) {
  const displayName = account
    ? account.first_name || account.last_name
      ? `${account.first_name} ${account.last_name}`.trim()
      : account.email
    : "";
  const initials = account
    ? `${account.first_name.charAt(0)}${account.last_name.charAt(0)}`.toUpperCase() || account.email.charAt(0).toUpperCase()
    : "";

  return (
    <header className="topbar">
      <a className="topbar__brand" href="/">
        <Logo size="md" />
      </a>
      {account && (
        <div className="topbar__account">
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
