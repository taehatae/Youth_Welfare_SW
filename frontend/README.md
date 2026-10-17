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

The selected brand logo is stored in `src/assets/brand/youth-wordmark.png` and imported by `BrandLogo`. It is used in the navigation and home footer. Put component assets in `src/assets/`; use `public/` only for files that need a fixed public URL.

### 로고 편집 기록

- 사용자가 제공한 두 번째 로고 목록의 오른쪽 위 가로형을 선택했음.
- 내장 이미지 편집 도구로 투명 배경 PNG를 분리하고 작은 하단 슬로건을 제외했음.
- 크기: 1774 × 887, RGBA. 원본 목록의 디자인을 바탕으로 편집한 이미지이며 픽셀 단위의 원본 복사본은 아님.

<details>
<summary>편집에 사용한 프롬프트</summary>

Use case: background-extraction. Edit target: supplied six-logo contact sheet. Extract ONLY the TOP RIGHT horizontal wordmark, preserving its exact distinctive Korean letterforms, original blue-to-navy lettering '자격있', turquoise-green '청', the green two-leaf sprout above 청 and the tiny green sparkle at its right. Preserve the English 'For Youth' on the second line. Remove the small bottom Korean slogan entirely. Remove all five other logo designs and all white background. This is an extraction of the user's existing selected logo, NOT a redesign: do not change typography, spelling, proportions, gradients, leaf placement or colors. Output one clean high resolution transparent PNG with genuine alpha, tightly framed around this selected wordmark with only ~3% transparent margin. Horizontal canvas around 2:1 aspect, selected logo fills nearly all canvas. No shadows, no new symbols, no added text, no checkerboard baked into image.

</details>

## Licensing

The repository includes an MIT license. Third party notices are listed in docs/THIRD_PARTY_NOTICES.md.
