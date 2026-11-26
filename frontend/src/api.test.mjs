import assert from 'node:assert/strict';
import { test, afterEach } from 'node:test';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('./api.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { api, ApiError } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });
const json = (value, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});

test('authentication sends same-origin cookies and the required mutation header', async () => {
  globalThis.fetch = async (path, options) => {
    assert.equal(path, '/api/v1/auth/login');
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.headers.get('X-RAG-Request'), '1');
    assert.deepEqual(JSON.parse(options.body), { email: 'reader@example.com', password: 'password' });
    return json({ id: 'account', email: 'reader@example.com' });
  };
  assert.equal((await api.authenticate('login', { email: 'reader@example.com', password: 'password' })).id, 'account');
});

test('upload sends multipart session_id and file without overriding the boundary', async () => {
  globalThis.fetch = async (path, options) => {
    assert.equal(path, '/api/v1/rag/ingest');
    assert.equal(options.body.get('session_id'), 'notebook');
    assert.equal(options.body.get('file').name, 'notes.txt');
    assert.equal(options.headers.has('Content-Type'), false);
    return json({ status: 'queued' }, 202);
  };
  await api.upload('notebook', new File(['notes'], 'notes.txt'));
});

test('query sends the backend query schema', async () => {
  globalThis.fetch = async (path, options) => {
    assert.equal(path, '/api/v1/rag/query');
    assert.deepEqual(JSON.parse(options.body), { session_id: 'notebook', query: 'Summarize' });
    return json({ answer: 'Summary', sources: [] });
  };
  assert.equal((await api.ask('notebook', 'Summarize')).answer, 'Summary');
});

test('an HTML fallback is reported instead of treated as API data', async () => {
  globalThis.fetch = async () => new Response('<html>App</html>', { headers: { 'Content-Type': 'text/html' } });
  await assert.rejects(api.notebooks(new AbortController().signal), /proxy configuration/);
});

test('proxy failure explains backend availability', async () => {
  globalThis.fetch = async () => new Response('', { status: 500 });
  await assert.rejects(api.account(new AbortController().signal), /API server is running/);
});

test('network errors are actionable and aborts remain aborts', async () => {
  globalThis.fetch = async () => { throw new TypeError('Failed to fetch'); };
  await assert.rejects(api.account(new AbortController().signal), /Cannot reach the server/);
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(api.account(controller.signal), TypeError);
});

test('backend validation messages survive and logout accepts 204', async () => {
  globalThis.fetch = async () => json({ detail: 'Incorrect email or password' }, 401);
  await assert.rejects(api.authenticate('login', {}), error => error instanceof ApiError && error.message === 'Incorrect email or password');
  globalThis.fetch = async () => new Response(null, { status: 204 });
  assert.equal(await api.logout(), undefined);
});
