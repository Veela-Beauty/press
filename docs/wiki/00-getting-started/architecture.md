# Architecture

## Servers

| Server | IP | Alias | Role |
|--------|-----|-------|------|
| Press Controller | 89.167.116.92 | `press-ctrl` | Frappe bench, Press app, Docker registry, dashboard |
| App Server | 89.167.57.21 | `press-f1` | Standalone server, runs tenant sites in Docker |

## DNS (Cloudflare)

- `demo.mvpstorm.com` → Server 1 (Press dashboard)
- `*.demo.mvpstorm.com` → Server 2 (tenant sites)
- `demo.sandbox.mvpstorm.com` → Server 1 (demo landing page)

## Dashboard Architecture

```
dashboard/
├── src/
│   ├── assets/
│   │   └── style.css              ← Global CSS overrides (colors, form sizing)
│   ├── components/
│   │   ├── AppSidebar.vue         ← Dark sidebar container, white logo
│   │   ├── AppSidebarItem.vue     ← Nav item (dark theme, active=blue)
│   │   ├── AppSidebarItemGroup.vue← Collapsible group (dark theme)
│   │   ├── ObjectList.vue         ← List view with search + filters
│   │   ├── ObjectListFilters.vue  ← Filter dropdowns wrapper
│   │   ├── FilterControl.vue      ← Individual filter (uses frappe-ui FormControl)
│   │   ├── auth/
│   │   │   ├── LoginBox.vue       ← Login wrapper (gradient bg, white logo)
│   │   │   └── SaaSLoginBox.vue   ← SaaS login variant (same treatment)
│   │   └── icons/
│   │       └── FCLogo.vue         ← SVG logo component
│   ├── pages/
│   │   └── LoginSignup.vue        ← Login/signup form (social buttons, OTP)
│   └── ...
├── index.html
└── vite.config.js
```

## Build Pipeline

1. Vue SPA built by Vite (`cd dashboard && yarn build`)
2. Output goes to `press/public/dashboard/`
3. Frappe serves it via Nginx
4. `bench build --force --app press` triggers the full pipeline
5. `bench clear-cache` clears server-side cache
6. `supervisorctl restart` picks up new assets

## Deploy Flow

```
Local (VSCode) → git push fork cloudflare-dns
                           ↓
Server (press-ctrl) → git pull upstream cloudflare-dns
                           ↓
                    bench build --force --app press
                           ↓
                    bench --site demo.mvpstorm.com clear-cache
                           ↓
                    supervisorctl restart frappe-bench-web:*
```
