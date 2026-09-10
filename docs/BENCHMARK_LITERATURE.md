# Literature-cited Motion Benchmarks

Status: `verification_status=literature_cited` · `source=peer_reviewed_literature`

Banner (API / mini-program):

> 文献科研参考标准（非教练现场标定）

These packages **replace reliance on `synthetic_demo` numeric ranges for production scoring** when published with `--allow-literature-cited`. They are **not** coach field calibration and **not** `verified` expert sign-off.

## Packages

| File | Skill | Version |
|------|-------|---------|
| `docs/benchmark/literature/forehand_smash.literature_v1.json` | forehand_smash | `1.0.0-lit` |
| `docs/benchmark/literature/net_tumble.literature_v1.json` | net_tumble | `1.0.0-lit` |
| `docs/benchmark/literature/forehand_clear.literature_v1.json` | forehand_clear | `1.0.0-lit` |

## Sources

### A) Forehand smash — Shan et al., *J Hum Kinet* 2016;53:9–22

- DOI: https://doi.org/10.1515/hukin-2016-0006 · PMC5260572
- Skilled group (SG) mean±SD used as `range_kind=literature_mean_sd` (mean±1SD):
  - X-factor / trunk rotation **46.9 ± 11.2°** → 35.7–58.1 (`trunk_coil_backswing`; lit X-factor = pelvis–shoulder separation)
  - Shoulder rotation ROM **107.5 ± 30.9°** → 76.6–138.4 (`shoulder_rotation_rom`, MediaPipe **proxy**)
  - Elbow flex/ext ROM **70.6 ± 9.1°** → 61.5–79.7 (`elbow_flex_ext_rom`, 2D ROM **proxy**)
  - Wrist flex/ext ROM **85.9 ± 50.4°** → caution band 40–130 (`wrist_flex_ext_rom`; MediaPipe **null** / not measurable)
- Instructional (not mean): contact with arm extended — `elbow_flexion_at_contact` **null**

### B) Net tumble — Hsueh, Tsai, Pan, Chang, ISB 2009

- PDF: https://media.isbweb.org/images/conf/2009/data/pdf/544.pdf
- Elite collegiate Taiwanese males (n=8), tumble at contact (`literature_point_tolerance`):
  - Elbow **139°** (dab 142°) → 130–150 (`elbow_flexion_at_contact`)
  - Racket vs horizontal **21°** (dab 33°) → 15–27 (`racket_face_vs_horizontal_proxy`; forearm **proxy** ≠ racket face)
  - Contact height **1.24 m** (dab 1.21) — absolute lab meters → metric **null** (`contact_height_lab_m`)

### C) Forehand clear

- Prefer honesty: few open numeric means.
- Korean J Sports Sci 2020 (doi:10.35159/kjss.2020.02.29.1.793) cited for X-factor/coordination **without fabricating clear-specific angles**.
- Shan 2016 X-factor reused only as `range_kind=literature_proxy_related_stroke` on trunk metrics, with explicit related-overhead note.
- Clear elbow / relative height metrics remain **null**.

## Limitations (critical)

1. **Single-camera MediaPipe ≠ lab Vicon / marker systems** used in the papers.
2. Many scorer values are **proxies of different quantities** (2D image angles vs 3D joint ROM / racket face / absolute height).
3. `literature_cited` ≠ coach on-court calibration; do not present as “verified”.
4. Publish requires explicit `--allow-literature-cited` (same honesty pattern as synthetic demo).

## Import + publish

```bash
# validate
python scripts/benchmark_validate.py docs/benchmark/literature/forehand_smash.literature_v1.json --allow-literature-cited
python scripts/benchmark_validate.py docs/benchmark/literature/net_tumble.literature_v1.json --allow-literature-cited
python scripts/benchmark_validate.py docs/benchmark/literature/forehand_clear.literature_v1.json --allow-literature-cited

# import (draft)
python scripts/benchmark_import.py docs/benchmark/literature/forehand_smash.literature_v1.json --allow-literature-cited
python scripts/benchmark_import.py docs/benchmark/literature/net_tumble.literature_v1.json --allow-literature-cited
python scripts/benchmark_import.py docs/benchmark/literature/forehand_clear.literature_v1.json --allow-literature-cited

# publish (archives prior published version for that skill)
python scripts/benchmark_publish.py forehand_smash --version 1.0.0-lit --allow-literature-cited
python scripts/benchmark_publish.py net_tumble --version 1.0.0-lit --allow-literature-cited
python scripts/benchmark_publish.py forehand_clear --version 1.0.0-lit --allow-literature-cited
```

Or: `bash scripts/benchmark_publish_literature.sh` (from repo root, with API venv / `DATABASE_URL` set).
