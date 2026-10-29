"""
Consistency check of the three ways DF-scan aggregates sources (standard MSF + pruned MSF):

  1. sequential batches   (process_source_batch + combine_batch_results)
  2. parallel pool        (process_sources_parallel)
  3. an independent reference built here from single-source runs

All three must give identical PQ_LIM, pruned PQ_LIM, LI, FRI, H/L and backlink rasters.
The rule is: PQ_LIM = cell-wise maximum over sources; LI, FRI, H/L and backlinks come from the source
that gives that maximum (first source wins ties; cells outside every PQ_LIM zone come from the first
source that reaches them).

Usage (from the repository root):
    python tests/check_modes.py                # checks ./src
    python tests/check_modes.py --src other/src
Exit code 0 = all checks passed.
"""
import argparse
import os
import sys
import tempfile

import numpy as np

ND = -9999.0
NDI = 32767


class Cfg:
    MAX_SLOPE_DEGREES = 5.0
    USE_DIRECTION_AWARE_UPHILL = False
    HRMA_FROM_THRESH_LI = 90
    HRMA_TO_THRESH_LI = 90
    ZERO_FACTOR = 0.5
    CUT_ANGLE = 45
    SLOPE = 0.011111
    USE_DIRECT_DISTANCE_FOR_HL = False
    FILL_HL_HOLES = True
    H_L_THRESHOLD = 0.25
    ENABLE_MSF_PRUNING = True
    MSF_PRUNING_THRESHOLD = 1.4
    RUN_RUNOUTSIM = False
    OUTPUT_DIR = ''
    NUM_WORKERS = 2
    BATCH_SIZE = 4


def reference(per):
    """Independent aggregation of single-source results (no shared code with the engine)."""
    n = len(per)
    pq = np.stack([p['pq_lim'] for p in per])
    ok_pq = (pq != ND) & (pq > 0)
    best = np.argmax(np.where(ok_pq, pq, -np.inf), axis=0)
    any_pq = ok_pq.any(0)
    out = {'pq_lim': np.where(any_pq, np.take_along_axis(pq, best[None], 0)[0], ND).astype(np.float32)}

    pp = np.stack([p['pq_lim_pruned'] for p in per])
    ok_pp = (pp != ND) & (pp > 0)
    out['pq_lim_pruned'] = np.where(ok_pp.any(0), np.where(ok_pp, pp, -np.inf).max(0), ND).astype(np.float32)

    for key, bl in (('li', 'backlink_li'), ('fri', 'backlink_fri'), ('h_l', None)):
        v = np.stack([p[key] for p in per])
        ok = (v != ND) & (v >= 0)
        first = np.argmax(ok, axis=0)
        idx = np.where(any_pq, best, first)
        out[key] = np.where(ok.any(0), np.take_along_axis(v, idx[None], 0)[0], ND).astype(np.float32)
        if bl:
            b = np.stack([p[bl] for p in per])
            out[bl] = np.where(ok.any(0), np.take_along_axis(b, idx[None], 0)[0], NDI).astype(np.int16)
    return out


def main():
    ap = argparse.ArgumentParser()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument('--src', default=os.path.join(root, 'src'))
    ap.add_argument('--data', default=os.path.join(root, 'test_data'))
    args = ap.parse_args()
    sys.dont_write_bytecode = True
    sys.path.insert(0, args.src)
    import io, contextlib
    import rasterio
    import dfscan_core as core

    def quiet(f, *a, **k):
        with contextlib.redirect_stdout(io.StringIO()):
            return f(*a, **k)

    with tempfile.TemporaryDirectory() as tmp:
        dtm_path = os.path.join(args.data, 'grigna_dtm.tif')
        with rasterio.open(dtm_path) as s:
            nodata = s.nodata
        dtm, ref_prof, _ = quiet(core.resample_dtm_aggregate, dtm_path, 20, 'bilinear', os.path.join(tmp, 'r.tif'))
        mask = core.make_mask(dtm, nodata)
        dtm = quiet(core.fill_pits_custom, dtm, mask, nodata)
        mask = core.make_mask(dtm, nodata)
        fdir, fnd = quiet(core.calculate_d8_flow_direction, dtm, mask, 20.0)
        fmask = core.make_mask(fdir, fnd)
        fdeg = core.fdir_to_degrees(fdir.astype(np.int32), fnd)
        src_raster, _ = quiet(core.shapefile_to_raster, os.path.join(args.data, 'test_points.shp'), ref_prof, None)
        src_pix = np.argwhere((src_raster != 0) & (~mask))
        print('sources:', len(src_pix), ' grid:', dtm.shape)

        cfg = Cfg()
        per = [quiet(core.process_single_source_point, int(r), int(c), dtm, mask, fdeg, fmask, 20.0, cfg, fdir) for r, c in src_pix]
        ref = reference(per)

        core.Config.RUN_RUNOUTSIM = False
        batches = [quiet(core.process_source_batch, src_pix[i:i + cfg.BATCH_SIZE], dtm, mask, fdeg, fmask, None, None, 20.0, cfg, fdir)
                   for i in range(0, len(src_pix), cfg.BATCH_SIZE)]
        seq = quiet(core.combine_batch_results, batches, ND, NDI)
        par = quiet(core.process_sources_parallel, src_pix, dtm, mask, fdeg, fmask, 20.0, cfg, None, fdir)

    failures = 0
    for name, res in (('sequential', seq), ('parallel', par)):
        for key in ('pq_lim', 'pq_lim_pruned', 'li', 'fri', 'h_l', 'backlink_li', 'backlink_fri'):
            if key not in res:
                print('FAIL  %-10s %-14s missing from the returned dictionary' % (name, key)); failures += 1
                continue
            same = np.array_equal(res[key], ref[key])
            valid = int((res[key] != (NDI if 'backlink' in key else ND)).sum())
            print('%s  %-10s %-14s valid cells %6d  %s' % ('ok  ' if same else 'FAIL', name, key, valid,
                                                           '' if same else '(%d cells differ from reference)' % int((res[key] != ref[key]).sum())))
            failures += 0 if same else 1
    print('\nALL CHECKS PASSED' if failures == 0 else '\n%d CHECK(S) FAILED' % failures)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
