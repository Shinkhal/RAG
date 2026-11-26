import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { api, errorMessage, type Answer, type Notebook, type SourceDocument, type Turn } from "./api";

const statuses: Record<string, string> = {
  processed: "Ready", failed: "Processing failed", queued: "Queued", processing: "Processing…",
};
const nameOf = (notebook: Notebook) => notebook.title || "Untitled notebook";

function Empty({ title, description }: { title: string; description?: string }) {
  return <div className="empty"><h2>{title}</h2>{description && <p>{description}</p>}</div>;
}

function ConversationTurn({ question, response }: { question: string; response?: Answer }) {
  return (
    <article className="turn">
      <p className="question">{question}</p>
      {response ? (
        <div className="answer-card">
          <p className="answer">{response.answer}</p>
          {response.sources.length ? (
            <div className="citations">
              {response.sources.map((source, index) => (
                <details key={index}>
                  <summary>{index + 1}. {source.doc_name || "Document"}{source.page != null && ` · page ${source.page}`}</summary>
                  {source.excerpt && <p>{source.excerpt}</p>}
                </details>
              ))}
            </div>
          ) : <small>No document excerpts were cited for this answer.</small>}
        </div>
      ) : <p className="muted">Looking through your sources…</p>}
    </article>
  );
}

function NotebookPanel({ notebook, active }: { notebook: Notebook; active: boolean }) {
  const id = useId();
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [turns, setTurns] = useState<Turn[]>();
  const [question, setQuestion] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [uploading, setUploading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [historyError, setHistoryError] = useState("");
  const [sourceError, setSourceError] = useState("");
  const [actionError, setActionError] = useState("");
  const ready = documents.some((document) => document.status === "processed");

  useEffect(() => {
    const controller = new AbortController();
    api.history(notebook.id, controller.signal).then(setTurns).catch((error) => {
      if (!controller.signal.aborted) setHistoryError(errorMessage(error));
    });
    return () => controller.abort();
  }, [notebook.id]);

  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const list = await api.documents(notebook.id, controller.signal);
        if (controller.signal.aborted) return;
        setDocuments(list);
        setSourceError("");
        if (list.some(({ status }) => status === "queued" || status === "processing")) {
          timer = setTimeout(load, 2200);
        }
      } catch (error) {
        if (!controller.signal.aborted) setSourceError(errorMessage(error));
      }
    }
    void load();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [active, notebook.id, refresh]);

  async function upload(file: File) {
    setUploading(true);
    setActionError("");
    try {
      await api.upload(notebook.id, file);
      setRefresh((value) => value + 1);
    } catch (error) {
      setActionError(errorMessage(error));
    } finally {
      setUploading(false);
    }
  }

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = question.trim();
    if (!text || !ready || pendingQuestion || !turns) return;
    setPendingQuestion(text);
    setQuestion("");
    setActionError("");
    try {
      const response = await api.ask(notebook.id, text);
      setTurns((previous) => [...(previous ?? []), { question: text, response }]);
    } catch (error) {
      setQuestion((draft) => draft || text);
      setActionError(errorMessage(error));
    } finally {
      setPendingQuestion("");
    }
  }

  return (
    <div className="notebook-panel" hidden={!active}>
      <section className="conversation" aria-labelledby={`${id}-title`}>
        <div className="conversation-head">
          <span className="kicker">NOTEBOOK</span><h1 id={`${id}-title`}>{nameOf(notebook)}</h1>
        </div>
        {actionError && <p className="error banner" role="alert">{actionError}</p>}
        <div className="messages" aria-live="polite">
          {historyError && <p className="error" role="alert">{historyError}</p>}
          {!turns && !historyError && <Empty title="Loading notebook…" />}
          {turns?.length === 0 && !pendingQuestion && (
            <Empty title="Start a conversation" description="Upload a document, then ask for an overview or a specific detail." />
          )}
          {turns?.map((turn, index) => <ConversationTurn key={index} {...turn} />)}
          {pendingQuestion && <ConversationTurn question={pendingQuestion} />}
        </div>
        <form className="composer" onSubmit={ask}>
          <label htmlFor={`${id}-question`}>Ask a question</label>
          <div className="question-row">
            <textarea id={`${id}-question`} rows={2} maxLength={8000} required value={question}
              onChange={(event) => setQuestion(event.target.value)} placeholder="What would you like to know?" />
            <button type="submit" disabled={!turns || !ready || !!pendingQuestion}>{pendingQuestion ? "Asking…" : "Ask"}</button>
          </div>
          <small>{ready ? "Source excerpts appear below each sourced answer." : "Add a source and wait for it to finish processing."}</small>
        </form>
      </section>
      <aside className="sources-panel" aria-labelledby={`${id}-sources`}>
        <div className="section-title"><h2 id={`${id}-sources`}>Sources</h2><span className="count">{documents.length}</span></div>
        <label className="upload" htmlFor={`${id}-upload`}>
          <strong>+ Upload a document</strong><small>PDF, TXT, Markdown, CSV</small>
        </label>
        <input id={`${id}-upload`} className="visually-hidden" type="file" accept=".pdf,.txt,.md,.csv" disabled={uploading}
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = "";
            if (file) void upload(file);
          }} />
        {uploading && <p className="muted upload-status" role="status">Uploading…</p>}
        {sourceError && <p className="error upload-status" role="alert">{sourceError}{" "}
          <button type="button" className="secondary" onClick={() => setRefresh((value) => value + 1)}>Retry</button>
        </p>}
        <ul className="documents">
          {documents.map((document) => (
            <li key={document.id}><strong>{document.name}</strong><small>{statuses[document.status] || document.status}</small></li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

function CreateNotebookDialog({ onCreate }: { onCreate: (notebook: Notebook) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const form = useRef<HTMLFormElement>(null);
  const id = useId();
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = String(new FormData(event.currentTarget).get("title")).trim();
    if (!title) {
      setError("Enter a notebook name.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      onCreate(await api.createNotebook(title));
      dialog.current?.close();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <button className="secondary" aria-label="New notebook" onClick={() => {
        setError("");
        form.current?.reset();
        dialog.current?.showModal();
      }}>+ New</button>
      <dialog ref={dialog} aria-labelledby={`${id}-title`} onCancel={(event) => { if (saving) event.preventDefault(); }}>
        <form ref={form} onSubmit={submit}>
          <h2 id={`${id}-title`}>New notebook</h2>
          <label htmlFor={`${id}-name`}>Notebook name</label>
          <input id={`${id}-name`} name="title" required maxLength={120} placeholder="e.g. Research notes" />
          {error && <p className="error" role="alert">{error}</p>}
          <div className="dialog-actions">
            <button type="button" className="secondary" disabled={saving} onClick={() => dialog.current?.close()}>Cancel</button>
            <button type="submit" disabled={saving}>Create notebook</button>
          </div>
        </form>
      </dialog>
    </>
  );
}

export function Workspace() {
  const [notebooks, setNotebooks] = useState<Notebook[]>([]);
  const [selected, setSelected] = useState<string>();
  const [opened, setOpened] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function select(id: string) {
    setOpened((ids) => ids.includes(id) ? ids : [...ids, id]);
    setSelected(id);
  }

  useEffect(() => {
    const controller = new AbortController();
    api.notebooks(controller.signal).then((list) => {
      setNotebooks(list);
      if (list[0]) select(list[0].id);
    }).catch((error) => {
      if (!controller.signal.aborted) setError(errorMessage(error));
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, []);

  return (
    <main className="workspace">
      <aside className="sidebar" aria-label="Notebooks">
        <div className="section-title">
          <h2>Notebooks</h2>
          {!loading && <CreateNotebookDialog onCreate={(notebook) => {
            setNotebooks((list) => [notebook, ...list]);
            select(notebook.id);
          }} />}
        </div>
        <nav id="notebooks" aria-label="Your notebooks">
          {notebooks.map((notebook) => (
            <button className="notebook" key={notebook.id} aria-current={notebook.id === selected ? true : undefined}
              onClick={() => select(notebook.id)}>{nameOf(notebook)}</button>
          ))}
        </nav>
      </aside>
      {notebooks.filter(({ id }) => opened.includes(id)).map((notebook) => (
        <NotebookPanel key={notebook.id} notebook={notebook} active={selected === notebook.id} />
      ))}
      {!selected && (
        <section className="conversation">
          <div className="conversation-head"><h1>Your workspace</h1></div>
          {error && <p className="error banner" role="alert">{error}</p>}
          {loading && <Empty title="Loading notebooks…" />}
          {!loading && !error && <Empty title="Create your first notebook" description="Use + New to make a place for your documents and questions." />}
        </section>
      )}
    </main>
  );
}
