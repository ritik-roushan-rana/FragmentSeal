# FragmentSeal — web app

The Next.js frontend. See the [project README](../README.md) for setup, and
[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for how the frontend is organised.

```bash
npm install
cp .env.example .env.local
npm run dev          # http://localhost:3000
```

The app expects the API at `NEXT_PUBLIC_API_BASE` (default `http://127.0.0.1:8000`).
Start it with `../scripts/dev.sh` to run both together.

| Command | Does |
| --- | --- |
| `npm run dev` | development server |
| `npm run build` | production build |
| `npx tsc --noEmit` | type check |
| `npx eslint .` | lint |
