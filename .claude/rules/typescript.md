# TypeScript Rules — Next.js & React

## TypeScript

- `strict: true` is enabled in `tsconfig.json`. Do not weaken it.
- **No `any`.** Use `unknown` and narrow the type, or define a proper interface.
  ```ts
  // BAD
  const data: any = await res.json();

  // GOOD
  const data = await res.json() as ChatResponse;
  ```
- Export types/interfaces that are shared across files. Keep component-local types inline.
- Prefer `interface` for object shapes, `type` for unions and aliases.

## Next.js App Router

- API routes live in `app/api/<resource>/route.ts`. One file per resource.
- All API route handlers must be `async` and return a `Response` object.
- **Never** use `fetch` from a client component to call an internal API route that could instead
  be a Server Component or Server Action.
- The streaming proxy in `route.ts` must pipe the body with `TransformStream` — do not buffer.
- Set `X-Accel-Buffering: no` and `Cache-Control: no-cache` on all streaming responses.

## React Components

- **One component per file.** Export a named export and an `index.ts` barrel.
  ```
  components/ChatBox/ChatBox.tsx   ← implementation
  components/ChatBox/index.ts      ← re-export
  ```
- Components must be typed. No implicit `children: any`.
  ```ts
  interface Props {
    onSubmit: (message: string) => void;
  }
  ```
- Keep components presentational. Move data-fetching and streaming logic to hooks or the
  parent page component.
- Do not inline large JSX blocks — extract sub-components when a render function exceeds
  ~50 lines.

## Styling

- Tailwind CSS is the primary styling tool. Use MUI components for complex interactive widgets.
- Do not mix inline `style={{}}` props with Tailwind on the same element.
- Avoid `!important` overrides in `globals.css`.

## State & Side Effects

- Use `useState` + `useEffect` for local UI state. Do not reach for a global store for
  component-local concerns.
- Streaming: consume the `ReadableStream` in a `useEffect` cleanup-aware loop. Always abort
  the fetch on component unmount:
  ```ts
  const controller = new AbortController();
  fetch(url, { signal: controller.signal });
  return () => controller.abort();
  ```

## Linting

- Run `npm run lint` before every commit.
- Do not suppress ESLint rules with `// eslint-disable` without a documented reason in the
  same comment.
