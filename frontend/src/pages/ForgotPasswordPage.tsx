import { useState, type FormEvent } from "react";
import { api, errorMessage } from "../api";
import { Logo } from "../components/Logo";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Alert } from "../components/Alert";

export function ForgotPasswordPage() {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [sentMessage, setSentMessage] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = String(new FormData(event.currentTarget).get("email")).trim();
    if (!email) {
      setError("Enter your email address.");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const res = await api.forgotPassword(email);
      setSentMessage(res.message);
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
          <h1 className="auth-page__hero-title">Reset your password.</h1>
          <p className="auth-page__hero-desc">
            Enter the email address associated with your account and we'll send
            you a link to create a new password.
          </p>
        </div>
      </div>

      <div className="auth-page__right">
        <div className="auth-card">
          <div className="auth-card__header">
            <h2 className="auth-card__title">Forgot password</h2>
            <p className="auth-card__subtitle">
              We'll email you a reset link valid for 30 minutes.
            </p>
          </div>

          {sentMessage ? (
            <div className="auth-card__form">
              <Alert type="success">{sentMessage}</Alert>
              <a href="/login">
                <Button variant="secondary" fullWidth size="lg">
                  Back to sign in
                </Button>
              </a>
            </div>
          ) : (
            <form className="auth-card__form" onSubmit={submit}>
              <Input
                id="forgot-email"
                name="email"
                type="email"
                label="Email address"
                placeholder="you@example.com"
                autoComplete="email"
                required
                maxLength={254}
              />
              {error && <Alert>{error}</Alert>}
              <Button type="submit" loading={submitting} fullWidth size="lg">
                Send reset link
              </Button>
            </form>
          )}

          <div className="auth-card__footer">
            <p>
              Remembered your password? <a href="/login">Sign in</a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
