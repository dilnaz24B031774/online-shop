import { test, expect } from '@playwright/test';
import { MOUSE, addMouseFromCatalog, cartLink, clearCart, loginViaUi, productCard } from '../helpers';

test.describe('Cart (logged in as admin)', () => {
  test.beforeEach(async ({ page, request }) => {
    await clearCart(request);        // same start for every test
    await loginViaUi(page);
  });

  test('add the mouse from the catalog: button and header cart update', async ({ page }) => {
    await addMouseFromCatalog(page);

    await expect(productCard(page, MOUSE.name).locator('button.add')).toContainText('In cart · 1');
    await expect(cartLink(page).locator('.count')).toHaveText('1');
    await expect(cartLink(page)).toContainText(MOUSE.price);
  });

  test('cart page: item, quantity buttons and remove', async ({ page }) => {
    await addMouseFromCatalog(page);
    await cartLink(page).click();

    await expect(page.getByRole('heading', { name: 'Your cart' })).toBeVisible();
    await expect(page.locator('article.row')).toContainText(MOUSE.name);
    await expect(page.locator('.sum-row.total')).toContainText('$25.00');

    await page.getByRole('button', { name: '+', exact: true }).click();
    await expect(page.locator('.stepper span')).toHaveText('2');
    await expect(page.locator('.sum-row.total')).toContainText('$50.00');

    await page.getByRole('button', { name: '−', exact: true }).click();
    await expect(page.locator('.stepper span')).toHaveText('1');
    await expect(page.locator('.sum-row.total')).toContainText('$25.00');

    await page.getByRole('button', { name: 'Remove' }).click();
    await expect(page.getByText('Your cart is empty. Add something from the catalog.')).toBeVisible();
    await expect(cartLink(page).locator('.count')).toHaveCount(0);
  });

  test('add 2 mice from the product page', async ({ page }) => {
    await page.goto('/catalog');
    await productCard(page, MOUSE.name).getByRole('heading').getByRole('link').click();

    await page.getByRole('button', { name: '+', exact: true }).click();
    await page.getByRole('button', { name: 'Add to cart' }).click();

    await expect(page.locator('.in-cart')).toContainText('In cart: 2');
    await expect(cartLink(page)).toContainText('$50.00');
  });

  test('cart is kept after page reload (it is stored on the server)', async ({ page }) => {
    await addMouseFromCatalog(page);
    await page.reload();
    await expect(cartLink(page).locator('.count')).toHaveText('1');
  });
});