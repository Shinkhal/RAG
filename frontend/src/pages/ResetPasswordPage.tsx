import { useState, type FormEvent } from "react";
import { api, errorMessage } from "../api";
import { Logo } from "../components/Logo";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Alert } from "../components/Alert";

export function ResetPasswordPage() {
  const token = new URLSearchParams(location.search).get("token") ?? "";
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const password = String(data.get("password"));
    const confirm = String(data.get("confirm"));

    if (!token) {
      setError("Reset token is missing. Please request a new reset link.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const res = await api.resetPassword(token, password);
      setSuccessMessage(res.message);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-page__left">
        <div className="auth-page__left-content">
          <a href="/" className="auth-page__logo-link">
            <Logo size="lg" />
          </a>
          <h1 className="auth-page__hero-title">Choose a new password.</h1>
          <p className="auth-page__hero-desc">
            Use at least 8 characters to keep your workspace secure.
          </p>
        </div>
      </div>

      <div className="auth-page__right">
        <div className="auth-card">
          <div className="auth-card__header">
            <h2 className="auth-card__title">Reset password</h2>
            <p className="auth-card__subtitle">
              Enter your new password below.
            </p>
          </div>

          {successMessage ? (
            <div className="auth-card__form">
              <Alert type="success">{successMessage}</Alert>
              <a href="/login">
                <Button fullWidth size="lg">
                  Sign in with new password
                </Button>
              </a>
            </div>
          ) : !token ? (
            <div className="auth-card__form">
              <Alert>This reset link is invalid or incomplete.</Alert>
              <a href="/forgot-password">
                <Button variant="secondary" fullWidth size="lg">
                  Request a new reset link
                </Button>
              </a>
            </div>
          ) : (
            <form className="auth-card__form" onSubmit={submit}>
              <Input
                id="reset-password"
                name="password"
                type="password"
                label="New password"
                placeholder="Create a new password"
                autoComplete="new-password"
                required
                minLength={8}
                maxLength={128}
                hint="Must be at least 8 characters."
              />
              <Input
                id="reset-confirm"
                name="confirm"
                type="password"
                label="Confirm new password"
                placeholder="Re-enter your new password"
                autoComplete="new-password"
                required
                minLength={8}
                maxLength={128}
              />
              {error && <Alert>{error}</Alert>}
              <Button type="submit" loading={submitting} fullWidth size="lg">
                Reset password
              </Button>
            </form>
          )}

          <div className="auth-card__footer">
            <p>
              Back to <a href="/login">Sign in</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
