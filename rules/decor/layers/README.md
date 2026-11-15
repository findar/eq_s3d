# Decor layers

Each `<name>.toml` here is a decor layer: a `[layer]` table (`name`, matching the file name,
and `description`) plus any of `rooms.toml`'s sections except `default` and `moves`
(`kinds`, `types`, `zones`, `sites`, `groups`, `dressing`, `every`, `weights`, `once`).
A layer is merged onto `rooms.toml` at load time; the shared file is never edited.

```toml
[layer]
name        = "bones"
description = "Bones in the barracks, darker deep rooms"

[groups.bone_heap]              # new: added
members = [ { kind = "skull", at = "anchor" }, { kind = "bones", at = "round", count = [1, 3] } ]

[types.barracks]                # already in rooms.toml: says what to do with it
mode  = "add"                   # its lines join the existing ones ("replace": they stand instead)
props = [ { group = "bone_heap", at = "scatter", chance = 0.5 } ]

[weights.kinds.deep]            # new Weights entry
light = 0.5
```

An entry the base (or an earlier layer) already has is refused unless it says `mode`. On a
Weights entry, `mode = "add"` adds Categories the entry doesn't name yet and refuses one it does;
`"replace"` stands for the whole entry. Each layer is checked on its own and the merged set as a
whole. `../themes.toml` says which themes and races take which layers; a build request can name
more (`decor_layers`).

The full guide is `docs/DECOR_RULES.md`; `tomb.toml` here is its worked example.
