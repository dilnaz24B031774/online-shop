import { test, expect } from '@playwright/test';
import { MOUSE, productCard } from '../helpers';

test.describe('Catalog, product page and search (not logged in)', () => {
  test('catalog shows products with prices', async ({ page }) => {
    await page.goto('/catalog');
    await expect(page.locator('app-product-card').first()).toBeVisible();
    expect(await page.locator('app-product-card').count()).toBeGreaterThan(5);

    const mouse = productCard(page, MOUSE.name);
    await expect(mouse).toBeVisible();
    await expect(mouse).toContainText(MOUSE.price);
  });

  test('product page opens from the catalog', async ({ page }) => {
    await page.goto('/catalog');
    await productCard(page, MOUSE.name).getByRole('heading').getByRole('link').click();

    await expect(page).toHaveURL(/\/product\/\d+/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(MOUSE.name);
    await expect(page.locator('.price')).toHaveText(MOUSE.price);
    await expect(page.getByText('EL-MOUSE-01')).toBeVisible();
    // guest cannot buy: the button asks to sign in
    await expect(page.getByRole('button', { name: 'Sign in to buy' })).toBeVisible();
  });

  test('search finds a product', async ({ page }) => {
    await page.goto('/catalog');
    await page.getByRole('search').getByPlaceholder(/Search products/).fill('mouse');
    await page.getByRole('search').getByPlaceholder(/Search products/).press('Enter');

    await expect(page).toHaveURL(/\/search\?q=mouse/);
    await expect(page.getByRole('heading', { level: 1 })).toContainText('Search results for');
    await expect(productCard(page, MOUSE.name)).toBeVisible();
  });

  test('search with a nonsense word shows "nothing found"', async ({ page }) => {
    await page.goto('/catalog');
    await page.getByRole('search').getByPlaceholder(/Search products/).fill('zzqxw');
    await page.getByRole('search').getByPlaceholder(/Search products/).press('Enter');

    await expect(page.getByText('Nothing found for this word.')).toBeVisible();
  });

  test('"Add to cart" for a guest sends to the login page', async ({ page }) => {
    await page.goto('/catalog');
    await productCard(page, MOUSE.name).locator('button.add').click();
    await expect(page).toHaveURL(/\/login\?returnUrl=/);
  });
});