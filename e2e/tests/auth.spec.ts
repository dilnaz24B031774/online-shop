import { test, expect } from '@playwright/test';
import { USER, loginViaUi } from '../helpers';

test.describe('Login and access', () => {
  test('login page opens with username and password fields', async ({ page }) => {
    await page.goto('/login');
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
    await expect(page.locator('#u')).toBeVisible();
    await expect(page.locator('#p')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeEnabled();
  });

  test('empty form shows an error message', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('alert')).toHaveText('Please fill in all required fields.');
  });

  test('wrong password shows an error and does not log in', async ({ page }) => {
    await page.goto('/login');
    // A non-existing user on purpose: one failed try must not count against the real "admin" account
    await page.locator('#u').fill('e2e_nobody');
    await page.locator('#p').fill('WrongPass1');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('alert')).toHaveText('Wrong username or password.');
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole('button', { name: 'Sign out' })).toHaveCount(0);
  });

  test('password can be shown and hidden', async ({ page }) => {
    await page.goto('/login');
    const password = page.locator('#p');
    await password.fill('Secret123');
    await expect(password).toHaveAttribute('type', 'password');
    await page.getByRole('button', { name: 'Show password' }).click();
    await expect(password).toHaveAttribute('type', 'text');
    await page.getByRole('button', { name: 'Hide password' }).click();
    await expect(password).toHaveAttribute('type', 'password');
  });

  test('admin can log in and log out', async ({ page }) => {
    await loginViaUi(page, USER);
    await expect(page).toHaveURL('/');
    await expect(page.getByRole('link', { name: 'Profile' })).toContainText('Admin');

    await page.getByRole('button', { name: 'Sign out' }).click();
    await expect(page.getByRole('banner').getByRole('link', { name: 'Sign in' })).toBeVisible();
  });

  test('private pages redirect to login and come back after login', async ({ page }) => {
    await page.goto('/cart');
    await expect(page).toHaveURL(/\/login\?returnUrl=%2Fcart/);

    await page.locator('#u').fill(USER.username);
    await page.locator('#p').fill(USER.password);
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page).toHaveURL(/\/cart$/);
    await expect(page.getByRole('heading', { name: 'Your cart' })).toBeVisible();
  });

  test('language switch changes the page and is remembered after reload', async ({ page }) => {
    await page.goto('/login');
    await page.getByRole('group', { name: 'Language' }).getByRole('button', { name: 'RU' }).click();
    await expect(page.getByRole('heading', { name: 'Вход' })).toBeVisible();

    await page.reload();
    await expect(page.getByRole('heading', { name: 'Вход' })).toBeVisible();
  });
});