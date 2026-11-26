import { test, expect, type Page } from '@playwright/test';
import {
  MOUSE, addMouseFromCatalog, cancelOrderViaApi, cartLink, clearCart, ensureAddress, loginViaUi,
} from '../helpers';

const GOOD_CARD = { number: '4242 4242 4242 4242', holder: 'AIGERIM K', expiry: '12/3 0', cvc: '123' };

async function fillCard(page: Page, card: typeof GOOD_CARD) {
  await page.locator('#cn').fill(card.number);
  await page.locator('#ch').fill(card.holder);
  await page.locator('#ce').fill(card.expiry);
  await page.locator('#cc').fill(card.cvc);
}

test.describe('Checkout (logged in as admin, mouse in the cart)', () => {
  let createdOrderId: number | null = null;

  test.beforeEach(async ({ page, request }) => {
    createdOrderId = null;
    await clearCart(request);
    await ensureAddress(request);          // admin has no address in the demo data
    await loginViaUi(page);
    await addMouseFromCatalog(page);
    await cartLink(page).click();
    await page.getByRole('link', { name: 'Go to checkout' }).click();
    await expect(page.getByRole('heading', { name: 'Checkout' })).toBeVisible();
    // wait until the delivery address is loaded and selected, otherwise "Place order" says "Add a delivery address first."
    await expect(page.locator('input[name="address"]').first()).toBeChecked();
  });

  // If a test stops in the middle, return the mouse to the stock (only 6 in the demo data).
  test.afterEach(async ({ request }) => {
    if (createdOrderId) await cancelOrderViaApi(request, createdOrderId);
    await clearCart(request);
  });

  test('full flow: pay by card, see the order, cancel it', async ({ page }) => {
    // the order summary shows the mouse and the total
    await expect(page.locator('.summary .line', { hasText: MOUSE.name })).toContainText('× 1');
    await expect(page.locator('.summary .line.total')).toContainText('$25.00');

    // delivery address is selected, payment by card
    await page.locator('label.option', { hasText: 'Visa, Mastercard, Mir' }).click();
    await fillCard(page, GOOD_CARD);
    await page.getByRole('button', { name: 'Place order' }).click();

    // success page
    const heading = page.getByRole('heading', { name: /Order #\d+ is placed and paid/ });
    await expect(heading).toBeVisible();
    const orderId = Number((await heading.textContent())!.match(/#(\d+)/)![1]);
    createdOrderId = orderId;
    await expect(page.locator('.done .total')).toContainText('$25.00');
    await expect(page.locator('.done .total')).toContainText('Paid');
    await expect(cartLink(page).locator('.count')).toHaveCount(0);       // cart is empty now

    // the order is in "My orders"
    await page.getByRole('link', { name: 'Open my orders' }).click();
    await expect(page).toHaveURL(/\/orders$/);
    const order = page.locator('article.order', { hasText: `Order #${orderId}` });
    await expect(order).toContainText(MOUSE.name);
    await expect(order.locator('.status')).toHaveText('Paid');

    // cancel it (also gives the mouse back to the stock for the next test run)
    await order.getByRole('button', { name: 'Cancel order' }).click();
    await order.getByRole('button', { name: 'Yes, cancel' }).click();
    await expect(page.locator('.alert-ok')).toContainText(`Order #${orderId} is cancelled`);
    await expect(order.locator('.status')).toHaveText('Cancelled');
  });

  const cardErrors = [
    { title: 'wrong card number', card: { ...GOOD_CARD, number: '1234 5678 9012 3456' }, message: 'Check the card number.' },
    { title: 'empty card holder', card: { ...GOOD_CARD, holder: '' }, message: 'Enter the name as on the card.' },
    { title: 'expired date', card: { ...GOOD_CARD, expiry: '01/20' }, message: 'Check the expiry date (MM/YY).' },
    { title: 'short CVC', card: { ...GOOD_CARD, cvc: '1' }, message: 'CVC is 3 digits on the back of the card.' },
  ];
  for (const { title, card, message } of cardErrors) {
    test(`card form validation: ${title}`, async ({ page }) => {
      await fillCard(page, card);
      await page.getByRole('button', { name: 'Place order' }).click();
      await expect(page.locator('.summary .alert-error')).toHaveText(message);
      await expect(page.getByRole('heading', { name: /is placed and paid/ })).toHaveCount(0);
    });
  }

  test('promo code: unknown code is rejected', async ({ page }) => {
    await page.locator('#promo').fill('FAKECODE');
    await page.getByRole('button', { name: 'Apply' }).click();
    await expect(page.locator('.promo-err')).toHaveText('Promo code not found.');
  });
});