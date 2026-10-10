# Youth Welfare SW

A youth welfare policy discovery and eligibility diagnosis frontend built with React, TypeScript, Vite, and Tailwind CSS.

## Development

~~~sh
pnpm install
pnpm dev
~~~

Create a production build with pnpm build.

## Source layout

- src/app contains the application shell and page selection.
- src/components contains shared branding, navigation, and policy status UI.
- src/data contains policy records.
- src/features contains the home, policy, diagnosis, and dashboard screens.
- src/services contains the backend API client.
- src/types contains shared route, policy, and API types.

## Static assets

There are currently no image or other public static assets in use, so `public/` and `src/assets/` are not present. Put assets imported by TypeScript components in `src/assets/`; put files that need a fixed URL and should be copied as-is in `public/`.

## Licensing

The repository includes an MIT license. Third party notices are listed in docs/THIRD_PARTY_NOTICES.md.
