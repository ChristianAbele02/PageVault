# Vendored front-end libraries

These third-party assets are bundled locally so PageVault works fully offline,
including inside the Android WebView, where there is no guarantee of network
access. Serving them same-origin also removes the need for Subresource Integrity
(the CDN `integrity=` hashes were dropped along with the CDN URLs).

Do not edit these files by hand. To refresh or bump a version, re-download from
the pinned source below.

| File | Version | Source |
|---|---|---|
| `html5-qrcode.min.js` | 2.3.8 | https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js |
| `plotly-basic.min.js` | 2.35.2 | https://cdn.plot.ly/plotly-basic-2.35.2.min.js (partial build: bar/pie/scatter, ~1 MB vs 4.5 MB — covers every chart the stats page uses) |
| `epub.min.js` | 0.3.93 | https://cdn.jsdelivr.net/npm/epubjs@0.3.93/dist/epub.min.js (bundles JSZip) |
| `qrcode.min.js` | 1.0.0 | https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js |
| `fonts/` | Google Fonts | Playfair Display + Lato, woff2 subsets + rewritten `fonts.css` |

## Regenerating the fonts

```bash
cd static/vendor/fonts
curl -sSL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36" \
  -o fonts.css \
  "https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Lato:wght@300;400;700&display=swap"
for url in $(grep -o "https://fonts.gstatic.com[^)]*\.woff2" fonts.css | sort -u); do
  curl -sSL -o "$(basename "$url")" "$url"
done
sed -i -E "s#https://fonts.gstatic.com/[^)]*/([^/)]*\.woff2)#\1#g" fonts.css
```
