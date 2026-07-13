---
inclusion: fileMatch
fileMatchPattern: "**/*.tsx"
---

# Frontend Patterns & Conventions

## Component Structure

```
frontend/src/
├── components/
│   ├── kiosk/          # Operator station (dark theme, large touch targets)
│   ├── review/         # IQA workbench (light theme, data-dense)
│   ├── dashboard/      # Analytics (light theme, charts)
│   ├── demo/           # Presenter panel (dark theme)
│   ├── certificate/    # Certificate display/verify
│   └── common/         # Shared components
├── api/                # API client functions
├── hooks/              # Custom React hooks
├── types/              # TypeScript interfaces
├── styles/             # Tailwind globals
└── utils/              # Utility functions
```

## Theme Rules

- **Kiosk screens** (`/kiosk/*`): Dark background (`bg-gray-900`), large text, touch-friendly (min 48px targets)
- **Review workbench** (`/review/*`): Light background (`bg-gray-100`), data-dense, mouse-optimized
- **Dashboards** (`/dashboard/*`): Light background, card-based layout
- **Demo panel** (`/demo`): Dark background

## Color System (Tailwind)

| Token | Hex | Usage |
|---|---|---|
| `avip-pass` | #1E8E3E | Pass decisions, success states |
| `avip-fail` | #C0392B | Fail decisions, errors |
| `avip-review` | #E67E22 | Review/pending states |
| `avip-info` | #156082 | Primary actions, info states |
| `avip-pass-light` | #d4edda | Badge backgrounds |
| `avip-fail-light` | #f8d7da | Badge backgrounds |
| `avip-review-light` | #fff3cd | Badge backgrounds |

## Data Fetching

- Use `@tanstack/react-query` for all API calls
- Query keys follow pattern: `["resource", id?]`
- Mutations use `useMutation` with `onSuccess` for navigation/invalidation
- Polling: use `refetchInterval` when waiting for async results

## Common Patterns

### API Response Handling
```typescript
// API returns typed data; cast to Record for flexible access in components
const data = queryResult as unknown as Record<string, unknown>;
```

### Idempotent Effects (React StrictMode safe)
```typescript
const started = useRef(false);
useEffect(() => {
  if (started.current) return;
  started.current = true;
  // ... your effect
}, []);
```

### Decision-Based Styling
```typescript
const colorClass = {
  PASS: "bg-avip-pass",
  FAIL: "bg-avip-fail", 
  REVIEW: "bg-avip-review",
}[decision] || "bg-gray-500";
```

## Accessibility

- All interactive elements: min 48x48px touch target
- Color is never the sole indicator (always paired with icon/text)
- Form inputs have visible labels
- Modals trap focus and have close buttons with aria-label
