# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Static portfolio site for Eugene Lim / Bro You Want Art? — deployed to `broyouwantart.com` via GitHub Pages. No build tools, no framework, no package manager. Everything is plain HTML, CSS, and vanilla JS.

## Local Preview

```bash
python3 -m http.server 8080
# then open http://localhost:8080
```

## File Structure

- `index.html` — the entire site in one file: all CSS is inline in `<style>`, all JS is inline in `<script>` at the bottom
- `about.html` — standalone about page with its own self-contained styles
- `assets/_cropped/FASHION /` — fashion project images (note the trailing space in the folder name)
- `assets/_cropped/HUMAN/` — human project images
- `assets/_cropped/OBJECTS/` — objects project images
- `assets/eugenelightning/contact/` — profile photo used in about.html
- `assets/monolith-loop/set-3/` — image frames used in the mobile monolith slideshow (00.jpg–04.jpg)
- `CNAME` — GitHub Pages custom domain config

## Architecture of index.html

The file has three logical sections on a single page: a monolith entrance screen, a scrolling text index, and a project detail view. These are toggled via body classes and element visibility — there is no client-side router library.

**Data layer** (line 148): `const PROJECTS = [...]` — a single hardcoded array. Each entry:
```js
{
  id: "slug-style-id",       // used as the URL hash fragment
  title: "Project Title",
  number: "01",              // two-digit display string
  category: "fashion" | "human" | "objects",
  images: [{ src: "...", alt: "..." }],
  video: "embed-url",        // optional YouTube/Vimeo embed URL
  videoTitle: "...",         // optional
  context: "Context text",   // optional, shown in the project meta strip
}
```

**Routing**: `location.hash` drives everything. `#project-id` calls `showProject(id)`; empty hash calls `showIndex()`. A `hashchange` listener and an initial `route()` call handle all navigation.

**Three view states**, toggled by body classes and element display:
1. **Monolith entrance** — active when `body.monolith-ready` is set (before the user has clicked in); hidden after `body.monolith-entered` is added
2. **Index view** — the auto-scrolling comma-separated text list; `in-project` body class hides it
3. **Project view** — the "book spread" layout; `.project-view.active` shows it; `in-project` body class triggers the dark background

**Category colour coding**: `fashion` → red (`#f00`), `human` → yellow (`#ffd400`), `objects` → blue (`#0057ff`). Applied via `data-category` attributes on index links.

**URL params**:
- `?font=softie` or `?font=pesto` — swaps the display typeface from default Futura PT
- `?monolith=v2` — activates the canvas-based V2 monolith entrance instead of the default CSS 3D / WebGL V1

**Monolith entrance (V1)**: A CSS 3D rectangular prism (`monolith-shell`) that spins continuously. If WebGL is available, a Three.js canvas (loaded from CDN) replaces the CSS prism (`webgl-ready` class on `monolith-stage`). On mobile, a slideshow of images from `assets/monolith-loop/set-3/` is composited onto the CSS prism faces.

**Monolith entrance (V2)**: A completely separate canvas-based implementation behind `?monolith=v2`; managed by `buildMonolithV2()` / `stopMonolithV2()`.

**Project detail layout**: A two-page "book spread" — left page is the hero image at full bleed; right page has a smaller secondary image (top-left) plus a text block (bottom). Images 3+ appear in a two-column grid below the spread. Prev/next navigation wraps around the PROJECTS array.

**Responsive breakpoint**: `760px` max-width. Mobile collapses the book spread to a single-column stack.

## Key Conventions

- All CSS and JS lives inside `index.html`. Do not create separate `.css` or `.js` files.
- `about.html` has its own self-contained `<style>` block; it does not share CSS with `index.html`.
- Image paths in `PROJECTS` are URL-encoded (spaces become `%20`, narrow no-break spaces become `%E2%80%AF`). Match the exact encoding of the actual filenames.
- The `FASHION ` asset folder has a trailing space — this is intentional (matches the source folder name).
- Project `id` values are kebab-case slugs derived from the title; they double as the URL hash.
- Project `number` values are sequential two-digit strings (`"01"`, `"02"`, …); update them if reordering.
- The site is deployed via GitHub Pages from the `main` branch. Push to `main` to publish.
