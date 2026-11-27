import { test, expect, type Page } from "@playwright/test";

type Preferences = {
  theme: "light" | "dark" | "system";
  email_notifications: boolean;
  default_persona_id: string | null;
};

const account = {
  id: "user",
  first_name: "Alex",
  last_name: "Morgan",
  email: "alex@example.com",
  created_at: "2025-01-15T00:00:00Z",
};

const profile = {
  ...account,
  full_name: "Alex Morgan",
  is_active: true,
  updated_at: "2025-06-01T10:30:00Z",
  last_login_at: "2025-06-02T09:15:00Z",
  preferences: {
    theme: "system",
    email_notifications: true,
    default_persona_id: "concise",
  },
  stats: {
    total_documents: 2,
    total_sessions: 3,
    total_chunks: 18,
    total_queries: 7,
    storage_bytes: 3145728,
    documents_by_status: { processed: 1, queued: 1 },
  },
  documents: [
    {
      id: "doc-1",
      name: "Research notes.pdf",
      mime_type: "application/pdf",
      size_bytes: 2097152,
      status: "processed",
      chunks_created: 12,
      session_id: "session-1",
      session_title: "Product research",
      created_at: "2025-05-28T12:00:00Z",
      processed_at: "2025-05-28T12:01:00Z",
      expires_at: "2025-08-26T12:00:00Z",
    },
    {
      id: "doc-2",
      name: "ideas.md",
      mime_type: "text/markdown",
      size_bytes: 2048,
      status: "queued",
      chunks_created: 0,
      session_id: "session-1",
      session_title: "Product research",
      created_at: "2025-06-01T08:00:00Z",
      processed_at: null,
      expires_at: "2025-08-30T08:00:00Z",
    },
  ],
};

const personas = [
  { persona_id: "concise", name: "Concise", description: "Short answers.", style_config: { system_prompt: "Be concise." }, intensity: 0.6, sample_responses: null, is_active: true, is_system: true },
  { persona_id: "teacher", name: "Teacher", description: "Explains step by step.", style_config: { system_prompt: "Teach carefully." }, intensity: 0.8, sample_responses: null, is_active: true, is_system: true },
];

async function mockProfile(page: Page) {
  let preferences: Preferences = { ...profile.preferences };
  let patched: Partial<Preferences> | null = null;

  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) return route.fulfill({ json: account });
    if (path.endsWith("/auth/profile/preferences")) {
      patched = JSON.parse(route.request().postData() || "{}");
      preferences = { ...preferences, ...patched };
      return route.fulfill({ json: preferences });
    }
    if (path.endsWith("/auth/profile")) return route.fulfill({ json: { ...profile, preferences } });
    if (path.endsWith("/personas")) return route.fulfill({ json: personas });
    return route.fulfill({ status: 404, json: { detail: "Not found" } });
  });

  return { patched: () => patched };
}

test("profile page shows account, uploads, and preferences without password controls", async ({ page }) => {
  const state = await mockProfile(page);

  await page.goto("/profile");

  await expect(page.getByRole("heading", { name: "Your profile" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Alex Morgan" })).toBeVisible();
  await expect(page.getByText("alex@example.com").first()).toBeVisible();
  await expect(page.getByText("Joined Jan 15, 2025")).toBeVisible();

  // Documents uploaded by the user.
  await expect(page.getByText("Research notes.pdf")).toBeVisible();
  await expect(page.getByText("ideas.md")).toBeVisible();
  await expect(page.locator(".profile-document-list .status-badge")).toHaveCount(2);
  await expect(page.locator(".profile-document-list .status-badge").first()).toHaveText("Ready");

  // Password management was removed from the profile page.
  await expect(page.getByRole("heading", { name: "Password" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Update password" })).toHaveCount(0);
  await expect(page.getByLabel("Current password")).toHaveCount(0);

  // Preferences load and save through the new endpoint.
  await expect(page.getByLabel("Theme")).toHaveValue("system");
  await expect(page.getByLabel("Default persona")).toHaveValue("concise");
  await page.getByLabel("Theme").selectOption("dark");
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText("Preferences saved.")).toBeVisible();
  expect(state.patched()).toMatchObject({ theme: "dark" });
});

test("theme preference applies immediately and survives a reload", async ({ page }) => {
  await mockProfile(page);

  await page.goto("/profile");
  await expect(page.locator("html")).toHaveAttribute("data-theme-preference", "system");

  await page.getByLabel("Theme").selectOption("dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText("Preferences saved.")).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("rag-theme"))).toBe("dark");

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("profile page shows an empty library state", async ({ page }) => {
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) return route.fulfill({ json: account });
    if (path.endsWith("/auth/profile")) {
      return route.fulfill({
        json: {
          ...profile,
          stats: { ...profile.stats, total_documents: 0, documents_by_status: {} },
          documents: [],
        },
      });
    }
    if (path.endsWith("/personas")) return route.fulfill({ json: personas });
    return route.fulfill({ status: 404, json: { detail: "Not found" } });
  });

  await page.goto("/profile");

  await expect(page.getByText("No documents yet")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open workspace" })).toBeVisible();
});

for (const width of [1440, 820, 390]) {
  test(`profile page has no horizontal overflow at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await mockProfile(page);
    await page.goto("/profile");
    await expect(page.getByRole("heading", { name: "Your profile" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: `/tmp/rag-profile-${width}.png`, fullPage: true });
  });
}
