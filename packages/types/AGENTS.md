# AGENTS.md — packages/types

> TypeScript shared types. Imported by apps/dashboard and packages/ui.
> Read root AGENTS.md first, then this file.

## Purpose

Single source of truth for TypeScript types shared across the frontend monorepo.
No runtime code — types and Zod schemas only.

## Layout

```
packages/types/
├── src/
│   ├── index.ts                # re-exports everything
│   ├── auth.ts                 # User, AuthTokens, LoginRequest, RegisterRequest
│   ├── farm.ts                 # Farm, SoilSample, WeatherData, GeoJSONPolygon
│   ├── market.ts               # MarketPrice, PriceAlert, Commodity
│   ├── ml.ts                   # CropRecommendation, YieldPrediction, FertilizerRecommendation
│   ├── vision.ts               # DiseaseDetectionResult, DetectionJob
│   ├── chat.ts                 # ChatSession, ChatMessage, SSETokenEvent, SSEDoneEvent
│   └── api.ts                  # ApiResponse<T>, PaginatedResponse<T>, ApiError
├── package.json                # name: @khetibadi/types, private: true
└── tsconfig.json               # composite: true, declaration: true, emitDeclarationOnly: true
```

## Key Invariants

- **No runtime imports.** This package must have zero dependencies (no axios, no react, no zod).
  Types only — `interface`, `type`, `enum` (avoid enums — prefer `as const` unions).
- **`as const` unions over enums:**
  ```typescript
  // CORRECT
  export const CROP_TYPES = ["rice", "wheat", "maize"] as const;
  export type CropType = typeof CROP_TYPES[number];
  // WRONG
  export enum CropType { Rice = "rice", ... }
  ```
- **`ApiResponse<T>` shape must match backend envelope exactly:**
  ```typescript
  export interface ApiResponse<T> { data: T; }
  export interface PaginatedResponse<T> { data: T[]; meta: PaginationMeta; }
  export interface ApiError { error: string; message: string; }
  export interface PaginationMeta { page: number; limit: number; total: number; }
  ```
- **GeoJSON types:** use `GeoJSONPolygon` from this package — do not import `@types/geojson`
  in the dashboard directly.
- **All types exported from `src/index.ts`.** Consumers import from `@khetibadi/types`, never
  from deep paths like `@khetibadi/types/src/farm`.

## Adding New Types

1. Add to the appropriate file (or create a new file if it's a new domain).
2. Re-export from `src/index.ts`.
3. Run `bun run type-check` in `apps/dashboard` to verify no breakage.

## Dev Commands

```bash
cd packages/types
bun run build        # tsc --emitDeclarationOnly
bun run type-check   # tsc --noEmit
```

## Consumers

- `apps/dashboard` — all API response types
- `packages/ui` — prop types for data-display components
