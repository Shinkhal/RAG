import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Topbar } from "./components/Topbar";
import { Alert } from "./components/Alert";
import { LandingPage } from "./pages/LandingPage";
import { AuthPage } from "./pages/AuthPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { ProfilePage } from "./pages/ProfilePage";
import { api, ApiError, errorMessage, type Account } from "./api";
import "./styles/global.css";
import "./styles/workspace.css";
import "./styles/profile.css";

type View = "loading" | "landing" | "auth" | "forgot" | "reset" | "workspace" | "profile";

function App() {
  const [account, setAccount] = useState<Account | null | undefined>();
  const [error, setError] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  const [view, setView] = useState<View>("loading");
  const path = location.pathname;

  useEffect(() => {
    const controller = new AbortController();

    if (path === "/" || path === "") {
      api
        .account(controller.signal)
        .then(() => {
          location.replace("/workspace");
        })
        .catch(() => {
          if (!controller.signal.aborted) {
            setAccount(null);
            setView("landing");
          }
        });
      return () => controller.abort();
    }

    if (
      path === "/login" ||
      path === "/signup" ||
      path === "/forgot-password" ||
      path === "/reset-password"
    ) {
      const targetView: View =
        path === "/forgot-password"
          ? "forgot"
          : path === "/reset-password"
          ? "reset"
          : "auth";
      api
        .account(controller.signal)
        .then(() => {
          location.replace("/workspace");
        })
        .catch((err) => {
          if (controller.signal.aborted) return;
          if (!(err instanceof ApiError && err.status === 401)) {
            setError(errorMessage(err));
          }
          setAccount(null);
          setView(targetView);
        });
      return () => controller.abort();
    }

    if (path === "/workspace" || path === "/profile") {
      api
        .account(controller.signal)
        .then((acc) => {
          setAccount(acc);
          setView(path === "/profile" ? "profile" : "workspace");
        })
        .catch((err) => {
          if (controller.signal.aborted) return;
          if (err instanceof ApiError && err.status === 401) {
            location.replace("/login");
          } else {
            setError(errorMessage(err));
            setView(path === "/profile" ? "profile" : "workspace");
          }
        });
      return () => controller.abort();
    }

    location.replace("/");
  }, [path]);

  async function signOut() {
    setSigningOut(true);
    setError("");
    try {
      await api.logout();
      location.replace("/");
    } catch (err) {
      setError(errorMessage(err));
      setSigningOut(false);
    }
  }

  if (view === "landing") {
    return <LandingPage />;
  }

  if (view === "auth") {
    return <AuthPage signup={path === "/signup"} />;
  }

  if (view === "forgot") {
    return <ForgotPasswordPage />;
  }

  if (view === "reset") {
    return <ResetPasswordPage />;
  }

  return (
    <>
      <Topbar account={account} signingOut={signingOut} onSignOut={signOut} />
      {error && <Alert className="app-banner">{error}</Alert>}
      {view === "loading" && (
        <div className="app-loading">
          <p className="text-muted" role="status">
            Loading workspace…
          </p>
        </div>
      )}
      {view === "workspace" && account && <WorkspacePage />}
      {view === "profile" && account && <ProfilePage account={account} onAccountUpdate={setAccount} />}
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
