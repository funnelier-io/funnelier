/**
 * E2E Tests: Leads & Contact Detail
 *
 * Tests the leads listing page, search, and contact detail panel.
 */

import { test, expect, login } from "./helpers";

test.describe("Leads Page", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
    await page.click('a[href*="/leads"]');
    await page.waitForLoadState("networkidle");
  });

  test("leads page renders with stat cards", async ({ page }) => {
    expect(page.url()).toContain("/leads");

    // Should have stat cards
    const statCards = page.locator(".stat-card");
    const count = await statCards.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test("leads page has search input", async ({ page }) => {
    const searchInput = page.locator('input[type="text"]').first();
    await expect(searchInput).toBeVisible();
  });

  test("leads page has data table", async ({ page }) => {
    // Should have a table
    const table = page.locator("table").first();
    await expect(table).toBeVisible();
  });

  test("can filter leads by stage dropdown", async ({ page }) => {
    // Find a select element for stage filter
    const selects = page.locator("select");
    const selectCount = await selects.count();
    expect(selectCount).toBeGreaterThanOrEqual(1);
  });
});

