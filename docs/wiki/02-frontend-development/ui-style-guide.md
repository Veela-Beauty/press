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

- Sidebar nav items: `13.5px` (custom), white on dark
- Body text: default frappe-ui sizing
- Login title: `text-2xl font-bold`
- Brand name: `text-lg font-bold`

## Components

### Sidebar
- Background: `#1E293B` solid
- Nav items: `py-2 px-2`, white text at 65% opacity
- Active item: `#046BD2` background, white text at 100%
- Hover: `rgba(255,255,255,0.08)` background
- Logo: white via `filter: brightness(0) invert(1)`
- Icons: white at 50% opacity, 80% on hover, 100% on active

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
