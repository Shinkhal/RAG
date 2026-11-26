const $ = (id) => document.getElementById(id);
const rag = "/api/v1/rag";
const auth = "/api/v1/auth";
const signup = location.pathname === "/signup";
const pending = new Set();
let notebooks = [];
let selected;
let documents = [];
let pollTimer;
let selectionVersion = 0;

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function showError(id, error) {
  $(id).textContent = error?.message || "";
  $(id).hidden = !error;
}

async function api(path, { method = "GET", data, body } = {}) {
  const headers = { "X-RAG-Request": "1" };
  if (data !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(data);
  }
  const response = await fetch(path, { method, headers, body, cache: "no-store" });
  if (response.status === 204) return;
  const result = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && path.startsWith(rag)) location.assign("/login");
    const detail = typeof result?.detail === "string" ? result.detail : null;
    const error = new Error(detail || (response.status === 422
      ? "Check the fields and try again."
      : "The service could not complete the request. Try again."));
    error.status = response.status;
    throw error;
  }
  return result;
}

function showAuth() {
  const mode = signup ? "Create account" : "Sign in";
  $("auth-heading").textContent = mode;
  $("auth-submit").textContent = mode;
  $("auth-password").autocomplete = signup ? "new-password" : "current-password";
  $("auth-password").minLength = signup ? 15 : 1;
  $("password-hint").hidden = !signup;
  $("auth-prompt").textContent = signup ? "Already have an account?" : "New to RAG Workspace?";
  $("auth-link").textContent = signup ? "Sign in" : "Create an account";
  $("auth-link").href = signup ? "/login" : "/signup";
  $("boot").hidden = true;
  $("auth").hidden = false;
}

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("auth-error");
  $("auth-submit").disabled = true;
  try {
    const data = Object.fromEntries(new FormData(event.currentTarget));
    await api(`${auth}/${signup ? "signup" : "login"}`, { method: "POST", data });
    location.replace("/workspace");
  } catch (error) {
    showError("auth-error", error);
  } finally {
    $("auth-submit").disabled = false;
  }
});

$("logout").addEventListener("click", async () => {
  $("logout").disabled = true;
  try {
    await api(`${auth}/logout`, { method: "POST" });
    location.replace("/login");
  } catch (error) {
    showError("workspace-error", error);
    $("logout").disabled = false;
  }
});

function renderNotebooks() {
  $("notebooks").replaceChildren(...notebooks.map((notebook) => {
    const button = el("button", notebook.title || "Untitled notebook", "notebook");
    if (selected?.id === notebook.id) button.setAttribute("aria-current", "true");
    button.addEventListener("click", () => selectNotebook(notebook));
    return button;
  }));
}

function renderEmpty(title, description) {
  const empty = el("div", undefined, "empty");
  empty.append(el("h2", title), el("p", description));
  $("messages").replaceChildren(empty);
}

function updateComposer() {
  const ready = documents.some((doc) => doc.status === "processed");
  const asking = selected && pending.has(selected.id);
  $("send").disabled = !ready || asking;
  $("send").textContent = asking ? "Asking…" : "Ask";
  $("composer-hint").textContent = ready
    ? "Source excerpts appear below each sourced answer."
    : "Add a source and wait for it to finish processing.";
}

function turnNode(question, response) {
  const turn = el("article", undefined, "turn");
  turn.append(el("p", question, "question"));
  if (!response) {
    turn.append(el("p", "Looking through your sources…", "muted"));
    return turn;
  }
  const answer = el("div", undefined, "answer-card");
  answer.append(el("p", response.answer, "answer"));
  if (response.metadata?.general_fallback || !response.sources.length) {
    answer.append(el("small", "No document excerpts were cited for this answer."));
  }
  if (response.sources.length) {
    const cites = el("div", undefined, "citations");
    response.sources.forEach((source, index) => {
      const detail = el("details");
      const page = source.page == null ? "" : ` · page ${source.page}`;
      detail.append(el("summary", `${index + 1}. ${source.doc_name || "Document"}${page}`));
      if (source.excerpt) detail.append(el("p", source.excerpt));
      cites.append(detail);
    });
    answer.append(cites);
  }
  turn.append(answer);
  return turn;
}

function renderHistory(turns) {
  if (turns.length) {
    $("messages").replaceChildren(...turns.map(({ question, response }) => turnNode(question, response)));
  } else {
    renderEmpty("Start a conversation", "Upload a document, then ask for an overview or a specific detail.");
  }
}

async function refreshDocuments(notebookId, version) {
  clearTimeout(pollTimer);
  const path = `${rag}/sessions/${encodeURIComponent(notebookId)}/documents`;
  const list = await api(path);
  if (version !== selectionVersion) return;
  documents = list;
  $("source-count").textContent = String(list.length);
  $("documents").replaceChildren(...list.map((doc) => {
    const item = el("li");
    const status = {
      processed: "Ready",
      failed: "Processing failed",
      queued: "Queued",
      processing: "Processing…",
    }[doc.status] || doc.status;
    item.append(el("strong", doc.name), el("small", status));
    return item;
  }));
  updateComposer();
  if (list.some((doc) => ["queued", "processing"].includes(doc.status))) {
    pollTimer = setTimeout(() => {
      refreshDocuments(notebookId, version).catch((error) => {
        if (version === selectionVersion) showError("workspace-error", error);
      });
    }, 2200);
  }
}

async function selectNotebook(notebook) {
  const version = ++selectionVersion;
  clearTimeout(pollTimer);
  selected = notebook;
  documents = [];
  $("upload-status").textContent = "";
  $("documents").replaceChildren();
  $("source-count").textContent = "";
  showError("workspace-error");
  renderNotebooks();
  $("notebook-title").textContent = notebook.title || "Untitled notebook";
  $("question-form").hidden = false;
  $("sources-panel").hidden = false;
  $("question").value = "";
  updateComposer();
  renderEmpty("Loading notebook…", "");
  try {
    const [turns] = await Promise.all([
      api(`${rag}/sessions/${encodeURIComponent(notebook.id)}/history`),
      refreshDocuments(notebook.id, version),
    ]);
    if (version === selectionVersion && !pending.has(notebook.id)) renderHistory(turns);
  } catch (error) {
    if (version === selectionVersion) {
      renderEmpty("Notebook unavailable", "Select this notebook again to retry.");
      showError("workspace-error", error);
    }
  }
}

$("new-notebook").addEventListener("click", () => {
  $("notebook-form").reset();
  showError("notebook-error");
  $("notebook-dialog").showModal();
});
$("cancel-notebook").addEventListener("click", () => $("notebook-dialog").close());

$("notebook-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = $("notebook-name").value.trim();
  if (!title) {
    showError("notebook-error", new Error("Enter a notebook name."));
    return;
  }
  const submit = event.submitter;
  submit.disabled = true;
  showError("notebook-error");
  try {
    const notebook = await api(`${rag}/sessions`, { method: "POST", data: { title } });
    notebooks = [notebook, ...notebooks];
    $("notebook-dialog").close();
    await selectNotebook(notebook);
  } catch (error) {
    showError("notebook-error", error);
  } finally {
    submit.disabled = false;
  }
});

$("upload").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file || !selected) return;
  const notebookId = selected.id;
  const body = new FormData();
  body.append("file", file);
  body.append("session_id", notebookId);
  $("upload-status").textContent = "Uploading…";
  $("upload").disabled = true;
  showError("workspace-error");
  try {
    await api(`${rag}/ingest`, { method: "POST", body });
    if (selected?.id === notebookId) {
      $("upload-status").textContent = "";
      await refreshDocuments(notebookId, selectionVersion);
    }
  } catch (error) {
    if (selected?.id === notebookId) {
      $("upload-status").textContent = "";
      showError("workspace-error", error);
    }
  } finally {
    $("upload").value = "";
    $("upload").disabled = false;
  }
});

$("question-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = $("question").value.trim();
  if (!question || !selected || $("send").disabled) return;
  const sessionId = selected.id;
  pending.add(sessionId);
  updateComposer();
  showError("workspace-error");
  $("question").value = "";
  const turn = turnNode(question);
  $("messages").querySelector(".empty")?.remove();
  $("messages").append(turn);
  try {
    const response = await api(`${rag}/query`, {
      method: "POST", data: { query: question, session_id: sessionId },
    });
    if (selected?.id === sessionId) {
      if (turn.isConnected) {
        turn.replaceWith(turnNode(question, response));
      } else {
        const version = selectionVersion;
        const turns = await api(`${rag}/sessions/${encodeURIComponent(sessionId)}/history`);
        if (version === selectionVersion) renderHistory(turns);
      }
    }
  } catch (error) {
    if (selected?.id === sessionId) {
      turn.remove();
      if (!$("question").value) $("question").value = question;
      showError("workspace-error", error);
    }
  } finally {
    pending.delete(sessionId);
    updateComposer();
  }
});

async function start() {
  let account;
  try {
    account = await api(`${auth}/me`);
  } catch (error) {
    if (error.status !== 401) {
      $("boot").textContent = error.message;
      return;
    }
    if (!["/login", "/signup"].includes(location.pathname)) {
      location.replace("/login");
      return;
    }
    showAuth();
    return;
  }
  if (location.pathname !== "/workspace") {
    location.replace("/workspace");
    return;
  }
  $("email").textContent = account.email;
  $("account").hidden = false;
  $("boot").hidden = true;
  $("workspace").hidden = false;
  try {
    notebooks = await api(`${rag}/sessions`);
    if (notebooks.length) await selectNotebook(notebooks[0]);
    else renderEmpty("Create your first notebook", "Use + New to make a place for your documents and questions.");
  } catch (error) {
    showError("workspace-error", error);
  }
}

start();
