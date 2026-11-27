import { useState, type FormEvent } from "react";
import { api, errorMessage } from "../api";
import { Logo } from "../components/Logo";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Alert } from "../components/Alert";
import { PASSWORD_POLICY_HINT, passwordPolicyError } from "../password";

export function AuthPage({ signup }: { signup: boolean }) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const title = signup ? "Create your account" : "Welcome back";
  const subtitle = signup
    ? "Start exploring your documents in minutes."
    : "Sign in to continue to your workspace.";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email")).trim();
    const password = String(data.get("password"));
    const first_name = signup ? String(data.get("first_name")).trim() : undefined;
    const last_name = signup ? String(data.get("last_name")).trim() : undefined;

    if (signup && (!first_name || !last_name)) {
      setError("Please enter your first and last name.");
      return;
    }

    if (signup) {
      const passwordProblem = passwordPolicyError(password);
      if (passwordProblem) {
        setError(passwordProblem);
        return;
      }
    }

    setSubmitting(true);
    setError("");
    try {
      await api.authenticate(signup ? "signup" : "login", {
        email,
        password,
        ...(signup ? { first_name, last_name } : {}),
      });
      location.replace("/workspace");
    } catch (error) {
      setError(errorMessage(error));
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
          <h1 className="auth-page__hero-title">
            Get answers from your documents.
          </h1>
          <p className="auth-page__hero-desc">
            Bring your PDFs and notes together, ask questions, and see the
            excerpts behind each sourced answer.
          </p>
          <div className="auth-page__example">
            <span className="auth-page__example-label">EXAMPLE QUESTION</span>
            <p>What are the main findings in this report?</p>
          </div>
          <div className="auth-page__testimonial">
            <p>"This tool saves me hours of manual document searching every week."</p>
            <small>— A happy user</small>
          </div>
        </div>
      </div>

      <div className="auth-page__right">
        <div className="auth-card">
          <div className="auth-card__header">
            <h2 className="auth-card__title">{title}</h2>
            <p className="auth-card__subtitle">{subtitle}</p>
          </div>

          <form className="auth-card__form" onSubmit={submit}>
            {signup && (
              <div className="auth-card__row">
                <Input
                  id="auth-first-name"
                  name="first_name"
                  type="text"
                  label="First name"
                  placeholder="Jane"
                  autoComplete="given-name"
                  required
                  maxLength={100}
                />
                <Input
                  id="auth-last-name"
                  name="last_name"
                  type="text"
                  label="Last name"
                  placeholder="Doe"
                  autoComplete="family-name"
                  required
                  maxLength={100}
                />
              </div>
            )}
            <Input
              id="auth-email"
              name="email"
              type="email"
              label="Email address"
              placeholder="you@example.com"
              autoComplete="email"
              required
              maxLength={254}
            />
            <Input
              id="auth-password"
              name="password"
              type="password"
              label="Password"
              placeholder={signup ? "Create a password" : "Enter your password"}
              autoComplete={signup ? "new-password" : "current-password"}
              required
              minLength={signup ? 8 : 1}
              maxLength={128}
              hint={signup ? PASSWORD_POLICY_HINT : undefined}
            />
            {!signup && (
              <div className="auth-card__forgot">
                <a href="/forgot-password">Forgot password?</a>
              </div>
            )}
            {error && <Alert>{error}</Alert>}
            <Button type="submit" loading={submitting} fullWidth size="lg">
              {signup ? "Create account" : "Sign in"}
            </Button>
          </form>

          <div className="auth-card__footer">
            <p>
              {signup
                ? "Already have an account?"
                : "New to RAG Workspace?"}{" "}
              <a href={signup ? "/login" : "/signup"}>
                {signup ? "Sign in" : "Create an account"}
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
