export interface Account {
  id: string;
  email: string;
}

export interface Notebook {
  id: string;
  title: string | null;
}

export interface SourceDocument {
  id: string;
  name: string;
  status: string;
}

export interface Answer {
  answer: string;
  sources: {
    doc_id: string;
    doc_name: string | null;
    page: number | null;
    excerpt: string | null;
  }[];
}

export interface Turn {
  question: string;
  response: Answer;
}

const auth = "/api/v1/auth";
const rag = "/api/v1/rag";

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

interface Options {
  method?: "POST";
  data?: object;
  body?: FormData;
  signal?: AbortSignal;
}

async function request<T>(path: string, options: Options = {}): Promise<T> {
  const { data, method = "GET", signal } = options;
  const headers = new Headers({ "X-RAG-Request": "1" });
  if (data) headers.set("Content-Type", "application/json");
  const response = await fetch(path, {
    method,
    headers,
    signal,
    body: data ? JSON.stringify(data) : options.body,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && path.startsWith(rag)) location.replace("/login");
    const fallback = response.status === 422
      ? "Check the fields and try again."
      : "The service could not complete the request. Try again.";
    throw new ApiError(response.status, typeof payload?.detail === "string" ? payload.detail : fallback);
  }
  return payload as T;
}

const sessionPath = (id: string) => `${rag}/sessions/${encodeURIComponent(id)}`;

export const api = {
  account: (signal: AbortSignal) => request<Account>(`${auth}/me`, { signal }),
  authenticate: (mode: "login" | "signup", data: { email: string; password: string }) =>
    request<Account>(`${auth}/${mode}`, { method: "POST", data }),
  logout: () => request<void>(`${auth}/logout`, { method: "POST" }),
  notebooks: (signal: AbortSignal) => request<Notebook[]>(`${rag}/sessions`, { signal }),
  createNotebook: (title: string) =>
    request<Notebook>(`${rag}/sessions`, { method: "POST", data: { title } }),
  history: (id: string, signal: AbortSignal) => request<Turn[]>(`${sessionPath(id)}/history`, { signal }),
  documents: (id: string, signal: AbortSignal) =>
    request<SourceDocument[]>(`${sessionPath(id)}/documents`, { signal }),
  upload: (sessionId: string, file: File) => {
    const body = new FormData();
    body.set("session_id", sessionId);
    body.set("file", file);
    return request<unknown>(`${rag}/ingest`, { method: "POST", body });
  },
  ask: (sessionId: string, question: string) =>
    request<Answer>(`${rag}/query`, { method: "POST", data: { session_id: sessionId, query: question } }),
};

export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong. Try again.";
}
