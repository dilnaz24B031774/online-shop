import { expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';

export const API_URL = process.env.API_URL ?? 'http://localhost:8000/api';
export const USER = { username: 'admin', password: 'Shop2026!' };

export const MOUSE = { name: 'Wireless Mouse', price: '$25.00' };

/** Log in through the real login form (what a user does). */
export async function loginViaUi(page: Page, user = USER) {
  await page.goto('/login');
  await page.locator('#u').fill(user.username);
  await page.locator('#p').fill(user.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
}

/** Product card in the catalog by product name. */
export function productCard(page: Page, name: string): Locator {
  return page.locator('app-product-card', { hasText: name });
}

/** Cart link in the site header (shows the number of items and the total). */
export function cartLink(page: Page): Locator {
  return page.locator('header a.cart');
}

/** Open the catalog and press "Add to cart" on the Wireless Mouse card. */
export async function addMouseFromCatalog(page: Page) {
  await page.goto('/catalog');
  const card = productCard(page, MOUSE.name);
  await card.locator('button.add').click();
  await expect(card.locator('button.add')).toContainText('In cart');
}

// ---------------------------------------------------------------- API helpers
// Used only to prepare / clean test data quickly, not to test the UI.

async function authHeaders(request: APIRequestContext) {
  const res = await request.post(`${API_URL}/auth/login/`, { data: USER });
  expect(res.ok(), 'API login with the test account must work').toBeTruthy();
  const { access } = await res.json();
  return { Authorization: `Bearer ${access}` };
}

/** Empty the cart of the test account so every test starts from the same state. */
export async function clearCart(request: APIRequestContext) {
  const headers = await authHeaders(request);
  const cart = await (await request.get(`${API_URL}/cart/`, { headers })).json();
  for (const item of cart.items) {
    await request.post(`${API_URL}/cart/`, { headers, data: { product_id: item.product.id, quantity: 0 } });
  }
}

/** The test account has no delivery address in the demo data: create one if needed. */
export async function ensureAddress(request: APIRequestContext) {
  const headers = await authHeaders(request);
  const list = await (await request.get(`${API_URL}/addresses/`, { headers })).json();
  if (list.length === 0) {
    const res = await request.post(`${API_URL}/addresses/`, {
      headers,
      data: { label: 'E2E Home', city: 'Almaty', street: 'Abay 1', apartment: '10' },
    });
    expect(res.status()).toBe(201);
  }
}

/** Safety net: if a test fails before it cancels its order, give the stock back. */
export async function cancelOrderViaApi(request: APIRequestContext, orderId: number) {
  const headers = await authHeaders(request);
  await request.post(`${API_URL}/orders/${orderId}/cancel/`, { headers });   // error if already cancelled: ignored
}