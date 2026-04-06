/**
 * E2E Tests: Data Import Flow
 *
 * Tests the imports page tabs, file scanning, and import history.
 */

import { test, expect, login } from "./helpers";

test.describe("Data Import Page", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.click('a[href*="/imports"]');
    await page.waitForLoadState("networkidle");
  });

  test("imports page renders with tabs", async ({ page }) => {
    expect(page.url()).toContain("/imports");

    // Should have tab buttons
    const buttons = page.locator("button");
    const buttonCount = await buttons.count();
    expect(buttonCount).toBeGreaterThanOrEqual(2);
  });

  test("imports page has stat cards", async ({ page }) => {
    const statCards = page.locator(".stat-card");
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });
});

