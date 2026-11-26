import { useId, useState, type FormEvent } from "react";
import { ArrowLeft, CalendarDays, Mail, ShieldCheck } from "lucide-react";
import { api, errorMessage, type Account } from "../api";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Input } from "../components/Input";

function formatDate(value?: string) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, { month: "long", day: "numeric", year: "numeric" }).format(date);
}

export function ProfilePage({ account, onAccountUpdate }: {
  account: Account;
  onAccountUpdate: (account: Account) => void;
}) {
  const ids = useId();
  const [firstName, setFirstName] = useState(account.first_name);
  const [lastName, setLastName] = useState(account.last_name);
  const [profileStatus, setProfileStatus] = useState("");
  const [profileError, setProfileError] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordStatus, setPasswordStatus] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);

  const fullName = `${account.first_name} ${account.last_name}`.trim() || account.email;
  const initials = `${account.first_name.charAt(0)}${account.last_name.charAt(0)}`.toUpperCase() || account.email.charAt(0).toUpperCase();

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const first = firstName.trim();
    const last = lastName.trim();
    if (!first || !last) {
      setProfileError("Enter your first and last name.");
      setProfileStatus("");
      return;
    }
    setSavingProfile(true);
    setProfileError("");
    setProfileStatus("");
    try {
      const updated = await api.updateProfile({ first_name: first, last_name: last });
      onAccountUpdate(updated);
      setFirstName(updated.first_name);
      setLastName(updated.last_name);
      setProfileStatus("Profile updated.");
    } catch (err) {
      setProfileError(errorMessage(err));
    } finally {
      setSavingProfile(false);
    }
  }

  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordError("");
    setPasswordStatus("");
    if (newPassword.length < 8) {
      setPasswordError("Use at least 8 characters for your new password.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("The new passwords do not match.");
      return;
    }
    setSavingPassword(true);
    try {
      const updated = await api.changePassword({ current_password: currentPassword, new_password: newPassword });
      onAccountUpdate(updated);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordStatus("Password updated. Other devices have been signed out.");
    } catch (err) {
      setPasswordError(errorMessage(err));
    } finally {
      setSavingPassword(false);
    }
  }

  return (
    <main className="profile-page">
      <header className="profile-page__header">
        <div>
          <a className="profile-back" href="/workspace"><ArrowLeft size={15} aria-hidden="true" />Back to workspace</a>
          <h1>Account settings</h1>
          <p className="text-muted">Manage your profile and sign-in details.</p>
        </div>
      </header>

      <div className="profile-grid">
        <aside className="profile-card profile-identity" aria-label="Account summary">
          <div className="profile-avatar" aria-hidden="true">{initials}</div>
          <div>
            <h2>{fullName}</h2>
            <p className="text-muted">{account.email}</p>
          </div>
          <div className="profile-meta">
            <div className="profile-meta__row"><Mail size={15} aria-hidden="true" /><span>Email</span><strong>{account.email}</strong></div>
            <div className="profile-meta__row"><CalendarDays size={15} aria-hidden="true" /><span>Member since</span><strong>{formatDate(account.created_at)}</strong></div>
            <div className="profile-meta__row"><ShieldCheck size={15} aria-hidden="true" /><span>Status</span><strong>Active</strong></div>
          </div>
        </aside>

        <div className="profile-forms">
          <section className="profile-card" aria-labelledby={`${ids}-profile`}>
            <h2 id={`${ids}-profile`}>Profile details</h2>
            <p className="profile-card__hint">This name appears in your workspace and on shared notebooks.</p>
            <form className="profile-form" onSubmit={saveProfile}>
              <div className="profile-form__row">
                <Input id={`${ids}-first`} label="First name" autoComplete="given-name" maxLength={100} required value={firstName} onChange={event => setFirstName(event.target.value)} />
                <Input id={`${ids}-last`} label="Last name" autoComplete="family-name" maxLength={100} required value={lastName} onChange={event => setLastName(event.target.value)} />
              </div>
              <Input id={`${ids}-email`} label="Email" type="email" value={account.email} readOnly hint="Email changes aren't available yet." />
              {profileError && <Alert>{profileError}</Alert>}
              {profileStatus && <Alert type="success">{profileStatus}</Alert>}
              <div className="profile-form__actions">
                <Button type="submit" loading={savingProfile}>Save changes</Button>
              </div>
            </form>
          </section>

          <section className="profile-card" aria-labelledby={`${ids}-security`}>
            <h2 id={`${ids}-security`}>Password</h2>
            <p className="profile-card__hint">Use at least 8 characters. Changing your password signs out other devices.</p>
            <form className="profile-form" onSubmit={savePassword}>
              <Input id={`${ids}-current`} label="Current password" type="password" autoComplete="current-password" required value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} />
              <div className="profile-form__row">
                <Input id={`${ids}-new`} label="New password" type="password" autoComplete="new-password" minLength={8} required value={newPassword} onChange={event => setNewPassword(event.target.value)} />
                <Input id={`${ids}-confirm`} label="Confirm new password" type="password" autoComplete="new-password" minLength={8} required value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} />
              </div>
              {passwordError && <Alert>{passwordError}</Alert>}
              {passwordStatus && <Alert type="success">{passwordStatus}</Alert>}
              <div className="profile-form__actions">
                <Button type="submit" loading={savingPassword}>Update password</Button>
              </div>
            </form>
          </section>
        </div>
      </div>
    </main>
  );
}
