# Previous versions (Python source only)

Snapshots of the Python code of earlier releases, for reference. The compiled executables are attached to the corresponding [GitHub Releases](https://github.com/HydrogeomorphologyTools/DF-scan/releases) (too large for the repository). The full state of each release, including test data, is also available from its git tag.

| Folder | Release / tag | Notes |
|---|---|---|
| `pre-release_MSF/` | `MSF_pre_release_executable` | First public pre-release (`msf_engine.py`, `msf_gui.py`, `msf_cli.py`) |
| `v5.0/` | `v5.0` | First DF-scan release. H/L, LI, FRI and backlink rasters could come from a different source than the one giving the maximum PQ_LIM; sequential mode: empty backlinks and no pruned raster |
| `v5.0.1/` | `v5.0.1` | Aggregation fixes (see the changelog in the main README) |

The current code is in `src/` (v5.0.2 and later). Do not run these snapshots from inside this repository without installing the same dependencies (rasterio, numpy, geopandas, PyQt5).
