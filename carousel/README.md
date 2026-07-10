# FPL Data Story Carousel

This is a deterministic Python and Pillow pipeline that turns six FPL retrospective data stories into 1080 by 1350 Instagram carousel slides and one PDF per story.

Render a story from this directory:

```sh
python3 render_data_story.py xg_finishing
```

Available story slugs: `xg_finishing`, `points_by_position`, `expected_stats`, `elite_ownership`, `fdr`, and `mean_vs_median`.

`brand.py` contains the one-place palette, typography, header, and footer settings. `stories/slides_<slug>.py` holds each story's `STORY` metadata and `SLIDES` copy. Source charts live in `charts/<slug>/`. Renders are written to `outputs/<slug>/png/` and `outputs/<slug>/story_carousel_<slug>.pdf`.

The renderer derives its background seed from the story slug and slide number, so re-rendering unchanged specs produces byte-identical PNGs.
