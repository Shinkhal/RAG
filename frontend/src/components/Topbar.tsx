import { Logo } from "./Logo";
import { Button } from "./Button";
import type { Account } from "../api";

interface TopbarProps {
  account: Account | null | undefined;
  signingOut: boolean;
  onSignOut: () => void;
}

export function Topbar({ account, signingOut, onSignOut }: TopbarProps) {
  return (
    <header className="topbar">
      <a className="topbar__brand" href="/">
        <Logo size="md" />
      </a>
      {account && (
        <div className="topbar__account">
          <span className="topbar__email" title={account.email}>
            {account.first_name || account.last_name
              ? `${account.first_name} ${account.last_name}`.trim()
              : account.email}
          </span>
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
