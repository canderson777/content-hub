# Brands

Each folder is one brand the Hub works on. The Hub reads these files in place —
it never copies or deletes them.

```txt
brands/<brand-id>/
  brand-voice.md          tone and voice rules
  audience.md             who the brand serves
  offers.md               offers and calls to action
  content-pillars.md      recurring content themes
  positions/three-ps.md   the Person / Pain / Promise
  assets/                 logos, brand-guidelines, product-shots, studio-shots, social/
```

Three empty example brands ship with the repo: `brand-a`, `brand-b`, `brand-c`.
Rename them or add your own — update `BRANDS` in `server.py` if you change the ids.

Point the Hub at a different brands root with the `CONTENT_HUB_BRANDS_ROOT`
environment variable.
