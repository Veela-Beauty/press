# Overview

## What This Is

A white-labeled fork of [Frappe Press](https://github.com/frappe/press) rebranded as **Accurate Systems Cloud Hosting Solutions**. The fork lives on the `cloudflare-dns` branch of `accurate-systems/press`.

## Brand Identity

- **Company**: Accurate Systems (accuratesystems.com.sa)
- **Product**: Cloud Hosting Solutions
- **Primary Color**: `#046BD2` (Accurate Systems blue)
- **Logo**: SVG component at `dashboard/src/components/icons/FCLogo.vue`

## What Was Changed

The rebrand touched 170+ files across the Press codebase. Key areas:

1. **Dashboard Vue SPA** — Sidebar, login, colors, form elements
2. **Email Templates** — Dark header with white logo
3. **Landing Pages** — Marketplace, SaaS pages
4. **API/Backend** — Brand strings in Python files
5. **Static Assets** — Logo files, favicons

## Scope

This fork does NOT modify Press's core functionality (site creation, bench management, billing, etc.). All changes are cosmetic/branding only. The fork tracks the upstream `develop` branch and can be rebased when needed.
