/**
 * E2E Test Helpers & Fixtures
 *
 * Shared login helper, admin credentials, and page utilities.
 */

import { test as base, expect, type Page } from "@playwright/test";

// Default admin credentials (seeded by backend)
export const ADMIN_USER = {
  username: "admin",
  password: "admin1234",
};

/**
 * Login helper — navigates to /login, fills form, submits, waits for redirect.
 */
export async function login(page: Page, username?: string, password?: string) {
  const user = username || ADMIN_USER.username;
  const pass = password || ADMIN_USER.password;

  await page.goto("/fa/login");
  await page.waitForLoadState("domcontentloaded");

  // Fill login form
  const usernameInput = page.locator('input[type="text"]').first();
  const passwordInput = page.locator('input[type="password"]').first();

  await usernameInput.fill(user);
  await passwordInput.fill(pass);

  // Submit
  const submitButton = page.locator('button[type="submit"]').first();
  await submitButton.click();

  // Wait for either: URL no longer has /login, OR a timeout (login may fail)
  try {
    await page.waitForURL((url) => !url.pathname.includes("/login"), { timeout: 15000 });
  } catch {
    // If URL didn't change, check if there's an error message (bad creds)
    // or if localStorage has a token (SPA redirect pending)
    const hasToken = await page.evaluate(() => !!localStorage.getItem("token"));
    if (hasToken) {
      // Token exists — force navigate to dashboard
      await page.goto("/fa");
      await page.waitForLoadState("domcontentloaded");
    }
  }
}

/**
 * Extended test fixture with auto-login.
 */
export const test = base.extend<{ loggedInPage: Page }>({
  loggedInPage: async ({ page }, use) => {
    await login(page);
    await use(page);
  },
});

export { expect };

