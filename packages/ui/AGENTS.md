# AGENTS.md — packages/ui

> Shared React 19 component library. Consumed by apps/dashboard.
> Read root AGENTS.md first, then this file.

## Purpose

Reusable, unstyled-base UI components built on Shadcn/UI primitives + Tailwind CSS 4.
No business logic. No API calls. No Zustand. Pure presentational components.

## Layout

```
packages/ui/
├── src/
│   ├── index.ts                # re-exports all components
│   ├── components/
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── input.tsx
│   │   ├── skeleton.tsx
│   │   ├── toast.tsx
│   │   ├── badge.tsx
│   │   ├── dialog.tsx
│   │   ├── table.tsx
│   │   ├── chart.tsx           # Recharts wrapper
│   │   └── map-canvas.tsx      # Leaflet wrapper (lazy-loaded)
│   └── lib/
│       └── cn.ts               # clsx + tailwind-merge utility
├── package.json                # name: @khetibadi/ui, private: true
├── tsconfig.json               # composite: true
└── vite.config.ts              # library mode build
```

## Key Invariants

- **No business logic.** Components receive data via props and emit events via callbacks.
  They do NOT call APIs, read from Zustand, or import from `@khetibadi/types` domain types
  (only primitive prop types).
- **All components export a named export** (no default exports).
- **All components accept `className` prop** for Tailwind overrides from the consumer.
- **`cn()` utility is mandatory** for all className merging — never string concatenation.
- **Leaflet (`map-canvas.tsx`) must be lazy-loaded** — it cannot run in SSR/Node context.
  Use `React.lazy` + `<Suspense>` at the consumer level.
- **No `any` types.** Strict TypeScript throughout.
- **Peer dependencies only:** `react`, `react-dom`, `tailwindcss` are peerDeps, not deps.

## Component Contract

Every component must:
1. Have explicit TypeScript props interface (exported as `<Name>Props`).
2. Accept and forward `className` via `cn()`.
3. Have a loading/skeleton variant or accept a `loading` boolean prop where applicable.
4. Be accessible: correct ARIA roles, keyboard navigation, focus management.

## Adding New Components

1. Create `src/components/<name>.tsx`.
2. Export the component AND its props type.
3. Add to `src/index.ts`.
4. If it wraps a third-party lib, add that lib as a `peerDependency` in `package.json`.

## Dev Commands

```bash
cd packages/ui
bun run build        # vite build --mode library
bun run type-check   # tsc --noEmit
bun run lint         # eslint
```

## Consumers

- `apps/dashboard` — all UI components
