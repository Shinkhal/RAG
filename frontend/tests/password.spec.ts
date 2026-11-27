import { test, expect } from "@playwright/test";

test("signup enforces the password policy before submitting", async ({ page }) => {
  let signupCalls = 0;

  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) {
      return route.fulfill({ status: 401, json: { detail: "Sign in to continue" } });
    }
    if (path.endsWith("/auth/signup")) {
      signupCalls += 1;
      return route.fulfill({ status: 201, json: {} });
    }
    return route.fulfill({ status: 404, json: { detail: "Not found" } });
  });

  await page.goto("/signup");
  await page.getByLabel("First name").fill("Alex");
  await page.getByLabel("Last name").fill("Morgan");
  await page.getByLabel("Email address").fill("alex@example.com");
  await page.getByLabel("Password", { exact: true }).fill("password");
  await page.getByRole("button", { name: "Create account" }).click();

  await expect(page.getByText("Password must include an uppercase letter.")).toBeVisible();
  expect(signupCalls).toBe(0);
});

test("password reset enforces the password policy", async ({ page }) => {
  await page.route("**/api/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/auth/me")) {
      return route.fulfill({ status: 401, json: { detail: "Sign in to continue" } });
    }
    return route.fulfill({ status: 404, json: { detail: "Not found" } });
  });

  await page.goto("/reset-password?token=sample-reset-token-123456");
  await page.getByLabel("New password", { exact: true }).fill("Password1");
  await page.getByLabel("Confirm new password").fill("Password1");
  await page.getByRole("button", { name: "Reset password" }).click();

  await expect(page.getByText("Password must include a special character.")).toBeVisible();
});
