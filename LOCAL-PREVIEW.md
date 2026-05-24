# Local preview

Because the public HTTPS certificate can be pending, preview the site locally from this folder.

## Easiest

Double-click:

```text
preview-local.command
```

It starts a Python static server and opens:

```text
http://127.0.0.1:8765/?monolith=v2&drawn=1
```

## Manual terminal command

```bash
cd /Users/eugene/LiveSites/broyouwantart.com
python3 -m http.server 8765 --bind 127.0.0.1
```

Then open:

```text
http://127.0.0.1:8765/?monolith=v2&drawn=1
```

Use `http://`, not `https://`, for local preview.
