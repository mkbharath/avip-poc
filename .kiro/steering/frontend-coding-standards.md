---
inclusion: fileMatch
fileMatchPattern: "**/*.{ts,tsx}"
---

# Frontend Coding Standards (TypeScript/React)

## Formatting & Linting

- **Linter:** ESLint with TypeScript plugin
- **Type checking:** `tsc --noEmit` (strict mode enabled in tsconfig)
- **Formatting:** 2-space indent, single quotes for imports, semicolons
- Run before commit: `npm run lint`

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Components | PascalCase | `ScanScreen`, `OcrCaptureModal` |
| Component files | PascalCase.tsx | `ReviewWorkbench.tsx` |
| Hooks | camelCase with `use` prefix | `useInspection()` |
| Utility files | camelCase.ts | `client.ts`, `inspections.ts` |
| Interfaces/Types | PascalCase | `Inspection`, `DemoScenario` |
| Constants | UPPER_SNAKE_CASE | `OVERRIDE_REASONS`, `FAMILY_TO_FOLDER` |
| Props interfaces | `ComponentNameProps` | `OcrCaptureModalProps` |
| Event handlers | `handle` + action | `handleSubmit`, `handleCapture` |
| Boolean props/state | `is`/`has`/`show` prefix | `isOpen`, `hasError`, `showModal` |

## Component Structure

```tsx
// 1. Imports (React, third-party, app modules)
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getInspection } from "../../api/inspections";
import type { Inspection } from "../../types";

// 2. Types/interfaces for this component
interface Props {
  inspectionId: string;
  onClose: () => void;
}

// 3. Component (exported, named function)
export function MyComponent({ inspectionId, onClose }: Props) {
  // State declarations
  const [value, setValue] = useState("");

  // Queries/mutations
  const { data } = useQuery({ ... });

  // Derived values
  const isValid = value.length > 0;

  // Event handlers
  const handleSubmit = () => { ... };

  // Effects (minimal — prefer derived state)
  useEffect(() => { ... }, [dep]);

  // Render
  return ( ... );
}

// 4. Sub-components (unexported, same file if small)
function SubItem({ label }: { label: string }) {
  return <span>{label}</span>;
}
```

## TypeScript Rules

- **No `any`** — use `unknown` and narrow with type guards
- **No `as` casts** unless interfacing with untyped API responses
- When casting API responses: `as unknown as Record<string, unknown>`
- Define all API response shapes in `src/types/index.ts`
- Use discriminated unions for state machines:

```tsx
type Step = "capturing" | "inspecting" | "done";
```

- Prefer `interface` for object shapes, `type` for unions/intersections
- Always type function parameters and return values in API/utility functions

## React Patterns

### State Management
- **Server state:** React Query (`@tanstack/react-query`) — never useState for API data
- **UI state:** useState for local component state (modals, selections, form values)
- **No global state library** — pass props or use React Query cache

### Effects
- Minimize useEffect — prefer derived state and event handlers
- Always include cleanup for async effects
- Use `useRef` guards for StrictMode-safe one-time effects:

```tsx
const started = useRef(false);
useEffect(() => {
  if (started.current) return;
  started.current = true;
  doSomethingOnce();
}, []);
```

### Event Handlers
- Define inline only if trivial (`onClick={() => setOpen(true)}`)
- Extract to named functions if >1 line or reused

### Conditional Rendering
```tsx
// Prefer early return for loading/error states
if (isLoading) return <Spinner />;
if (error) return <ErrorMessage />;

// Use && for simple conditionals
{isOpen && <Modal />}

// Use ternary for two-branch
{isActive ? <Active /> : <Inactive />}
```

## Styling (Tailwind)

- Use Tailwind utility classes exclusively — no inline styles except dynamic values
- Dynamic styles via template literals:

```tsx
className={`px-4 py-2 rounded ${isActive ? "bg-avip-info text-white" : "bg-gray-200"}`}
```

- Use `clsx()` for complex conditional classes
- Component-specific custom styles in component file, not global CSS
- Touch targets: minimum `min-h-[48px] min-w-[48px]` on interactive elements
- Use design tokens: `avip-pass`, `avip-fail`, `avip-review`, `avip-info`

## API Integration

```tsx
// All API functions in src/api/*.ts
export async function getInspection(id: string) {
  return api.get<Inspection>(`/inspections/${id}`);
}

// Use in components via React Query
const { data, isLoading } = useQuery({
  queryKey: ["inspection", id],
  queryFn: () => getInspection(id),
  enabled: !!id,
});
```

- Query keys: `["resource"]` for lists, `["resource", id]` for details
- Mutations: `useMutation` with `onSuccess` for side effects (navigate, invalidate)
- Polling: `refetchInterval` option (return `false` to stop)

## Accessibility

- All images have `alt` text
- Interactive elements are `<button>` or `<a>` (not `<div onClick>`)
- Form inputs have associated `<label>` elements
- Modals have `aria-label` on close buttons
- Color is supplemented by icons/text (never sole indicator)
- Focus management: auto-focus primary input in modals/forms

## File Organization

- One primary component per file
- Small helper components can live in the same file (unexported)
- Extract to separate file when component exceeds ~100 lines or is reused
- Co-locate types with the component if component-specific
- Shared types go in `src/types/index.ts`
