# Install Reading Room as a Mac app

This turns your local reading room (`192.168.1.1:4747`) into a real dock app
using a PWA. Three small steps — I can't do the install for you (it's on your
Mac, I'm in the cloud), but this makes it a one-click button.

## 1. Drop these three files into your reading room app folder

Put `manifest.webmanifest`, `icon.svg`, and `sw.js` next to the HTML your
server serves at `/` (so they're reachable at `/manifest.webmanifest`,
`/icon.svg`, `/sw.js`).

## 2. Add these lines inside the `<head>` of the reading room's HTML

```html
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="#1a1714">
<link rel="apple-touch-icon" href="/icon.svg">
<script>
  if ('serviceWorker' in navigator)
    navigator.serviceWorker.register('/sw.js');
</script>
```

## 3. Install it on your Mac

**Chrome / Edge** — open `http://192.168.1.1:4747/`, click the **install icon**
(a monitor with a down-arrow) on the right edge of the address bar, then
**Install**. It lands in your Applications + Dock.

**Safari (macOS Sonoma 14 or newer)** — open the site, then **File → Add to
Dock…**. (Safari doesn't need the service worker, but it's harmless to have.)

---

### Heads-up: `http` + a bare IP

Browsers only treat a page as installable over **https** *or* **localhost**.
A plain `http://192.168.1.1` may not show the install button. Easiest fixes:

- Open it as **`http://localhost:4747`** if you're on the same machine that
  runs the server — `localhost` counts as a secure context, so install works.
- Or serve the reading room over https (e.g. a self-signed cert, or a tool
  like Caddy / `mkcert`).

Tell me which way you serve it and I'll tailor the exact setup.
