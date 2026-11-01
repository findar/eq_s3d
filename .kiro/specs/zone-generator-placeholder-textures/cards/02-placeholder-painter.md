# 2 — Bitmap font and placeholder painter

Index entry: `tasks.md` task 2. Design: "Placeholder look". Requirement 3.

## Goal
`placeholder_rgb(name, base_color, surface_class)` draws a 256×256 tileable
texture with its Surface_Class pattern and the name as legible text, and
`PlaceholderProvider` wraps it as DDS.

## Done when
- [ ] The font covers a–z (drawn uppercase), 0–9 and `_`; an unknown
      character raises.
- [ ] X5 holds for every Surface_Class and for names of 1–40 characters
      (Hypothesis over `[a-z0-9_]` names): glyphs ≥ 12 px tall, label
      contrast ≥ 4.5 against its plate, one whole label inside the edges,
      seamless wrap, the same bytes in a fresh process, different names give
      different bytes.
- [ ] The five patterns differ from one another (same name and colour, five
      classes, five different images).
      → verify: `python -m pytest tests/test_placeholder_textures.py -q`.
- [ ] `python -m pytest tests/ -q` is green.

## Pitfalls
- No `hash()`, no RNG (Req 3.5); ROADMAP's known issue with salted seeds is
  exactly what to avoid.
- Use WCAG relative luminance for the contrast ratio.
- Don't wire the provider into the factory here; that's task 3.

## Result
