# Dashboard V2 — Test Cases

> **130 tests** across **11 test files** in **6 modules**
> Framework: Vitest + React Testing Library + jsdom
> Run: `npm test` (single) | `npm run test:watch` (watch)

---

## 1. Utils — `test/utils/format.test.js`

**Module under test:** `src/utils/format.js`
**Purpose:** Verify all currency formatting and channel name resolution utilities.

### 1.1 `fmtCcy(n, opts)` — Currency formatter with $ suffix

| # | Test | Purpose |
|---|------|---------|
| 1 | formats positive number with $ suffix | Verify `123.456` → `"123.46 $"` (2 decimal default) |
| 2 | formats negative number with - prefix | Verify `-42.7` → `"-42.70 $"` (negative sign before value) |
| 3 | formats zero | Verify `0` → `"0.00 $"` (zero case) |
| 4 | returns `0.00 $` for null | Guard: null input → safe fallback |
| 5 | returns `0.00 $` for undefined | Guard: undefined input → safe fallback |
| 6 | returns `0.00 $` for NaN | Guard: NaN input → safe fallback |
| 7 | compacts values >= 1000 to K | Verify `1500` → `"1.5K $"` (compact mode) |
| 8 | compacts negative values >= 1000 | Verify `-2500` → `"-2.5K $"` (negative compact) |
| 9 | disables compact when compact=false | Verify `1500` with `{compact:false}` → `"1500.00 $"` |
| 10 | uses custom decimals | Verify `{decimals:4}` → 4 decimal places |
| 11 | does not compact values < 1000 | Verify `999.99` stays as `"999.99 $"` |

### 1.2 `tickCcy(v)` — Short currency for chart axis ticks

| # | Test | Purpose |
|---|------|---------|
| 12 | formats >= 1000 as K (integer) | Axis label: `5000` → `"5K $"` |
| 13 | formats >= 100 as integer | Axis label: `150` → `"150 $"` (no decimals) |
| 14 | formats >= 1 with 1 decimal | Axis label: `3.75` → `"3.8 $"` |
| 15 | formats < 1 with 2 decimals | Axis label: `0.123` → `"0.12 $"` |
| 16 | handles negative values | Negative axis: `-500` → `"-500 $"` |
| 17 | returns `0 $` for null | Guard: null → `"0 $"` |

### 1.3 `tooltipCcy(v)` — Tooltip currency (always 2 decimals)

| # | Test | Purpose |
|---|------|---------|
| 18 | formats positive with 2 decimals | Tooltip: `12.345` → `"12.35 $"` |
| 19 | formats negative | Tooltip: `-7.5` → `"-7.50 $"` |
| 20 | returns `0.00 $` for null | Guard: null → safe fallback |

### 1.4 `buildChannelMap(channelList)` — Channel ID → name lookup

| # | Test | Purpose |
|---|------|---------|
| 21 | builds map from channel list | `[{id:123,name:'A'}]` → `{'123':'A'}` |
| 22 | uses stringified id as fallback | Missing name → uses ID string as name |
| 23 | returns empty object for null | Guard: null input → `{}` |
| 24 | returns empty object for empty array | Guard: `[]` → `{}` |

### 1.5 `resolveChannelName(channelId, channelMap)` — Display name resolution

| # | Test | Purpose |
|---|------|---------|
| 25 | returns mapped name | Known ID → returns human-readable name |
| 26 | returns shortened ID for long unknown ID | > 10 chars → `"…{last 8 chars}"` |
| 27 | returns full short ID for unknown channel | ≤ 10 chars → shows full ID |
| 28 | returns em-dash for null/empty | Guard: null/empty → `"—"` |
| 29 | returns shortened ID when map value = ID | Avoid displaying raw ID that matches key |

---

## 2. API Client — `test/api/client.test.js`

**Module under test:** `src/api/client.js`
**Purpose:** Verify URL construction, query params, auth headers, error handling, and HTTP methods.

### 2.1 URL Construction

| # | Test | Purpose |
|---|------|---------|
| 1 | api.overview calls `/api/overview` | Verify base endpoint URL |
| 2 | api.dailyPnl passes days param | Verify query string `?days=7` |
| 3 | api.trades skips empty params | Verify empty/null params excluded from URL |
| 4 | api.channelDailyPnl includes ID in path | Verify path param `/channels/{id}/daily-pnl` |
| 5 | api.signalDetail encodes fingerprint | Verify `encodeURIComponent` for special chars |

### 2.2 Error Handling

| # | Test | Purpose |
|---|------|---------|
| 6 | throws on non-OK response | Verify `fetch` 500 → throws `"API 500"` |

### 2.3 API Key Authentication

| # | Test | Purpose |
|---|------|---------|
| 7 | sends X-API-Key when set in localStorage | Verify header injection from localStorage |
| 8 | does not send X-API-Key when not set | Verify no header when key absent |

### 2.4 DELETE Methods

| # | Test | Purpose |
|---|------|---------|
| 9 | api.deleteSignal sends DELETE method | Verify HTTP method = DELETE |
| 10 | api.clearAll sends DELETE to correct path | Verify path + method for bulk delete |

### 2.5 `exportCsvUrl` (Synchronous URL Builder)

| # | Test | Purpose |
|---|------|---------|
| 11 | builds URL with params | Verify query string construction |
| 12 | returns base URL when no params | Verify clean URL without `?` |

---

## 3. Hooks — `test/hooks/useApi.test.jsx`

**Module under test:** `src/hooks/useApi.js`
**Purpose:** Verify all 17 TanStack React Query hooks bind to correct API methods with correct parameters.

| # | Hook | Test | Purpose |
|---|------|------|---------|
| 1 | `useOverview` | calls api.overview, returns data | Verify basic hook → API binding |
| 2 | `useDailyPnl(7)` | passes days parameter | Verify param forwarding |
| 3 | `useDailyPnl()` | defaults to 30 days | Verify default param |
| 4 | `useChannels` | calls api.channels | Verify hook registration |
| 5 | `useChannelDailyPnl(null)` | is disabled when id falsy | Verify `enabled: !!id` guard |
| 6 | `useChannelDailyPnl('ch1', 14)` | calls api with id + days | Verify dual param forwarding |
| 7 | `useTrades` | passes params object | Verify filter params forwarding |
| 8 | `useActive` | calls api.active | Verify hook registration |
| 9 | `useEquityCurve()` | defaults to 365 days | Verify default param |
| 10 | `useSymbolStats` | calls api.symbolStats | Verify hook registration |
| 11 | `useSymbols` | calls api.symbols | Verify no refetchInterval |
| 12 | `useChannelList` | calls api.channelList | Verify hook registration |
| 13 | `usePnlHeatmap(90)` | passes days param | Verify param forwarding |
| 14 | `useDrawdown(180)` | passes days param | Verify param forwarding |
| 15 | `usePnlDistribution` | calls api.pnlDistribution | Verify hook registration |
| 16 | `useSignals` | passes params object | Verify filter params forwarding |
| 17 | `useSignalDetail(null)` | disabled when falsy | Verify `enabled: !!fingerprint` |
| 18 | `useSignalDetail('fp123')` | calls api with fingerprint | Verify param forwarding |
| 19 | `useTableCounts` | calls api.tableCounts | Verify hook registration |
| 20 | `useSignalStatusCounts` | calls api.signalStatusCounts | Verify hook registration |

---

## 4. Charts — `test/charts/ChartPrimitives.test.jsx`

**Module under test:** `src/charts/ChartPrimitives.jsx`
**Purpose:** Verify shared chart tooltip/label components render correctly and handle edge cases.

### 4.1 `PremiumTooltip` — Shared glassmorphism tooltip

| # | Test | Purpose |
|---|------|---------|
| 1 | returns null when not active | No render when chart not hovered |
| 2 | returns null when payload empty | No render when no data points |
| 3 | renders label and payload rows | Verify tooltip structure with date + values |
| 4 | applies profit class for positive | Green styling for profit values |
| 5 | applies loss class for negative | Red styling for loss values |
| 6 | applies neutral class for zero | Neutral styling for zero values |
| 7 | uses custom formatter | Verify `formatter` prop is called |
| 8 | shows total when showTotal=true | Footer with sum of all payload values |

### 4.2 `BarLabel` — Value label above/below bars

| # | Test | Purpose |
|---|------|---------|
| 9 | returns null for value=0 | No label on zero-value bars |
| 10 | returns null for value=null | Guard: null value |
| 11 | formats >= 1000 as `k` | Compact: `1500` → `"1.5k"` |
| 12 | formats small value with 1 decimal | `42.67` → `"42.7"` |
| 13 | positions above bar for positive | `y = y - 6` for positive bars |
| 14 | positions below bar for negative | `y = y + 16` for negative bars |

### 4.3 `PieLabel` — Percentage label outside pie slices

| # | Test | Purpose |
|---|------|---------|
| 15 | returns null when < 5% | Skip tiny slices to avoid clutter |
| 16 | renders label for visible slices | Verify name + percent text |
| 17 | sets textAnchor by position | `'start'` when right of center, `'end'` when left |

---

## 5. Components — `test/components/`

### 5.1 `ChartCard` — `test/components/ChartCard.test.jsx`

**Module under test:** `src/components/ChartCard.jsx`
**Purpose:** Verify card rendering, loading skeleton, and action slot.

| # | Test | Purpose |
|---|------|---------|
| 1 | renders title | Card header shows title text |
| 2 | renders children when not loading | Content slot visible |
| 3 | shows skeleton when loading | Skeleton placeholder replaces content |
| 4 | renders actions when provided | Action buttons in header |
| 5 | applies custom className | CSS class forwarding |

### 5.2 `ConfirmModal` — `test/components/ConfirmModal.test.jsx`

**Module under test:** `src/components/ConfirmModal.jsx`
**Purpose:** Verify modal open/close, type-to-confirm guard, and callback invocation.

| # | Test | Purpose |
|---|------|---------|
| 1 | renders nothing when open=false | Modal hidden by default |
| 2 | renders content when open=true | Title + message visible |
| 3 | Cancel calls onClose | Cancel button triggers close callback |
| 4 | Confirm calls both callbacks | Confirm triggers onConfirm + onClose |
| 5 | disables confirm until phrase matches | Type-to-confirm guard active |
| 6 | enables confirm when typed matches | Guard releases when input = phrase |
| 7 | renders danger level colors | Default level = danger styling |

### 5.3 `Navbar` — `test/components/Navbar.test.jsx`

**Module under test:** `src/components/Navbar.jsx`
**Purpose:** Verify navigation link rendering, brand text, and route targets.

| # | Test | Purpose |
|---|------|---------|
| 1 | renders brand text | "Forex Bot" + "V2" visible |
| 2 | renders all 7 navigation links | All page links present |
| 3 | renders Live status indicator | Status dot + "Live" text |
| 4 | has correct link hrefs | Overview → `/`, Analytics → `/analytics` |

### 5.4 `SparkCard` — `test/components/SparkCard.test.jsx`

**Module under test:** `src/components/SparkCard.jsx`
**Purpose:** Verify KPI card rendering, sparkline chart types, and color fallback.

| # | Test | Purpose |
|---|------|---------|
| 1 | renders title and value | KPI label + big number visible |
| 2 | renders subtitle when provided | Subtitle text appears |
| 3 | does not render subtitle when absent | No extra elements |
| 4 | renders chart when sparkData given | ResponsiveContainer present |
| 5 | no chart when sparkData empty | No chart rendered |
| 6 | falls back to blue for unknown color | Invalid color → default blue |
| 7 | uses bar chart for sparkType=bar | BarChart component selected |
| 8 | uses line chart for sparkType=line | LineChart component selected |

### 5.5 `StatCard` — `test/components/StatCard.test.jsx`

**Module under test:** `src/components/StatCard.jsx`
**Purpose:** Verify stat card rendering, change indicators, and icon rendering.

| # | Test | Purpose |
|---|------|---------|
| 1 | renders label and value | Stat label + value visible |
| 2 | renders icon | Icon component rendered |
| 3 | shows ▲ for positive change | Profit indicator arrow |
| 4 | shows ▼ for negative change | Loss indicator arrow |
| 5 | hides change when undefined | No change element if prop absent |
| 6 | applies color class | Color theme forwarding |

---

## 6. Pages — `test/pages/`

### 6.1 Overview Helpers — `test/pages/Overview.helpers.test.js`

**Functions under test:** Data transforms extracted from `src/pages/Overview.jsx`
**Purpose:** Verify aggregation/merge logic used by Overview charts, isolated from React rendering.

#### `aggregateByWeekday` — PnL by Weekday chart data

| # | Test | Purpose |
|---|------|---------|
| 1 | aggregates PnL by weekday | Mon-Fri grouping with correct sum |
| 2 | returns zeros for empty data | Guard: no data → 5 zero entries |
| 3 | skips entries without date | Guard: missing date field |
| 4 | accumulates same weekday across weeks | Two Mondays → summed PnL |

#### `mergeDailyAndEquity` — ComboPnlChart overlay merge

| # | Test | Purpose |
|---|------|---------|
| 5 | merges by date | Daily + equity joined on `date` key |
| 6 | null cumulative for unmatched dates | Missing equity → `null` |
| 7 | handles null inputs | Guard: null arrays → `[]` |

#### `aggregateMonthly` — Monthly Win/Loss grouped bars

| # | Test | Purpose |
|---|------|---------|
| 8 | groups by month | Win/loss split per month |
| 9 | returns empty for empty data | Guard: `[]` → `[]` |
| 10 | limits to last 6 months | Sliding window of 6 months |

### 6.2 Analytics Helpers — `test/pages/Analytics.helpers.test.js`

**Functions under test:** Data transforms extracted from `src/pages/Analytics.jsx`
**Purpose:** Verify aggregation, bucketing, and calculation logic used by Analytics charts.

#### `aggregateWeekly` — Win/Loss stacked bars

| # | Test | Purpose |
|---|------|---------|
| 1 | groups by ISO week | Same-week entries combined |
| 2 | returns empty for empty data | Guard: `[]` → `[]` |
| 3 | limits to last 12 weeks | Sliding window cap |

#### `buildHistogram` — PnL distribution

| # | Test | Purpose |
|---|------|---------|
| 4 | buckets data with size 50 | Round to nearest 50 bucket |
| 5 | returns empty for empty data | Guard: `[]` → `[]` |
| 6 | sorts by bucket ascending | Output ordered low → high |

#### `calculateDrawdown` — Drawdown from equity peak

| # | Test | Purpose |
|---|------|---------|
| 7 | calculates drawdown from peak | Peak tracking + percentage calculation |
| 8 | drawdown always <= 0 | Invariant: never positive |
| 9 | handles all-zero data | Edge: no equity → 0% drawdown |
| 10 | handles missing cumulative_pnl | Guard: undefined → treat as 0 |

#### `enrichWithCumulative` — Trading activity running total

| # | Test | Purpose |
|---|------|---------|
| 11 | adds cumulative trade count | Running sum: 3, 8, 10 |
| 12 | handles missing trades as 0 | Guard: undefined → 0 |
