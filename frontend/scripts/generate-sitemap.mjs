// Writes public/sitemap.xml and public/robots.txt for the public pages.
// Set SITE_URL to the deployed origin before building, for example:
//   SITE_URL=https://lostfound.university.edu npm run build
import { writeFileSync } from 'node:fs';

const site = (process.env.SITE_URL || 'http://localhost:4200').replace(/\/+$/, '');
// Only pages that work without signing in; item pages require a campus account.
const pages = ['/', '/login', '/register', '/privacy'];
const today = new Date().toISOString().slice(0, 10);

const urls = pages
  .map((path) => `  <url><loc>${site}${path}</loc><lastmod>${today}</lastmod></url>`)
  .join('\n');
writeFileSync(
  'public/sitemap.xml',
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls}\n</urlset>\n`,
);
writeFileSync(
  'public/robots.txt',
  `User-agent: *\nDisallow: /dashboard\nDisallow: /staff\nDisallow: /admin\nDisallow: /api/\n\nSitemap: ${site}/sitemap.xml\n`,
);
console.log(`sitemap.xml and robots.txt written for ${site}`);
