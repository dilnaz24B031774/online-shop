import type { FullConfig } from '@playwright/test';

/** Stops early with a clear message if the website or the backend is not running. */
export default async function globalSetup(config: FullConfig) {
  const site = config.projects[0].use.baseURL ?? 'http://localhost:4200';
  const api = process.env.API_URL ?? 'http://localhost:8000/api';

  const check = async (name: string, url: string, hint: string) => {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch (e) {
      throw new Error(`\n${name} is not available at ${url} (${(e as Error).message}).\n${hint}\n`);
    }
  };

  await check('Backend', `${api}/categories/`,
    'Start it: python3 manage.py runserver (with the POSTGRES_* export lines, see README) and run "python3 manage.py seed_shop" once.');
  await check('Website', site, 'Start it: cd frontend && npm start');
}