# Rebrand Guide

## Design Tokens

### Colors

| Token | Hex | CSS Variable | Usage |
|-------|-----|--------------|-------|
| Primary | `#046BD2` | `--blue-500` | Buttons, links, active states |
| Primary Light | `#3B9AE8` | `--blue-400` | Lighter accents |
| Primary Hover | `#045CB4` | `--blue-600` | Hover states |
| Primary Dark | `#044D96` | `--blue-700` | Pressed states |
| Sidebar BG | `#1E293B` | — | Dark sidebar background |
| Login Gradient Start | `#046BD2` | — | Login page gradient |
| Login Gradient End | `#197972` | — | Login page gradient (teal) |

### CSS Variable Overrides

All in `dashboard/src/assets/style.css`:

```css
:root {
  --blue-400: #3B9AE8;
  --blue-500: #046BD2;
  --blue-600: #045CB4;
  --blue-700: #044D96;
  --surface-blue-3: #046BD2;
  --ink-blue-2: #046BD2;
  --ink-blue-3: #045CB4;
  --ink-blue-link: #046BD2;
}
```

These override frappe-ui's default blue scale (`#0289F7`). frappe-ui generates its colors from `colors.json` via `colorPalette.js`, but `:root` overrides take precedence.

## Files Changed (Key)

### Global Styles
- **`dashboard/src/assets/style.css`** — Color overrides, form element sizing (36px height, 6px radius)

### Sidebar (Dark Theme)
- **`dashboard/src/components/AppSidebar.vue`** — Dark bg (`#1E293B`), white logo (`filter: brightness(0) invert(1)`), white text
- **`dashboard/src/components/AppSidebarItem.vue`** — White text, blue active state, `py-2` padding
- **`dashboard/src/components/AppSidebarItemGroup.vue`** — Same dark treatment for collapsible groups

### Login Page
- **`dashboard/src/components/auth/LoginBox.vue`** — Blue-teal gradient bg, white logo above card, `rounded-2xl` card
- **`dashboard/src/components/auth/SaaSLoginBox.vue`** — Same treatment for SaaS variant
- **`dashboard/src/pages/LoginSignup.vue`** — Google + GitHub social buttons, "or" divider, `redirectToGitHub` method

### Email
- **`press/templates/emails/base.html`** — Dark header (`#1E293B`), white logo, "Accurate Systems Cloud" title

### Logo
- **`dashboard/src/components/icons/FCLogo.vue`** — SVG logo component (used everywhere)
- White on dark: apply `filter: brightness(0) invert(1)` class
- Colored on white: use as-is

## How to Change the Brand Color

1. Edit `dashboard/src/assets/style.css` — update all `--blue-*` variables
2. Edit `AppSidebarItem.vue` line 50 — update `.as-nav-active` background
3. Edit `LoginBox.vue` and `SaaSLoginBox.vue` — update gradient start color
4. Build and deploy

## How to Change the Logo

1. Replace SVG content in `dashboard/src/components/icons/FCLogo.vue`
2. For email: update the `<img>` src URL in `press/templates/emails/base.html`
3. Build and deploy

## Form Element Sizing

Global in `style.css`:
- All inputs (text, email, password, etc.): `height: 36px`, `border-radius: 6px`
- All selects: same sizing
- All buttons: `border-radius: 6px`
- Excludes: checkboxes, radios, hidden inputs
