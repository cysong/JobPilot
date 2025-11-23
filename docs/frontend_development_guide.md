# Frontend Development Guide & Standards

This document outlines the standard workflow, component usage, and styling guidelines for the JobPilot frontend, based on our `shadcn/ui` + `Tailwind CSS` architecture.

## 1. Development Workflow (How to create a new page)

Follow these steps when adding a new feature or page:

### Step 1: Define the Route
Add the new route in `src/App.tsx`.
- Use **Public Routes** for auth pages (Login/Register).
- Use **Protected Routes** for authenticated features (Dashboard, Jobs).

### Step 2: Create the Page Component
Create your page in `src/features/<feature_name>/<PageName>.tsx`.
- **Example**: `src/features/jobs/JobListing.tsx`

### Step 3: Define Validation Schema (Zod)
Always use **Zod** for form validation. Define the schema in the same file or a separate `schemas.ts` if complex.
```tsx
const formSchema = z.object({
  title: z.string().min(1, "Title is required"),
  // ...
})
```

### Step 4: Build the UI with `shadcn/ui`
Compose the UI using existing components from `src/components/ui`.
- **Layout**: Use `Card` for content containers.
- **Forms**: Use `Form`, `FormField`, `Input`, `Button`.
- **Feedback**: Use `Alert` for block errors, `Toast` for success messages.

### Step 5: Integrate State & API
- Use **React Query** (via custom hooks in `src/api/`) for data fetching.
- Use **Zustand** (in `src/store/`) for global client state (like Auth).

---

## 2. Component Standards

### "Do I need to copy everything to `components/ui`?"
**YES.**
`shadcn/ui` is **NOT** a component library you install (like MUI or AntD). It is a collection of reusable components that you **copy and paste** into your project.

- **If you need a component (e.g., Select, Dialog, Checkbox):**
  1.  Check if it exists in `src/components/ui/`.
  2.  If **YES**: Import and use it.
  3.  If **NO**: You must add it.
      - **Preferred**: Run `npx shadcn@latest add <component_name>` (e.g., `npx shadcn@latest add select`).
      - **Manual**: Copy the code from [ui.shadcn.com](https://ui.shadcn.com) into a new file in `src/components/ui/`.

### Core Components List (Current)
These are already available in `src/components/ui/`:
- `Button` (Primary, Secondary, Ghost, Destructive variants)
- `Input` (Text fields)
- `Label` (Form labels)
- `Card` (Container with Header, Content, Footer)
- `Form` (React Hook Form wrapper)
- `Alert` (In-page error banners)
- `Toast` (Popup notifications)

---

## 3. Styling & Aesthetics

### Design System
- **Framework**: Tailwind CSS.
- **Theme**: "Modern PaaS" (Clean, Professional, Airy).
- **Primary Color**: Indigo-600 (`bg-indigo-600`, `text-indigo-600`).
- **Backgrounds**:
  - Page: `bg-slate-50` (Light Gray)
  - Cards/Containers: `bg-white` + `shadow-sm` or `shadow-md`

### Common Patterns

**1. Page Layout**
```tsx
<div className="min-h-screen bg-slate-50 p-4">
  <div className="max-w-7xl mx-auto">
    {/* Content */}
  </div>
</div>
```

**2. Cards**
```tsx
<Card className="shadow-sm border-slate-200">
  <CardHeader>
    <CardTitle>Title</CardTitle>
  </CardHeader>
  <CardContent>...</CardContent>
</Card>
```

**3. Error Handling (The "JobPilot Standard")**
- **Field Errors**: Use `FormMessage` (appears below input).
- **Form/Page Errors**: Use `Alert` (appears at top of form).
  ```tsx
  {error && (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>{error}</AlertDescription>
    </Alert>
  )}
  ```
- **Success/System Events**: Use `toast`.
  ```tsx
  toast({ title: "Success", description: "Saved successfully." })
  ```

---

## 4. Checklist for New Pages
- [ ] Route added to `App.tsx`?
- [ ] Page component created in `features/`?
- [ ] Zod schema defined?
- [ ] `shadcn/ui` components used (no raw HTML inputs)?
- [ ] Error handling implemented (Alert + Toast)?
- [ ] Responsive? (Check mobile view)
