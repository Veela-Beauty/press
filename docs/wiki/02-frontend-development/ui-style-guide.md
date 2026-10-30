# UI Style Guide

## Color Palette

### Primary (Accurate Systems Blue)
- `#046BD2` — Primary actions, links, active sidebar items
- `#045CB4` — Hover states
- `#044D96` — Pressed/dark states
- `#3B9AE8` — Light accents

### Neutral (Dark)
- `#1E293B` — Sidebar background
- `#374151` — Body text on social buttons
- `#6B7280` — Secondary text
- `#9CA3AF` — Placeholder text, dividers

### Backgrounds
- `linear-gradient(135deg, #046BD2 0%, #197972 100%)` — Login page, landing page
- `#1E293B` — Sidebar
- `#FFFFFF` — Cards, content areas

## Typography

- Sidebar nav items: `13.5px` (custom), `#CBD5E1` on dark
- Body text: default frappe-ui sizing
- Login title: `text-2xl font-bold`
- Brand name: `text-lg font-bold`

**Give list text an explicit size.** The dashboard root sets no base font size (upstream
Frappe Cloud does not either), so text with no `text-*` class falls back to the browser's
16px. In frappe-ui's scale `text-xs` = 12px, `text-sm` = 13px, `text-base` = 14px,
`text-lg` = 16px. Lists use `text-base` for the name column and `text-sm` for the other cells
(benches list since 0.7.5: names were 16px next to 13px cells, which the user read as "too
bold"; removing `font-medium` did not help, the size did). When text looks too heavy,
measure the computed font-size before changing the weight.

**Pages are full width.** Data pages and object tabs do not sit in a centered `max-w-*`
column (10 pages changed in 0.7.3; Tessera's side margins went from 251 to 20 px).

## Components

### Sidebar
Since 0.7.2 the sidebar uses the prototype's solid colors (`AppSidebar.vue`,
`AppSidebarItem.vue`, `AppSidebarItemGroup.vue`). Translucent white text blended into the
slate and read "matte".
- Width `240px`, background `#1E293B` solid, right border `rgba(255,255,255,0.06)`
- Nav items and icons: `#CBD5E1` solid (not white at an opacity); group labels `#94A3B8`
- Active item: `#0B6BD3` background, white text and icon
- Hover: `rgba(255,255,255,0.06)` background, white text
- Item radius exactly `6px`: frappe-ui's `rounded` is 8px and `rounded-md` 10px, so set it explicitly
- Logo: white via `filter: brightness(0) invert(1)`

### Login Page
- Background: blue-to-teal gradient
- Decorative circles: `rgba(255,255,255,0.06-0.08)` radial gradients
- Logo: white, above the card on the gradient
- Card: `rounded-2xl`, white, `box-shadow: 0 20px 60px rgba(0,0,0,0.25)`
- Social buttons (Google, GitHub): side-by-side, `44px` height, `10px` radius, gray border
- "or" divider: gray lines with text centered
- Footer: `text-white/60`

### Form Elements (Dashboard-Wide)
- Inputs/selects: `36px` height, `6px` border-radius
- Buttons: `6px` border-radius
- Applied globally via `!important` in `style.css`

### Email
- Header: `#1E293B` background, white logo + title
- Body: standard frappe email layout
