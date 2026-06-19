# BoardRoom web

The web front end for BoardRoom: a Vite + React + TypeScript single page that
renders a debate from the API in a light, editorial style.

```bash
pnpm install
pnpm dev        # http://localhost:5173
```

The dev server proxies `/api` to the Django backend on port 8000, so start the
backend too (see the project root README). On first load the page shows a
sample debate; enter a ticker to run a live one.

```bash
pnpm build      # type-check and produce a production build in dist/
```

Source layout:

- `src/types.ts` mirrors the API result schema.
- `src/api.ts` fetches a debate.
- `src/components/` holds the verdict hero, research brief, investor cards, and
  risk panel.
- `src/index.css` defines the theme tokens (Tailwind v4).
