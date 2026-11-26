import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { AuthPage } from "./AuthPage";
import { Workspace } from "./Workspace";
import { api, ApiError, errorMessage, type Account } from "./api";
import "./workspace.css";

function App() {
  const [account, setAccount] = useState<Account | null | undefined>();
  const [error, setError] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  const path = location.pathname;

  useEffect(() => {
    const controller = new AbortController();
    api.account(controller.signal).then((account) => {
      if (path === "/workspace") setAccount(account);
      else location.replace("/workspace");
    }).catch((error) => {
      if (controller.signal.aborted) return;
      if (error instanceof ApiError && error.status === 401) {
        if (path === "/login" || path === "/signup") setAccount(null);
        else location.replace("/login");
      } else {
        setError(errorMessage(error));
      }
    });
    return () => controller.abort();
  }, [path]);

  async function signOut() {
    setSigningOut(true);
    setError("");
    try {
      await api.logout();
      location.replace("/login");
    } catch (error) {
      setError(errorMessage(error));
      setSigningOut(false);
    }
  }

  return (
    <>
      <header className="topbar">
        <a className="brand" href="/workspace"><span className="mark" aria-hidden="true">▤</span> RAG Workspace</a>
        {account && (
          <div className="account"><span id="email">{account.email}</span>
            <button className="secondary" disabled={signingOut} onClick={signOut}>Sign out</button>
          </div>
        )}
      </header>
      {error && <p className="error banner" role="alert">{error}</p>}
      {account === undefined && !error && <p className="boot" role="status">Loading workspace…</p>}
      {account === null && <AuthPage signup={path === "/signup"} />}
      {account && <Workspace />}
    </>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
