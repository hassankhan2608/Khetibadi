# Dashboard UI Specification

## Purpose

Provide a responsive, data-rich single-page application for farmers to access all
Khetibadi v2 features: farm management, crop/yield/fertilizer predictions, plant
disease detection, live market prices, and AI chat assistance.

Built with React 19 + Vite 8 + TanStack Router (file-based typed routing) +
TanStack Query v5 + Shadcn/UI + Tailwind CSS 4.

---

## Requirements

### Requirement: Authentication Flow

The system MUST enforce authentication on all routes except `/login` and `/register`.

#### Scenario: Unauthenticated User Access

- GIVEN an unauthenticated user navigates to any protected route (e.g., `/dashboard`)
- WHEN TanStack Router evaluates the route guard (beforeLoad context check)
- THEN the user is redirected to `/login` with `?redirect=<original_path>`

#### Scenario: Login Success

- GIVEN a user submits valid credentials on `/login`
- WHEN POST /auth/login returns HTTP 200 with access token + sets refresh cookie
- THEN the access token is stored in memory (Zustand `authStore`)
- AND the user is redirected to `/dashboard` or the `?redirect` path

#### Scenario: Token Expiry During Session

- GIVEN a user is on `/dashboard` and their 15-minute access token expires
- WHEN any TanStack Query mutation or query fails with HTTP 401
- THEN the Axios interceptor automatically calls POST /auth/refresh
- AND if the refresh succeeds, the original request is retried transparently
- AND if the refresh fails, the user is redirected to `/login`

#### Scenario: Registration

- GIVEN a new user fills the registration form (`/register`)
- WHEN POST /auth/register returns HTTP 201
- THEN the user is redirected to `/login` with a success toast

---

### Requirement: Dashboard Home Page (`/dashboard`)

The system MUST display a summary overview of the user's farm activity on the home page.

#### Scenario: Dashboard Load

- GIVEN an authenticated user with 2 farms
- WHEN the user navigates to `/dashboard`
- THEN the page displays:
  - **Stats row:** Total Farms count, Total Farm Area (ha), Active Alerts count, Crop Varieties tracked
  - **Weather card:** Current weather at primary farm (temperature, humidity, wind, rainfall)
  - **Market highlights:** Top 5 commodity prices for user's tracked crops (with % change from yesterday)
  - **Recent activity feed:** Last 5 actions (soil sample added, disease scan, chat session started)
  - **Quick actions:** "Scan Disease", "Check Crop", "View Market", "Chat with AI" CTA buttons

#### Scenario: No Farms Yet

- GIVEN an authenticated user with 0 farms
- WHEN the user navigates to `/dashboard`
- THEN an empty state is shown: "You haven't added any farms yet" + "Add Your First Farm" CTA button

---

### Requirement: Farm Map Page (`/dashboard/farm-map`)

The system MUST provide an interactive GIS map for viewing and managing farm boundaries.

#### Scenario: View Farm Boundaries

- GIVEN a user with 3 farms
- WHEN the user navigates to `/dashboard/farm-map`
- THEN a Leaflet map is displayed centered on the average centroid of all farms
- AND each farm boundary polygon is drawn as a filled overlay with the farm name label
- AND clicking a polygon opens a side panel with farm details (name, area, soil type, last soil sample date)

#### Scenario: Add New Farm

- GIVEN the user clicks "Draw Farm Boundary"
- WHEN Leaflet-Draw toolbar is activated and the user draws a polygon
- THEN a "Save Farm" dialog appears with fields: Name, Soil Type, Primary Crop
- AND on submit, POST /farms is called with the GeoJSON polygon
- AND on success, the map re-renders with the new farm boundary and a success toast

#### Scenario: Invalid Polygon

- GIVEN the user draws a self-intersecting polygon
- WHEN the form is submitted
- THEN the API returns HTTP 422 and the error is displayed inline: "Farm boundary cannot self-intersect"

#### Scenario: Edit Farm

- GIVEN a farm polygon is selected
- WHEN the user clicks "Edit Boundary"
- THEN Leaflet-Draw edit mode is activated for that polygon
- AND on save, PUT /farms/{id} is called with the updated GeoJSON

#### Scenario: Soil Samples Overlay

- GIVEN the user toggles "Show Soil Samples" layer control
- WHEN the toggle is on
- THEN soil sample markers appear as pins on the map at their GPS coordinates
- AND hovering a pin shows a tooltip: pH, N/P/K values, sample date

---

### Requirement: Crop Advisor Page (`/dashboard/crop-advisor`)

The system MUST provide a form-based interface for crop recommendation and yield prediction.

#### Scenario: Crop Recommendation

- GIVEN the user navigates to `/dashboard/crop-advisor`
- WHEN the user fills the soil & weather form (N, P, K, Temperature, Humidity, pH, Rainfall)
  - Pre-fill option: "Use values from farm {name}" pulls latest soil sample
- AND submits the form
- THEN POST /ml/crop/recommend is called
- AND the result is displayed as:
  - Top recommended crop (large card with crop image)
  - Top 3 alternatives (smaller cards with confidence %)
  - Feature importance bar chart (Recharts horizontal bar)

#### Scenario: Yield Prediction

- GIVEN the user selects the "Yield Forecast" tab on the same page
- WHEN the user fills: State, District, Season, Crop, Area (ha), Year
- AND submits the form
- THEN POST /ml/crop/yield is called
- AND the result shows:
  - Estimated yield (t/ha) as a large metric
  - Total production (tonnes) = yield × area
  - Confidence interval range (± CI)
  - Low-confidence warning banner if the model confidence is low

#### Scenario: Fertilizer Recommendation

- GIVEN the user selects the "Fertilizer" tab
- WHEN the user fills: Temperature, Humidity, Moisture, Soil Type, Crop Type, N, P, K
- THEN POST /ml/crop/fertilizer is called
- AND the result shows the recommended fertilizer + 2 alternatives as cards

---

### Requirement: Disease Scanner Page (`/dashboard/disease-scan`)

The system MUST provide an image upload interface for plant disease detection.

#### Scenario: Image Upload and Detection

- GIVEN the user navigates to `/dashboard/disease-scan`
- WHEN the user drags or selects an image (JPG/PNG, max 10MB)
- THEN a preview of the image is shown
- AND the user clicks "Scan for Disease"
- THEN POST /ml/vision/detect is called with the image as multipart form data
- AND a loading spinner with "Analyzing plant image..." is shown during inference
- AND the result is displayed as:
  - Annotated image (base64 overlay with bounding box and label)
  - Disease name + confidence % (large badge)
  - Severity indicator (low/medium/high based on confidence)
  - Treatment recommendations (static text per disease class)

#### Scenario: Low Confidence Result

- GIVEN the model returns confidence < 0.60
- WHEN the result is rendered
- THEN a yellow warning banner: "Low confidence result — please try a clearer photo"
- AND the predicted class is still shown with its confidence

#### Scenario: Invalid File Format

- GIVEN the user selects a PDF file
- WHEN the file picker validates the selection
- THEN an inline error: "Only JPG and PNG images are supported" (no API call is made)

#### Scenario: Async Detection (Large Image)

- GIVEN the image is large (>2MB) and async mode is triggered
- WHEN POST /ml/vision/detect?async=true returns `{ "job_id": "..." }`
- THEN the UI shows a "Processing in background..." state with a progress spinner
- AND polls GET /ml/vision/jobs/{job_id} every 3 seconds
- AND renders the result when status = "completed"

---

### Requirement: Market Prices Page (`/dashboard/market-prices`)

The system MUST display live commodity prices with filtering and historical charts.

#### Scenario: Price Table View

- GIVEN the user navigates to `/dashboard/market-prices`
- WHEN GET /market/prices is called with default filters
- THEN a searchable, sortable table (TanStack Table) is shown with columns:
  Commodity | Market | State | Min Price | Max Price | Modal Price | Date | Cache status (X-Cache)

#### Scenario: Filter and Search

- GIVEN the user types "Wheat" in the search box
- WHEN the table filters
- THEN only rows where commodity contains "Wheat" are shown (client-side filter)

#### Scenario: Historical Price Chart

- GIVEN the user clicks "View History" on a commodity row
- WHEN GET /market/prices/history?commodity=Wheat&market=Delhi&days=30 is called
- THEN a Recharts line chart appears in a modal showing:
  - X-axis: date
  - Y-axis: modal price (₹/quintal)
  - 30/90/180 day range selector buttons

#### Scenario: Price Alert Creation

- GIVEN the user clicks "Set Alert" on a commodity row
- WHEN the alert dialog opens
- THEN the user can set: threshold price, condition (above/below)
- AND on submit, POST /market/alerts is called
- AND success toast: "Alert created for {Commodity} in {Market}"

---

### Requirement: AI Chat Page (`/dashboard/ai-assistant`)

The system MUST provide a chat interface for the AI agricultural assistant.

#### Scenario: Chat Interface Layout

- GIVEN the user navigates to `/dashboard/ai-assistant`
- THEN the page shows:
  - Left sidebar: list of past chat sessions (title, last message preview, date)
  - Main area: chat message thread with user and assistant messages
  - Input area: text box + send button + "New Chat" button

#### Scenario: New Chat Session

- GIVEN the user clicks "New Chat"
- WHEN POST /ai/chat/sessions is called
- THEN a new session is created and selected in the sidebar
- AND the main chat area is cleared

#### Scenario: Sending a Message with Streaming

- GIVEN an active session
- WHEN the user types a message and presses Enter (or clicks Send)
- THEN the user message is immediately appended to the thread (optimistic UI)
- AND POST /ai/chat/sessions/{id}/messages is called (SSE endpoint)
- AND a typing indicator (animated dots) is shown for the assistant
- AND as `event: token` SSE events arrive, the assistant message progressively renders
- AND on `event: done`, the typing indicator is removed and the full message is saved

#### Scenario: Load Past Session

- GIVEN the user clicks a past session in the left sidebar
- WHEN GET /ai/chat/sessions/{id}/messages is called
- THEN the chat history is loaded and rendered in the main area (oldest first, newest at bottom)
- AND the view auto-scrolls to the bottom

#### Scenario: Stream Error

- GIVEN the Groq API fails mid-stream
- WHEN `event: error` is received
- THEN the partial assistant message is discarded
- AND a red error toast: "AI service unavailable, please try again"

---

### Requirement: Settings Page (`/dashboard/settings`)

The system MUST provide a settings page for account and preference management.

#### Scenario: Profile Settings

- GIVEN the user navigates to `/dashboard/settings`
- THEN the page shows:
  - Profile: name, email (read-only), created_at
  - Change Password form (current password, new password, confirm)
  - Language preference: English / Hindi (stored in localStorage)
  - Notification preferences: price alert notifications on/off

#### Scenario: Password Change

- GIVEN the user fills the change password form correctly
- WHEN POST /auth/password/change is called
- THEN success toast: "Password updated successfully"

#### Scenario: Delete Account (Placeholder)

- GIVEN the user clicks "Delete Account"
- THEN a confirmation dialog warns: "This action cannot be undone"
- AND the feature is marked as "coming soon" (disabled button) in v2.0

---

## Route Structure (TanStack Router)

```
/                        → redirect to /dashboard
/login                   → LoginPage (public)
/register                → RegisterPage (public)
/dashboard               → DashboardLayout (authenticated)
  /                      → DashboardHomePage
  /farm-map              → FarmMapPage
  /crop-advisor          → CropAdvisorPage (tabs: recommend / yield / fertilizer)
  /disease-scan          → DiseaseScanPage
  /market-prices         → MarketPricesPage
  /ai-assistant          → AIChatPage
  /settings              → SettingsPage
```

---

## Page State Management Pattern

Each feature page MUST follow the context-hook pattern from the FlosBridge reference:

```
Page
  └── FeatureProvider (React Context)
        └── useFeatureContext (custom hook)
              └── Components (consume hook)
```

- **TanStack Query** for all server state (fetching, caching, mutations)
- **Zustand** for global client state (auth tokens, UI preferences, sidebar state)
- **React Hook Form + Zod** for all forms with schema-driven validation

---

## Component Library Usage (`@khetibadi/ui`)

All UI components MUST be sourced from `@khetibadi/ui` (Shadcn/UI based):

| Component | Usage |
|-----------|-------|
| `<Button>` | All CTAs |
| `<Card>`, `<CardHeader>`, `<CardContent>` | Stats, results, farm details |
| `<Dialog>` | Modals (alerts, confirmations) |
| `<Form>`, `<FormField>`, `<FormMessage>` | All React Hook Form forms |
| `<Table>` | Market prices, soil samples |
| `<Tabs>` | Crop advisor multi-tab layout |
| `<Sonner>` (toast) | All success/error feedback |
| `<Skeleton>` | Loading states for all async content |
| `<Badge>` | Confidence levels, disease severity |
| `<Separator>` | Section dividers |

---

## Responsive Design Requirements

The system MUST be usable on both desktop and mobile devices.

- Breakpoints follow Tailwind CSS 4 defaults (sm:640, md:768, lg:1024, xl:1280)
- The farm map page MUST have a minimum height of 400px on mobile
- The AI chat sidebar collapses to a bottom sheet on mobile (`sm:` breakpoint)
- All tables MUST horizontally scroll on mobile rather than truncate columns
- Form inputs MUST be full-width on mobile

---

## Error Boundary Requirements

The system MUST handle unexpected errors gracefully.

#### Scenario: Component Crash

- GIVEN a React component throws an unhandled exception
- WHEN the error boundary catches it
- THEN a fallback UI is shown: "Something went wrong" + "Reload Page" button
- AND the error is logged to the console (Sentry integration in future)

---

## Loading & Empty States

Every data-fetching component MUST implement:

1. **Loading state:** `<Skeleton>` placeholders that match the shape of the loaded content
2. **Error state:** Error card with retry button
3. **Empty state:** Descriptive message + CTA to add first item

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `VITE_AUTH_URL` | Auth service base URL (e.g., http://localhost:8000) |
| `VITE_FARM_URL` | Farm service base URL (e.g., http://localhost:8001) |
| `VITE_MARKET_URL` | Market service base URL (e.g., http://localhost:8002) |
| `VITE_ML_CROP_URL` | ML crop service base URL (e.g., http://localhost:8010) |
| `VITE_ML_VISION_URL` | ML vision service base URL (e.g., http://localhost:8011) |
| `VITE_AI_CHAT_URL` | AI chat service base URL (e.g., http://localhost:8012) |
