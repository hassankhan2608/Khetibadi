# AGENTS.md — apps/dashboard

> TypeScript/React 19 SPA. Port 3000 (nginx in Docker). TanStack Router + TanStack Query v5.
> Read root AGENTS.md first, then this file.

## Service Responsibility

Single-page application for farmers. Fully authenticated — no public pages except
`/login` and `/register`. Communicates with all backend services via Axios with
HMAC headers forwarded from auth.

## Layout

```
apps/dashboard/
├── src/
│   ├── routes/                 # TanStack Router file-based routes
│   │   ├── __root.tsx          # root layout + QueryClient provider
│   │   ├── index.tsx           # redirect to /dashboard
│   │   ├── login.tsx
│   │   ├── register.tsx
│   │   └── dashboard/
│   │       ├── index.tsx       # DashboardHomePage
│   │       ├── farm-map.tsx
│   │       ├── crop-advisor.tsx
│   │       ├── disease-scan.tsx
│   │       ├── market-prices.tsx
│   │       ├── ai-assistant.tsx
│   │       └── settings.tsx
│   ├── features/               # feature modules (context-hook pattern)
│   │   ├── farm-map/
│   │   ├── crop-advisor/
│   │   ├── disease-scan/
│   │   ├── market-prices/
│   │   └── ai-chat/
│   ├── store/
│   │   └── auth-store.ts       # @tanstack/react-store: access token (memory), user info
│   ├── lib/
│   │   ├── axios.ts            # Axios instance + 401 interceptor for token refresh
│   │   └── query-client.ts     # TanStack QueryClient config
│   └── main.tsx
├── eslint.config.js
├── tsconfig.json               # strict: true, noUncheckedIndexedAccess: true
├── vite.config.ts
├── package.json
├── bun.lockb
├── nginx.conf
└── Dockerfile
```

## Feature Module Pattern (REQUIRED for all features)

Every feature in `src/features/<name>/` MUST follow this structure:

```
features/farm-map/
├── index.ts                    # public exports only
├── FarmMapPage.tsx             # thin route component — imports Provider
├── FarmMapProvider.tsx         # React Context provider
├── useFarmMap.ts               # context hook (throws if used outside Provider)
├── components/                 # sub-components (consume hook, not props drilling)
├── api/
│   └── farm-api.ts             # TanStack Query hooks + queryKey factory
└── types.ts                    # feature-local types
```

## Auth Token Flow

1. Login → access token stored in `@tanstack/react-store` `authStore` (memory only, never localStorage).
2. Axios interceptor attaches `Authorization: Bearer <token>` to every request.
3. On 401 → interceptor calls `POST /auth/refresh` → retries original request.
4. On refresh failure → clear store → redirect to `/login`.
5. Route guard (`beforeLoad`) checks `authStore.isAuthenticated` → redirect to `/login` if false.

## TanStack Query Rules

- **queryKey factories** for every resource (see root AGENTS.md example).
- **staleTime:** 5 minutes for prices, 10 minutes for farm data, 0 for auth.
- **Mutations:** always `invalidateQueries` on success. Always `toast.error` on failure.
- **SSE (AI chat):** use native `EventSource` — do NOT use TanStack Query for streaming.

## SSE Client Pattern (AI Chat)

```typescript
const source = new EventSource(`${AI_CHAT_URL}/ai/chat/sessions/${id}/messages`, {
  withCredentials: true,
});
source.addEventListener('token', (e) => appendToken(JSON.parse(e.data).token));
source.addEventListener('done', (e) => { finalizeMessage(e.data); source.close(); });
source.addEventListener('error', () => { showErrorToast(); source.close(); });
```

## TanStack Ecosystem (Full Stack)

This dashboard uses the complete TanStack suite. Use the right tool for each concern:

| Package | Version | Purpose |
|---|---|---|
| `@tanstack/react-router` | `^1.170.8` | File-based typed routing, `beforeLoad` guards |
| `@tanstack/react-query` | `^5.100.14` | Server state, caching, mutations |
| `@tanstack/react-table` | `^8.21.3` | Market prices table, headless, fully typed |
| `@tanstack/react-form` | `^1.32.0` | All forms — replaces react-hook-form |
| `@tanstack/react-virtual` | `^3.13.25` | Virtualize long lists (prices, farms) |
| `@tanstack/react-store` | `^0.11.0` | Client state (auth token, user info) |
| `@tanstack/react-pacer` | `^0.22.1` | Debounce/throttle search inputs, API calls |
| `@tanstack/router-plugin` | `^1.168.11` | Vite plugin — auto-generates route tree |

### File-Based Routing Setup (vite.config.ts)

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { tanstackRouter } from '@tanstack/router-plugin/vite';

export default defineConfig({
  plugins: [
    tanstackRouter(), // MUST be before react()
    react(),
  ],
});
```

### TanStack Form Pattern

```typescript
import { useForm } from '@tanstack/react-form';

// Pass Zod schema directly — no adapter or resolver needed (Standard Schema)
const form = useForm({
  defaultValues: { nitrogen: 0, phosphorus: 0, potassium: 0 },
  validators: { onChange: cropInputSchema },
  onSubmit: async ({ value }) => { await cropApi.recommend(value); },
});
```

### TanStack Store Pattern (auth store)

```typescript
// src/store/auth-store.ts
import { Store } from '@tanstack/react-store';
import { useStore } from '@tanstack/react-store';

export const authStore = new Store({
  user: null as User | null,
  token: null as string | null,
});

export const useAuthUser = () => useStore(authStore, (s) => s.user);
export const useAuthToken = () => useStore(authStore, (s) => s.token);

export function setAuth(user: User, token: string) {
  authStore.setState(() => ({ user, token }));
}
export function clearAuth() {
  authStore.setState(() => ({ user: null, token: null }));
}
```

### TanStack Virtual Pattern (price list)

```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

const virtualizer = useVirtualizer({
  count: prices.length,
  getScrollElement: () => parentRef.current,
  estimateSize: () => 56,
  overscan: 5,
});
```

### TanStack Pacer Pattern (search debounce)

```typescript
import { useDebouncer } from '@tanstack/react-pacer';

const debouncedQuery = useDebouncer(searchInput, { wait: 300 });
const { data } = useQuery(commodityOptions(debouncedQuery));
```

## Key Invariants

- **No `any` types.** `strict: true` + `noUncheckedIndexedAccess: true` in tsconfig.
- **No inline styles.** Tailwind classes only.
- **No `console.log` in committed code.** Use the logger utility.
- **All forms:** TanStack Form + Zod (Standard Schema). No uncontrolled inputs.
- **All async components:** must have `<Skeleton>` loading state, error state, and empty state.
- **All route pages:** must have an error boundary.
- **Component library:** all UI from `@khetibadi/ui`. Do not install duplicate Shadcn components.

## Critical Pitfalls

- **NEVER** store the access token in localStorage or sessionStorage — XSS risk.
- **NEVER** call backend services directly from components — always go through the `api/` layer.
- **NEVER** use `useEffect` for data fetching — use TanStack Query.
- **NEVER** use `any` to silence TypeScript errors — fix the type.
- **NEVER** use `style={{}}` — use Tailwind.

## Dev Commands

```bash
cd apps/dashboard
bun run dev          # start Vite dev server on :3000
bun run build        # production build
bun run lint         # ESLint
bun run type-check   # tsc --noEmit
bun run test         # vitest
```

## Spec Reference

`openspec/specs/dashboard/spec.md`
