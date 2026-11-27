import { useEffect, useId, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  BookOpen,
  CalendarDays,
  Clock3,
  FileText,
  HardDrive,
  Layers,
  Mail,
  MessageSquare,
  Palette,
  ShieldCheck,
} from "lucide-react";
import {
  api,
  errorMessage,
  type Account,
  type Persona,
  type Profile,
  type ProfileDocument,
  type ProfilePreferences,
} from "../api";
import { Alert } from "../components/Alert";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { applyTheme, storeTheme } from "../theme";

const statusLabels: Record<string, string> = {
  processed: "Ready",
  processing: "Processing",
  queued: "Queued",
  failed: "Failed",
};

function formatDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function formatBytes(bytes?: number | null) {
  if (bytes == null || bytes < 0) return "—";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** index;
  return `${index === 0 || value >= 10 ? Math.round(value) : value.toFixed(1)} ${units[index]}`;
}

function StatTile({ icon, value, label }: { icon: React.ReactNode; value: string | number; label: string }) {
  return (
    <div className="profile-stat">
      <span className="profile-stat__icon" aria-hidden="true">{icon}</span>
      <div>
        <strong>{value}</strong>
        <span>{label}</span>
      </div>
    </div>
  );
}

function DocumentRow({ document }: { document: ProfileDocument }) {
  const meta = [
    document.session_title || "Untitled notebook",
    document.size_bytes != null ? formatBytes(document.size_bytes) : null,
    document.chunks_created ? `${document.chunks_created} chunks` : null,
    formatDate(document.created_at),
  ].filter(Boolean);

  return (
    <li className="profile-document">
      <span className="profile-document__icon" aria-hidden="true"><FileText size={18} /></span>
      <div className="profile-document__body">
        <strong title={document.name}>{document.name}</strong>
        <p className="profile-document__meta">{meta.join(" · ")}</p>
      </div>
      <div className="profile-document__side">
        <span className={`status-badge status-${document.status}`}>
          {statusLabels[document.status] ?? document.status}
        </span>
        <small>{document.mime_type?.split("/").pop()?.toUpperCase() ?? "File"}</small>
      </div>
    </li>
  );
}

export function ProfilePage({ account, onAccountUpdate }: {
  account: Account;
  onAccountUpdate: (account: Account) => void;
}) {
  const ids = useId();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [firstName, setFirstName] = useState(account.first_name);
  const [lastName, setLastName] = useState(account.last_name);
  const [profileStatus, setProfileStatus] = useState("");
  const [profileError, setProfileError] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);

  const [personas, setPersonas] = useState<Persona[]>([]);
  const [preferences, setPreferences] = useState<ProfilePreferences | null>(null);
  const [savedPreferences, setSavedPreferences] = useState<ProfilePreferences | null>(null);
  const [preferencesStatus, setPreferencesStatus] = useState("");
  const [preferencesError, setPreferencesError] = useState("");
  const [savingPreferences, setSavingPreferences] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    api.profile(controller.signal)
      .then(data => {
        if (controller.signal.aborted) return;
        setProfile(data);
        setFirstName(data.first_name);
        setLastName(data.last_name);
        setPreferences(data.preferences);
        setSavedPreferences(data.preferences);
        storeTheme(data.preferences.theme);
        applyTheme(data.preferences.theme);
        setLoadError("");
      })
      .catch(err => {
        if (!controller.signal.aborted) setLoadError(errorMessage(err));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    api.personas(controller.signal).then(setPersonas).catch(() => {
      // Personas are optional here; the preference can still be saved by ID.
    });
    return () => controller.abort();
  }, []);

  // Keep the selector in sync when the theme is changed from the topbar.
  useEffect(() => {
    const theme = account.preferences?.theme;
    if (!theme) return;
    setPreferences(current => (current && current.theme !== theme ? { ...current, theme } : current));
    setSavedPreferences(current => (current && current.theme !== theme ? { ...current, theme } : current));
  }, [account.preferences?.theme]);

  const fullName = profile?.full_name || `${account.first_name} ${account.last_name}`.trim() || account.email;
  const initials = `${account.first_name.charAt(0)}${account.last_name.charAt(0)}`.toUpperCase() || account.email.charAt(0).toUpperCase();
  const stats = profile?.stats;
  const documents = profile?.documents ?? [];
  const active = profile?.is_active ?? true;
  const createdAt = profile?.created_at ?? account.created_at;
  const preferencesDirty = Boolean(
    preferences && savedPreferences && JSON.stringify(preferences) !== JSON.stringify(savedPreferences)
  );

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
      setProfile(current => current ? {
        ...current,
        first_name: updated.first_name,
        last_name: updated.last_name,
        full_name: `${updated.first_name} ${updated.last_name}`.trim(),
      } : current);
      setProfileStatus("Profile updated.");
    } catch (err) {
      setProfileError(errorMessage(err));
    } finally {
      setSavingProfile(false);
    }
  }

  async function savePreferences(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!preferences) return;
    setSavingPreferences(true);
    setPreferencesError("");
    setPreferencesStatus("");
    try {
      const updated = await api.updatePreferences(preferences);
      setPreferences(updated);
      setSavedPreferences(updated);
      storeTheme(updated.theme);
      applyTheme(updated.theme);
      onAccountUpdate({ ...account, preferences: updated });
      setProfile(current => current ? { ...current, preferences: updated } : current);
      setPreferencesStatus("Preferences saved.");
    } catch (err) {
      if (savedPreferences) {
        setPreferences(current => current ? { ...current, theme: savedPreferences.theme } : current);
        applyTheme(savedPreferences.theme);
      }
      setPreferencesError(errorMessage(err));
    } finally {
      setSavingPreferences(false);
    }
  }

  return (
    <main className="profile-page">
      <header className="profile-page__header">
        <div>
          <a className="profile-back" href="/workspace"><ArrowLeft size={15} aria-hidden="true" />Back to workspace</a>
          <h1>Your profile</h1>
          <p className="text-muted">Your account, library, and workspace preferences in one place.</p>
        </div>
      </header>

      {loadError && <Alert>{loadError}</Alert>}

      <section className="profile-hero" aria-label="Account overview">
        <div className="profile-hero__identity">
          <div className="profile-avatar" aria-hidden="true">{initials}</div>
          <div className="profile-hero__copy">
            <span className="kicker">Account</span>
            <h2>{fullName}</h2>
            <p className="profile-email"><Mail size={14} aria-hidden="true" />{profile?.email ?? account.email}</p>
            <div className="profile-hero__badges">
              <span className={`profile-chip ${active ? "is-active" : "is-off"}`}>
                <ShieldCheck size={13} aria-hidden="true" />{active ? "Active" : "Inactive"}
              </span>
              <span className="profile-chip">
                <CalendarDays size={13} aria-hidden="true" />Joined {formatDate(createdAt)}
              </span>
              {profile?.last_login_at && (
                <span className="profile-chip">
                  <Clock3 size={13} aria-hidden="true" />Last login {formatDate(profile.last_login_at)}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="profile-hero__stats">
          <StatTile icon={<FileText size={17} />} value={stats?.total_documents ?? "—"} label="Documents" />
          <StatTile icon={<BookOpen size={17} />} value={stats?.total_sessions ?? "—"} label="Notebooks" />
          <StatTile icon={<MessageSquare size={17} />} value={stats?.total_queries ?? "—"} label="Questions" />
          <StatTile icon={<HardDrive size={17} />} value={formatBytes(stats?.storage_bytes)} label="Storage" />
        </div>
      </section>

      <div className="profile-grid">
        <section className="profile-card profile-details" aria-labelledby={`${ids}-details`}>
          <h2 id={`${ids}-details`}>Profile details</h2>
          <p className="profile-card__hint">This name appears in your workspace and on shared notebooks.</p>
          <form className="profile-form" onSubmit={saveProfile}>
            <div className="profile-form__row">
              <Input id={`${ids}-first`} label="First name" autoComplete="given-name" maxLength={100} required value={firstName} onChange={event => setFirstName(event.target.value)} />
              <Input id={`${ids}-last`} label="Last name" autoComplete="family-name" maxLength={100} required value={lastName} onChange={event => setLastName(event.target.value)} />
            </div>
            <Input id={`${ids}-email`} label="Email" type="email" value={profile?.email ?? account.email} readOnly hint="Email changes aren't available yet." />
            {profileError && <Alert>{profileError}</Alert>}
            {profileStatus && <Alert type="success">{profileStatus}</Alert>}
            <div className="profile-form__actions">
              <Button type="submit" loading={savingProfile}>Save changes</Button>
            </div>
          </form>
        </section>

        <section className="profile-card profile-preferences" aria-labelledby={`${ids}-preferences`}>
          <h2 id={`${ids}-preferences`} className="profile-card__title"><Palette size={17} aria-hidden="true" />Preferences</h2>
          <p className="profile-card__hint">Choose how your workspace looks and how we reach you.</p>
          {preferences ? (
            <form className="profile-form" onSubmit={savePreferences}>
              <div className="profile-form__row">
                <div className="input-group">
                  <label className="input-group__label" htmlFor={`${ids}-theme`}>Theme</label>
                  <select
                    id={`${ids}-theme`}
                    className="profile-select"
                    value={preferences.theme}
                    onChange={event => {
                      const theme = event.target.value as ProfilePreferences["theme"];
                      setPreferences({ ...preferences, theme });
                      applyTheme(theme);
                    }}
                  >
                    <option value="system">Match system</option>
                    <option value="light">Light</option>
                    <option value="dark">Dark</option>
                  </select>
                </div>
                <div className="input-group">
                  <label className="input-group__label" htmlFor={`${ids}-persona`}>Default persona</label>
                  <select
                    id={`${ids}-persona`}
                    className="profile-select"
                    value={preferences.default_persona_id ?? ""}
                    onChange={event => setPreferences({ ...preferences, default_persona_id: event.target.value || null })}
                  >
                    <option value="">No preference</option>
                    {personas.map(persona => (
                      <option key={persona.persona_id} value={persona.persona_id}>{persona.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <label className="profile-toggle">
                <span className="profile-toggle__copy">
                  <strong>Email notifications</strong>
                  <small>Product updates and activity about your notebooks.</small>
                </span>
                <input
                  type="checkbox"
                  checked={preferences.email_notifications}
                  onChange={event => setPreferences({ ...preferences, email_notifications: event.target.checked })}
                />
                <span className="profile-switch" aria-hidden="true"><span /></span>
              </label>

              {preferencesError && <Alert>{preferencesError}</Alert>}
              {preferencesStatus && <Alert type="success">{preferencesStatus}</Alert>}
              <div className="profile-form__actions">
                <Button type="submit" loading={savingPreferences} disabled={!preferencesDirty}>Save preferences</Button>
              </div>
            </form>
          ) : (
            <p className="profile-muted" role="status">Loading preferences…</p>
          )}
        </section>

        <section className="profile-card profile-usage" aria-labelledby={`${ids}-library`}>
          <h2 id={`${ids}-library`} className="profile-card__title"><Layers size={17} aria-hidden="true" />Library at a glance</h2>
          <ul className="profile-breakdown">
            {(["processed", "processing", "queued", "failed"] as const).map(status => (
              <li key={status}>
                <span className={`profile-dot profile-dot--${status}`} aria-hidden="true" />
                <span>{statusLabels[status]}</span>
                <strong>{stats?.documents_by_status[status] ?? 0}</strong>
              </li>
            ))}
          </ul>
          <div className="profile-breakdown__total">
            <span>Chunks indexed</span>
            <strong>{stats?.total_chunks ?? "—"}</strong>
          </div>
        </section>

        <section className="profile-card profile-documents" aria-labelledby={`${ids}-documents`}>
          <div className="profile-card__head">
            <div>
              <h2 id={`${ids}-documents`}>Uploaded documents</h2>
              <p className="profile-card__hint">Files you have added across your notebooks.</p>
            </div>
            {stats && <span className="profile-count">{stats.total_documents}</span>}
          </div>

          {loading ? (
            <p className="profile-muted" role="status">Loading your documents…</p>
          ) : documents.length === 0 ? (
            <div className="profile-empty">
              <span className="profile-empty__icon" aria-hidden="true"><FileText size={22} /></span>
              <strong>No documents yet</strong>
              <p>Upload a PDF, text, or markdown file in a notebook and it will appear here.</p>
              <a className="btn btn--secondary btn--sm" href="/workspace">Open workspace</a>
            </div>
          ) : (
            <>
              <ul className="profile-document-list">
                {documents.map(document => <DocumentRow key={document.id} document={document} />)}
              </ul>
              {stats && stats.total_documents > documents.length && (
                <p className="profile-muted">
                  Showing the {documents.length} most recent of {stats.total_documents} documents.
                </p>
              )}
            </>
          )}
        </section>
      </div>
    </main>
  );
}
