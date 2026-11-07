# Notes on a sample ArtiosCAD design (from ARD construction history)

Units metric, defaults `Folding Carton - Metric - Single design parameters`,
bridging `Folding Carton - Metric - bridging formula`, board I-SBS-16, GRAIN 2.
Line types used: `cha ... type 1` cut, `type 2` crease, `type 8` reverse crease.

## 设计2 (设计2_history.txt) — rotational structure
- Construction circles R25.63 and R13.06/R47, construction lines at -25°, -22.5°, -11.25°.
- One unit cell drawn, then `trans ... rot (-22.5)`, `rot 22.5`, `rot -45`, `rot -90` copies
  → 4-fold rotational symmetry (360/16 = 22.5° step geometry).
- Many lines changed to `type 8` (reverse crease) and `type 2` → mountain/valley fold pattern.
- Reproduce with `Dieline.rotate_copy` / `polar_array` and `set_type(..., REV_CREASE)`.
