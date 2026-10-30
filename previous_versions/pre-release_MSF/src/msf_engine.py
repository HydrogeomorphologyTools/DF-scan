"""
COMPLETE MSF WORKFLOW - Regional Scale Version
===============================================
Enhanced for regional-scale analysis with multiple source points:
- Batch processing for large numbers of sources (max 200 points per batch)
- Overlapping zones: keeps MAXIMUM PQ_LIM (most hazardous value)
- DTM resampling with median aggregation
- Automatic pit filling and flow direction
- Complete MSF model execution
- OPTIONAL: Save LI, FRI rasters with their backlink arrays
- NEW: Optional H/L calculation with euclidean distance
- NEW: Optional parallel processing for multiple cores

Version: MSF Regional Scale v3.2
Date: 2025-10-30
Changes: Added parallel processing and euclidean distance option for H/L
"""

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.features import rasterize
import heapq
import math
import os
from datetime import datetime
import sys

# Try to import optional dependencies
try:
    import geopandas as gpd

    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False
    print("⚠ Warning: geopandas not available. Shapefile input will not work.")
    sys.stdout.flush()
    sys.stderr.flush()

try:
    from whitebox import WhiteboxTools

    WHITEBOX_AVAILABLE = True
except ImportError:
    WHITEBOX_AVAILABLE = False
    print("⚠ Warning: whitebox not available. Using custom implementations.")
    sys.stdout.flush()
    sys.stderr.flush()

try:
    import multiprocessing as mp
    from functools import partial

    MULTIPROCESSING_AVAILABLE = True
except ImportError:
    MULTIPROCESSING_AVAILABLE = False
    print("⚠ Warning: multiprocessing not available. Parallel processing disabled.")
    sys.stdout.flush()
    sys.stderr.flush()


# =========================================================================
# HELPER FUNCTIONS
# =========================================================================

def safe_flush():
    """Safely flush stdout and stderr (exe-safe for compiled binaries)"""
    try:
        if sys.stdout is not None:
            sys.stdout.flush()
        if sys.stderr is not None:
            sys.stderr.flush()
    except:
        pass


# =========================================================================
# CONFIGURATION
# =========================================================================

class Config:
    """Configuration for MSF workflow"""

    # =====================================================================
    # INPUT OPTIONS
    # =====================================================================

    SOURCE_INPUT_TYPE = "SHAPEFILE"

    DTM_ORIGINAL_PATH = ""
    DTM_FILLED_PATH = ""  # Optional
    FDIR_PATH = ""  # Optional

    SOURCE_SHAPEFILE_PATH = ""
    # SOURCE_RASTER_PATH = ""  # Optional

    SHAPEFILE_ELEV_FIELD = "elev"

    PQLIM_OUTPUT_FILENAME = "pq_lim.tif"

    OUTPUT_DIR = "outputs"

    # =====================================================================
    # DTM RESAMPLING OPTIONS
    # =====================================================================

    RESAMPLE_DTM = True  # Set to True to resample
    TARGET_RESOLUTION = 15  # Target resolution in meters
    AGGREGATION_METHOD = "median"  # "median", "mean", or "bilinear"

    # =====================================================================
    # BATCH PROCESSING OPTIONS
    # =====================================================================

    # Maximum number of source points to process simultaneously
    BATCH_SIZE = 200  # Reduce if memory issues, increase for faster processing

    # Combination method for overlapping zones
    OVERLAP_METHOD = "MAX"  # Always use MAX for most hazardous value

    # =====================================================================
    # PARALLEL PROCESSING OPTIONS (NEW!)
    # =====================================================================

    ENABLE_PARALLEL_PROCESSING = True  # Enable multiprocessing
    NUM_WORKERS = 8  # Number of parallel workers (adjust based on CPU cores)
    POINTS_PER_WORKER = 4  # Number of source points each worker processes

    # =====================================================================
    # PROCESSING OPTIONS
    # =====================================================================

    DO_PIT_FILLING = True
    USE_WHITEBOX_FILLING = True

    CALCULATE_FLOW_DIRECTION = True
    USE_WHITEBOX_FDIR = False

    # =====================================================================
    # MSF MODEL PARAMETERS
    # =====================================================================

    MAX_SLOPE_DEGREES = 30
    H_L_THRESHOLD = 0.19
    USE_DIRECTION_AWARE_UPHILL = False

    HRMA_FROM_THRESH_LI = 90
    HRMA_TO_THRESH_LI = 90

    ZERO_FACTOR = 0.5
    CUT_ANGLE = 90
    SLOPE = 0.011111

    # =====================================================================
    # H/L CALCULATION OPTIONS (NEW!)
    # =====================================================================

    USE_DIRECT_DISTANCE_FOR_HL = False  # If True, H/L uses Euclidean distance instead of path distance
    # When True: H/L = vertical_drop / euclidean_distance_2D
    # When False: H/L = vertical_drop / path_distance (current behavior)

    # =====================================================================
    # ADVANCED OPTIONS
    # =====================================================================

    WBT_BREACH_DIST = 5
    WBT_FILL_DEPS = True

    SAVE_INTERMEDIATE_OUTPUTS = False
    COMPRESS_OUTPUTS = True

    # =====================================================================
    # OPTIONAL OUTPUT RASTERS
    # =====================================================================

    SAVE_LI_RASTER = False  # Save Distance raster from LI
    SAVE_LI_BACKLINK = False  # Save Backlink raster from LI

    SAVE_FRI_RASTER = False  # Save Distance raster from FRI
    SAVE_FRI_BACKLINK = False  # Save Backlink raster from FRI


# =========================================================================
# UTILITY FUNCTIONS
# =========================================================================

def print_header(title):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)
    sys.stdout.flush()
    sys.stderr.flush()


def print_step(step_num, total_steps, description):
    """Print formatted step header"""
    print(f"\n[STEP {step_num}/{total_steps}] {description}...")
    sys.stdout.flush()
    sys.stderr.flush()


def read_and_snap(path, ref_profile):
    """Read a raster and align it to reference grid if necessary"""
    with rasterio.open(path) as src:
        arr = src.read(1)
        nodata_val = src.nodata
        src_crs = src.crs if src.crs is not None else ref_profile["crs"]

        same_grid = (
                src.width == ref_profile["width"]
                and src.height == ref_profile["height"]
                and src.transform == ref_profile["transform"]
                and src_crs == ref_profile["crs"]
        )

        if same_grid:
            return arr, nodata_val

        dst = np.empty((ref_profile["height"], ref_profile["width"]), dtype=arr.dtype)
        reproject(
            source=arr,
            destination=dst,
            src_transform=src.transform,
            src_crs=src_crs,
            dst_transform=ref_profile["transform"],
            dst_crs=ref_profile["crs"],
            resampling=Resampling.nearest,
        )
        return dst, nodata_val


def make_mask(arr, nodata):
    """Create mask for NoData values"""
    mask = np.zeros(arr.shape, dtype=bool)
    if nodata is not None:
        if np.issubdtype(arr.dtype, np.floating):
            mask |= (arr == nodata) | np.isnan(arr) | (arr < -1e10)
        else:
            mask |= (arr == nodata)
    return mask


def save_raster(arr, profile, output_path, nodata=None, compress=True):
    """Save raster to file"""
    prof = profile.copy()
    prof.update(dtype=arr.dtype)
    if nodata is not None:
        prof.update(nodata=nodata)
    if compress:
        prof.update(compress="lzw")

    with rasterio.open(output_path, "w", **prof) as ds:
        ds.write(arr, 1)
    print(f"  ✓ Saved: {output_path}")
    sys.stdout.flush()
    sys.stderr.flush()


def fdir_to_degrees(fdir_arr, fdir_nodata):
    """Convert ArcGIS D8 flow direction to degrees"""
    deg = np.full(fdir_arr.shape, np.nan, dtype=np.float32)

    mapping = {
        64: 0, 128: 45, 1: 90, 2: 135,
        4: 180, 8: 225, 16: 270, 32: 315,
    }

    for val, angle in mapping.items():
        deg[fdir_arr == val] = angle

    if fdir_nodata is not None:
        deg[fdir_arr == fdir_nodata] = np.nan

    return deg


def calculate_uphill_tolerance(cellsize, max_slope_degrees=30, direction_idx=None,
                               use_direction_aware=False):
    """Calculate uphill tolerance"""
    max_slope_rad = math.radians(max_slope_degrees)
    root2 = math.sqrt(2)

    if use_direction_aware and direction_idx is not None:
        is_diagonal = direction_idx % 2 == 1
        distance = cellsize * root2 if is_diagonal else cellsize
        uphill_tolerance_theoretical = distance * math.tan(max_slope_rad)
    else:
        uphill_tolerance_theoretical = cellsize * math.tan(max_slope_rad)

    uphill_tolerance_rounded = round(uphill_tolerance_theoretical, 1)
    uphill_tolerance_final = round(uphill_tolerance_rounded)

    return uphill_tolerance_final


# =========================================================================
# DTM RESAMPLING FUNCTIONS
# =========================================================================

def resample_dtm_aggregate(dtm_path, target_resolution, method="median", output_path=None):
    """Resample DTM to coarser resolution using aggregation"""
    print(f"  Resampling DTM to {target_resolution}m resolution...")
    print(f"  Aggregation method: {method}")

    with rasterio.open(dtm_path) as src:
        original_profile = src.profile
        dtm = src.read(1)
        nodata = src.nodata
        original_transform = src.transform
        original_crs = src.crs

        original_resolution = abs(original_transform.a)

        print(f"  Original resolution: {original_resolution}m")
        print(f"  Original shape: {dtm.shape}")

        if target_resolution <= original_resolution:
            print("  ⚠ Warning: Target resolution <= original resolution, no resampling performed")
            return dtm, original_profile, original_profile

        factor = int(round(target_resolution / original_resolution))
        print(f"  Aggregation factor: {factor}x{factor}")

        new_height = dtm.shape[0] // factor
        new_width = dtm.shape[1] // factor

        print(f"  New shape: ({new_height}, {new_width})")

        mask = make_mask(dtm, nodata)

        if method == "median":
            resampled = aggregate_median(dtm, mask, factor, nodata)
        elif method == "mean":
            resampled = aggregate_mean(dtm, mask, factor, nodata)
        elif method == "bilinear":
            new_transform = original_transform * original_transform.scale(factor, factor)
            resampled = np.empty((new_height, new_width), dtype=dtm.dtype)
            reproject(
                source=dtm,
                destination=resampled,
                src_transform=original_transform,
                src_crs=original_crs,
                dst_transform=new_transform,
                dst_crs=original_crs,
                resampling=Resampling.bilinear,
                src_nodata=nodata,
                dst_nodata=nodata
            )
        else:
            raise ValueError(f"Unknown aggregation method: {method}")

        new_transform = original_transform * original_transform.scale(factor, factor)
        new_profile = original_profile.copy()
        new_profile.update({
            'height': new_height,
            'width': new_width,
            'transform': new_transform
        })

        valid_orig = ~mask
        valid_new = (resampled != nodata) & ~np.isnan(resampled)

        print(f"  Original valid cells: {valid_orig.sum():,}")
        print(f"  Resampled valid cells: {valid_new.sum():,}")
        print(f"  Original elevation range: [{dtm[valid_orig].min():.2f}, {dtm[valid_orig].max():.2f}]m")
        print(f"  Resampled elevation range: [{resampled[valid_new].min():.2f}, {resampled[valid_new].max():.2f}]m")

        if output_path:
            save_raster(resampled, new_profile, output_path, nodata, True)

        return resampled, new_profile, original_profile


def aggregate_median(arr, mask, factor, nodata):
    """Aggregate array using median of factor x factor windows"""
    old_height, old_width = arr.shape
    new_height = old_height // factor
    new_width = old_width // factor

    result = np.full((new_height, new_width), nodata, dtype=arr.dtype)

    for i in range(new_height):
        if i % 10 == 0:
            print(f"    Aggregating row {i}/{new_height}...")
        for j in range(new_width):
            window = arr[i * factor:(i + 1) * factor, j * factor:(j + 1) * factor]
            window_mask = mask[i * factor:(i + 1) * factor, j * factor:(j + 1) * factor]
            valid_vals = window[~window_mask]

            if len(valid_vals) > 0:
                result[i, j] = np.median(valid_vals)

    return result


def aggregate_mean(arr, mask, factor, nodata):
    """Aggregate array using mean of factor x factor windows"""
    old_height, old_width = arr.shape
    new_height = old_height // factor
    new_width = old_width // factor

    result = np.full((new_height, new_width), nodata, dtype=arr.dtype)

    for i in range(new_height):
        if i % 10 == 0:
            print(f"    Aggregating row {i}/{new_height}...")
        for j in range(new_width):
            window = arr[i * factor:(i + 1) * factor, j * factor:(j + 1) * factor]
            window_mask = mask[i * factor:(i + 1) * factor, j * factor:(j + 1) * factor]
            valid_vals = window[~window_mask]

            if len(valid_vals) > 0:
                result[i, j] = np.mean(valid_vals)

    return result


# =========================================================================
# PIT FILLING FUNCTIONS
# =========================================================================

import subprocess

def get_wbt_exe_path():
    """Find the whitebox_tools.exe binary, supporting both dev and frozen modes."""
    if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS'):
        # In the PyInstaller bundle
        base_path = sys._MEIPASS
        bundled_exe = os.path.join(base_path, 'WBT', 'whitebox_tools.exe')
        if os.path.exists(bundled_exe):
            return bundled_exe
    
    # In development mode
    local_exe = os.path.join(os.getcwd(), 'WBT', 'whitebox_tools.exe')
    if os.path.exists(local_exe):
        return local_exe
        
    return "whitebox_tools.exe"  # Fallback to system path

def run_wbt_command(tool_name, args):
    """Run a WhiteboxTools command directly via subprocess."""
    exe_path = get_wbt_exe_path()
    cmd = [exe_path, f"--run={tool_name}"]
    for k, v in args.items():
        if v is True:
            cmd.append(f"--{k}")
        elif v is not False and v is not None:
            cmd.append(f"--{k}={v}")
    
    print(f"    Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    ⚠ WhiteboxTools Error: {result.stderr}")
    return result.returncode == 0

def fill_pits_whitebox(dtm_path, output_path, breach_dist=5, fill_deps=True):
    """Fill pits using WhiteboxTools (Direct Call)"""
    print("  Using WhiteboxTools for pit filling (Direct CLI mode)...")
    
    temp_breached = output_path.replace(".tif", "_breached_temp.tif")
    
    # 1. Breach Depressions
    run_wbt_command("BreachDepressions", {
        "dem": dtm_path,
        "output": temp_breached,
        "max_length": breach_dist
    })

    if fill_deps:
        # 2. Fill Depressions
        run_wbt_command("FillDepressions", {
            "dem": temp_breached,
            "output": output_path,
            "fix_flats": True
        })
        if os.path.exists(temp_breached):
            os.remove(temp_breached)
    else:
        os.replace(temp_breached, output_path)

    print("  ✓ Pit filling completed")

def calculate_fdir_whitebox(dtm_path, output_path):
    """Calculate flow direction using WhiteboxTools (D8 Direct Call)"""
    print("  Using WhiteboxTools D8 flow direction (Direct CLI mode)...")
    
    run_wbt_command("D8Pointer", {
        "dem": dtm_path,
        "output": output_path,
        "esri_pntr": True
    })

    print("  ✓ Flow direction calculated")


def calculate_d8_flow_direction(dtm, dtm_mask, cellsize):
    """Calculate D8 flow direction - ArcGIS-compatible"""
    print("  Calculating D8 flow direction (ArcGIS-compatible)...")

    nrows, ncols = dtm.shape
    root2 = math.sqrt(2)

    fdir = np.zeros((nrows, ncols), dtype=np.uint8)
    fdir_nodata = 255

    neighbors = [
        (-1, 1, cellsize * root2, 128),
        (-1, 0, cellsize, 64),
        (-1, -1, cellsize * root2, 32),
        (0, -1, cellsize, 16),
        (1, -1, cellsize * root2, 8),
        (1, 0, cellsize, 4),
        (1, 1, cellsize * root2, 2),
        (0, 1, cellsize, 1),
    ]

    cells_processed = 0
    flat_cells = 0

    for r in range(nrows):
        if r % 50 == 0:
            print(f"    Processing row {r}/{nrows}...")

        for c in range(ncols):
            if dtm_mask[r, c]:
                fdir[r, c] = fdir_nodata
                continue

            elev_center = dtm[r, c]
            max_slope = -np.inf
            flow_direction = fdir_nodata

            for dr, dc, distance, d8_code in neighbors:
                nr, nc = r + dr, c + dc

                if nr < 0 or nr >= nrows or nc < 0 or nc >= ncols:
                    continue

                if dtm_mask[nr, nc]:
                    continue

                elev_neighbor = dtm[nr, nc]
                drop = elev_center - elev_neighbor
                slope = drop / distance

                if slope > max_slope:
                    max_slope = slope
                    flow_direction = d8_code

            if max_slope > 0:
                fdir[r, c] = flow_direction
                cells_processed += 1
            else:
                fdir[r, c] = fdir_nodata
                flat_cells += 1

    print(f"    ✓ Flow direction calculated")
    print(f"    Cells with flow: {cells_processed:,}")
    print(f"    Flat/pit cells: {flat_cells:,}")

    return fdir, fdir_nodata


# =========================================================================
# SHAPEFILE TO RASTER CONVERSION
# =========================================================================

def shapefile_to_raster(shapefile_path, ref_profile, elev_field=None):
    """Convert shapefile points to raster"""
    if not GEOPANDAS_AVAILABLE:
        raise RuntimeError("geopandas not available. Install with: pip install geopandas")

    print(f"  Reading shapefile: {shapefile_path}")
    gdf = gpd.read_file(shapefile_path)

    if gdf.crs is None:
        print(f"  ℹ Shapefile CRS: None - assuming same as DTM: {ref_profile['crs']}")
        gdf.set_crs(ref_profile["crs"], inplace=True)
    else:
        print(f"  ℹ Shapefile CRS: {gdf.crs} - DTM CRS: {ref_profile['crs']}")
        if gdf.crs != ref_profile["crs"]:
            print(f"  Reprojecting from {gdf.crs} to {ref_profile['crs']}")
            gdf = gdf.to_crs(ref_profile["crs"])

    print(f"  Number of points: {len(gdf)}")

    if elev_field and elev_field in gdf.columns:
        print(f"  Using elevation from field: {elev_field}")
        shapes = [(geom, value) for geom, value in zip(gdf.geometry, gdf[elev_field])]
    else:
        print("  Using constant value (will be replaced with DTM elevation)")
        shapes = [(geom, 1) for geom in gdf.geometry]

    source_raster = np.zeros((ref_profile["height"], ref_profile["width"]), dtype=np.float32)

    if shapes:
        rasterize(
            shapes,
            out=source_raster,
            transform=ref_profile["transform"],
            fill=0,
            dtype=np.float32
        )

    nodata = 0.0
    cells_with_source = (source_raster != nodata).sum()
    print(f"  ✓ Source raster created: {cells_with_source} cells with sources")

    return source_raster, nodata


def replace_source_with_dtm_elevation(source_raster, dtm, dtm_mask, nodata):
    """Replace source values with actual DTM elevation at those locations"""
    source_mask = (source_raster != nodata) & (~dtm_mask)

    if source_mask.any():
        elevations = dtm[source_mask]
        source_raster_out = np.full(source_raster.shape, nodata, dtype=np.float32)
        source_raster_out[source_mask] = elevations

        print(f"  ✓ Source values replaced with DTM elevations")
        sys.stdout.flush()
        sys.stderr.flush()
        print(f"    Elevation range: [{elevations.min():.2f}, {elevations.max():.2f}]m")

        return source_raster_out, nodata
    else:
        print("  ⚠ Warning: No valid source points found!")
        return source_raster, nodata


# =========================================================================
# PATH ALLOCATION FUNCTIONS
# =========================================================================

def path_allocation_li(dtm, dtm_mask, fdir_deg, fdir_mask, source_mask, cellsize,
                       max_slope_degrees, use_direction_aware,
                       hrma_from_thresh, hrma_to_thresh):
    """PathAllocation for LI with start_z propagation"""
    nrows, ncols = dtm.shape
    root2 = math.sqrt(2)

    moves = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
    move_angles = [0, 45, 90, 135, 180, 225, 270, 315]
    move_distances = [cellsize, cellsize * root2, cellsize, cellsize * root2,
                      cellsize, cellsize * root2, cellsize, cellsize * root2]

    uphill_tolerances = []
    for i in range(8):
        uphill_tol = calculate_uphill_tolerance(
            cellsize, max_slope_degrees, direction_idx=i,
            use_direction_aware=use_direction_aware
        )
        uphill_tolerances.append(uphill_tol)

    backlink_code = {
        (0, 1): 1, (1, 1): 2, (1, 0): 3, (1, -1): 4,
        (0, -1): 5, (-1, -1): 6, (-1, 0): 7, (-1, 1): 8, (0, 0): 0
    }

    dist = np.full((nrows, ncols), np.inf, dtype=np.float32)
    backlink = np.full((nrows, ncols), 32767, dtype=np.int16)
    start_z = np.full((nrows, ncols), np.nan, dtype=np.float32)

    src_pix = np.argwhere(source_mask)
    if src_pix.size == 0:
        raise RuntimeError("No source pixel found!")

    source_elevations = {}
    for sr, sc in src_pix:
        source_elevation = dtm[sr, sc]
        source_elevations[(sr, sc)] = source_elevation
        dist[sr, sc] = 0.0
        backlink[sr, sc] = 0
        start_z[sr, sc] = source_elevation

    pq = [(0.0, int(sr), int(sc)) for sr, sc in src_pix]
    heapq.heapify(pq)
    processed = 0

    while pq:
        cur_dist, r, c = heapq.heappop(pq)

        if cur_dist > dist[r, c]:
            continue

        if dtm_mask[r, c]:
            continue

        processed += 1
        if processed % 5000 == 0:
            print(f"    LI: Processed {processed:,} cells...")
            sys.stdout.flush()
            sys.stderr.flush()

        elev_from = dtm[r, c]
        horiz_dir_from = fdir_deg[r, c]
        current_source_elev = start_z[r, c]

        for move_idx in range(8):
            dr, dc = moves[move_idx]
            nr, nc = r + dr, c + dc

            if nr < 0 or nr >= nrows or nc < 0 or nc >= ncols:
                continue

            if dtm_mask[nr, nc]:
                continue

            elev_to = dtm[nr, nc]
            dz = elev_to - elev_from

            if dz > uphill_tolerances[move_idx]:
                continue

            surf_dist = move_distances[move_idx]
            move_dir = move_angles[move_idx]
            horiz_dir_to = fdir_deg[nr, nc]

            if not np.isnan(horiz_dir_from):
                hrma_from = abs(move_dir - horiz_dir_from)
                if hrma_from > 180:
                    hrma_from = 360 - hrma_from
                if hrma_from >= hrma_from_thresh:
                    continue

            if not np.isnan(horiz_dir_to):
                hrma_to = abs(move_dir - horiz_dir_to)
                if hrma_to > 180:
                    hrma_to = 360 - hrma_to
                if hrma_to >= hrma_to_thresh:
                    continue

            new_dist = cur_dist + surf_dist

            if new_dist < dist[nr, nc]:
                dist[nr, nc] = new_dist
                backlink[nr, nc] = backlink_code[(dr, dc)]
                start_z[nr, nc] = current_source_elev
                heapq.heappush(pq, (new_dist, int(nr), int(nc)))

    print(f"    LI: Total cells processed: {processed:,}")

    nodata_float = -9999.0
    nodata_int = 32767

    dist[dist == np.inf] = nodata_float
    dist[dtm_mask] = nodata_float
    backlink[backlink == 32767] = nodata_int
    backlink[dtm_mask] = nodata_int
    start_z[np.isnan(start_z)] = nodata_float
    start_z[dtm_mask] = nodata_float

    return dist, backlink, start_z, nodata_float, nodata_int


def path_allocation_fri(dtm, dtm_mask, fdir_deg, fdir_mask, source_mask, cellsize,
                        max_slope_degrees, use_direction_aware,
                        zero_factor, cut_angle, slope):
    """PathAllocation for FRI with LINEAR Horizontal Factor"""
    rows, cols = dtm.shape
    root2 = math.sqrt(2)

    neighbors = [
        (-1, 0, cellsize, 0, 0),
        (-1, 1, cellsize * root2, 1, 45),
        (0, 1, cellsize, 2, 90),
        (1, 1, cellsize * root2, 3, 135),
        (1, 0, cellsize, 4, 180),
        (1, -1, cellsize * root2, 5, 225),
        (0, -1, cellsize, 6, 270),
        (-1, -1, cellsize * root2, 7, 315),
    ]

    dist = np.full((rows, cols), np.inf, dtype=np.float32)
    backlink = np.full((rows, cols), -1, dtype=np.int16)
    visited = np.zeros((rows, cols), dtype=bool)

    source_pix = np.argwhere(source_mask)
    if source_pix.size == 0:
        raise RuntimeError("No source pixel found!")

    for sr, sc in source_pix:
        dist[sr, sc] = 0.0
        backlink[sr, sc] = 0

    heap = [(0.0, int(sr), int(sc)) for sr, sc in source_pix]
    heapq.heapify(heap)
    visited_count = 0

    while heap:
        d, r, c = heapq.heappop(heap)

        if visited[r, c]:
            continue

        visited[r, c] = True
        visited_count += 1

        if visited_count % 5000 == 0:
            print(f"    FRI: Processed {visited_count:,} cells...")
            sys.stdout.flush()
            sys.stderr.flush()

        z_curr = dtm[r, c]
        fdir_curr = fdir_deg[r, c]

        for dr, dc, dist_base, dir_idx, move_angle in neighbors:
            nr, nc = r + dr, c + dc

            if not (0 <= nr < rows and 0 <= nc < cols):
                continue

            if visited[nr, nc] or dtm_mask[nr, nc] or fdir_mask[nr, nc]:
                continue

            z_next = dtm[nr, nc]
            dz = z_next - z_curr

            uphill_tol = calculate_uphill_tolerance(cellsize, max_slope_degrees,
                                                    dir_idx, use_direction_aware)

            if dz > uphill_tol:
                continue

            fdir_next = fdir_deg[nr, nc]

            angle_from = None
            angle_to = None

            if not np.isnan(fdir_curr):
                angle_diff_from = move_angle - fdir_curr
                while angle_diff_from > 180:
                    angle_diff_from -= 360
                while angle_diff_from < -180:
                    angle_diff_from += 360
                angle_from = abs(angle_diff_from)

            if not np.isnan(fdir_next):
                angle_diff_to = move_angle - fdir_next
                while angle_diff_to > 180:
                    angle_diff_to -= 360
                while angle_diff_to < -180:
                    angle_diff_to += 360
                angle_to = abs(angle_diff_to)

            if angle_from is not None and angle_to is not None:
                if angle_from > cut_angle or angle_to > cut_angle:
                    continue
                avg_angle = (angle_from + angle_to) / 2.0
            elif angle_from is not None:
                if angle_from > cut_angle:
                    continue
                avg_angle = angle_from
            elif angle_to is not None:
                if angle_to > cut_angle:
                    continue
                avg_angle = angle_to
            else:
                avg_angle = 0.0

            hf = zero_factor + avg_angle * slope
            cost = dist_base * hf
            new_dist = d + cost

            if new_dist < dist[nr, nc]:
                dist[nr, nc] = new_dist
                backlink[nr, nc] = (dir_idx + 4) % 8 + 1
                heapq.heappush(heap, (new_dist, nr, nc))

    print(f"    FRI: Total cells reached: {visited_count:,}")

    nodata_f = -3.4028234663852886e+38
    nodata_i = 32767

    dist[~visited | dtm_mask] = nodata_f
    backlink[~visited | dtm_mask] = nodata_i

    return dist, backlink, nodata_f, nodata_i


# =========================================================================
# SINGLE SOURCE PROCESSING
# =========================================================================

def process_single_source_point(sr, sc, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg):
    """
    Process a SINGLE source point individually and return all rasters

    Args:
        sr, sc: Row and column of the source point
        dtm: Digital terrain model
        dtm_mask: DTM nodata mask
        fdir_deg: Flow direction in degrees
        fdir_mask: Flow direction mask
        cellsize: Cell size
        cfg: Configuration object

    Returns:
        dict with pq_lim, li, backlink_li, fri, backlink_fri and nodata values
    """
    # Create source mask for ONLY this single point
    source_mask = np.zeros(dtm.shape, dtype=bool)
    source_mask[sr, sc] = True
    source_mask &= ~dtm_mask

    # Run LI for this single source
    li, backlink_li, start_z, nd_f_li, nd_i_li = path_allocation_li(
        dtm, dtm_mask, fdir_deg, fdir_mask, source_mask, cellsize,
        cfg.MAX_SLOPE_DEGREES, cfg.USE_DIRECTION_AWARE_UPHILL,
        cfg.HRMA_FROM_THRESH_LI, cfg.HRMA_TO_THRESH_LI
    )

    # Run FRI for this single source
    fri, backlink_fri, nd_f_fri, nd_i_fri = path_allocation_fri(
        dtm, dtm_mask, fdir_deg, fdir_mask, source_mask, cellsize,
        cfg.MAX_SLOPE_DEGREES, cfg.USE_DIRECTION_AWARE_UPHILL,
        cfg.ZERO_FACTOR, cfg.CUT_ANGLE, cfg.SLOPE
    )

    # Calculate HI (vertical drop)
    hi = np.full(dtm.shape, nd_f_li, dtype=np.float32)
    valid_li = (li != nd_f_li) & (li >= 0) & (~dtm_mask)
    hi[valid_li] = start_z[valid_li] - dtm[valid_li]

    # Calculate H/L - either with path distance or euclidean distance
    h_l = np.full(dtm.shape, nd_f_li, dtype=np.float32)

    if cfg.USE_DIRECT_DISTANCE_FOR_HL:
        # Calculate euclidean distance from source point
        nrows, ncols = dtm.shape
        rows_grid, cols_grid = np.meshgrid(np.arange(nrows), np.arange(ncols), indexing='ij')

        # Calculate euclidean distance in map units
        euclidean_dist = np.sqrt(
            ((rows_grid - sr) * cellsize) ** 2 +
            ((cols_grid - sc) * cellsize) ** 2
        )

        # Calculate H/L with euclidean distance
        valid_hl = valid_li & (euclidean_dist > 0)
        h_l[valid_hl] = hi[valid_hl] / euclidean_dist[valid_hl]
    else:
        # Original behavior: use path distance
        valid_hl = valid_li & (li > 0)
        h_l[valid_hl] = hi[valid_hl] / li[valid_hl]

    # Apply H/L threshold
    h_l_lim = np.full(dtm.shape, nd_f_li, dtype=np.float32)
    valid_lim = (h_l != nd_f_li) & (h_l >= cfg.H_L_THRESHOLD)
    h_l_lim[valid_lim] = h_l[valid_lim]

    # Calculate PQI
    pqi = np.full(dtm.shape, nd_f_li, dtype=np.float32)
    valid_pqi = valid_li & (fri != nd_f_fri) & (fri > 0)
    pqi[valid_pqi] = li[valid_pqi] / fri[valid_pqi]

    # Calculate PQ_LIM - CRITICAL: only where H/L threshold is met
    pq_lim = np.full(dtm.shape, nd_f_li, dtype=np.float32)
    valid_pqlim = valid_lim & valid_pqi
    pq_lim[valid_pqlim] = pqi[valid_pqlim]

    return {
        'pq_lim': pq_lim,
        'li': li,
        'backlink_li': backlink_li,
        'fri': fri,
        'backlink_fri': backlink_fri,
        'nodata_float': nd_f_li,
        'nodata_int': nd_i_li,
        'source_row': sr,
        'source_col': sc
    }


# =========================================================================
# PARALLEL PROCESSING WORKER
# =========================================================================

def process_single_point_worker(point_info, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg_dict):
    """
    Worker function for parallel processing of a single source point.

    Args:
        point_info: tuple (sr, sc, point_index)
        dtm, dtm_mask, fdir_deg, fdir_mask: Arrays
        cellsize: Cell size
        cfg_dict: Configuration as dictionary

    Returns:
        Result dictionary from process_single_source_point plus point_index
    """
    sr, sc, point_idx = point_info

    # Reconstruct config object from dict
    class TempConfig:
        def __init__(self, d):
            for k, v in d.items():
                setattr(self, k, v)

    cfg = TempConfig(cfg_dict)

    result = process_single_source_point(sr, sc, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg)
    result['point_index'] = point_idx

    return result


def process_sources_parallel(src_pix_all, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg):
    """
    Process all source points using parallel workers.

    IMPORTANT: Each source point is processed completely independently to ensure
    correct PQ_LIM values. Results are combined using MAX operation.

    Args:
        src_pix_all: Array of (row, col) for all source points
        dtm, dtm_mask, fdir_deg, fdir_mask: Input arrays
        cellsize: Cell size
        cfg: Configuration object

    Returns:
        Combined results dictionary
    """
    if not MULTIPROCESSING_AVAILABLE:
        raise RuntimeError("Multiprocessing not available. Set ENABLE_PARALLEL_PROCESSING=False")

    num_sources = len(src_pix_all)
    print(f"\n  🚀 PARALLEL PROCESSING MODE")
    print(f"    Workers: {cfg.NUM_WORKERS}")
    print(f"    Total source points: {num_sources}")

    # Convert config to dict for pickling
    cfg_dict = {
        'MAX_SLOPE_DEGREES': cfg.MAX_SLOPE_DEGREES,
        'H_L_THRESHOLD': cfg.H_L_THRESHOLD,
        'USE_DIRECTION_AWARE_UPHILL': cfg.USE_DIRECTION_AWARE_UPHILL,
        'HRMA_FROM_THRESH_LI': cfg.HRMA_FROM_THRESH_LI,
        'HRMA_TO_THRESH_LI': cfg.HRMA_TO_THRESH_LI,
        'ZERO_FACTOR': cfg.ZERO_FACTOR,
        'CUT_ANGLE': cfg.CUT_ANGLE,
        'SLOPE': cfg.SLOPE,
        'USE_DIRECT_DISTANCE_FOR_HL': cfg.USE_DIRECT_DISTANCE_FOR_HL
    }

    # Prepare point info list: (row, col, index)
    points_info = [(int(sr), int(sc), i) for i, (sr, sc) in enumerate(src_pix_all)]

    # Initialize combined results
    nodata_f = -9999.0
    nodata_i = 32767

    combined_pq_lim = np.full(dtm.shape, nodata_f, dtype=np.float32)
    combined_li = np.full(dtm.shape, nodata_f, dtype=np.float32)
    combined_backlink_li = np.full(dtm.shape, nodata_i, dtype=np.int16)
    combined_fri = np.full(dtm.shape, nodata_f, dtype=np.float32)
    combined_backlink_fri = np.full(dtm.shape, nodata_i, dtype=np.int16)

    # Create worker function with fixed parameters
    worker_func = partial(
        process_single_point_worker,
        dtm=dtm,
        dtm_mask=dtm_mask,
        fdir_deg=fdir_deg,
        fdir_mask=fdir_mask,
        cellsize=cellsize,
        cfg_dict=cfg_dict
    )

    # Process points in parallel
    with mp.Pool(processes=cfg.NUM_WORKERS) as pool:
        # Use imap for progress tracking
        results_iter = pool.imap(worker_func, points_info)

        processed = 0
        for result in results_iter:
            processed += 1

            if processed % 10 == 0 or processed == num_sources:
                print(f"    Progress: {processed}/{num_sources} points ({100 * processed / num_sources:.1f}%)")
                sys.stdout.flush()
                sys.stderr.flush()

            # Combine result with existing using MAX strategy
            # CRITICAL: Only update where new values are valid AND higher

            # PQ_LIM
            valid_new = (result['pq_lim'] != nodata_f) & (result['pq_lim'] > 0)
            valid_existing = (combined_pq_lim != nodata_f) & (combined_pq_lim > 0)

            # Where both exist, take max
            both_valid = valid_new & valid_existing
            combined_pq_lim[both_valid] = np.maximum(
                combined_pq_lim[both_valid],
                result['pq_lim'][both_valid]
            )

            # Where only new exists, use new
            only_new = valid_new & ~valid_existing
            combined_pq_lim[only_new] = result['pq_lim'][only_new]

            # LI - keep from source with highest PQ_LIM
            valid_new = (result['li'] != nodata_f) & (result['li'] >= 0)
            valid_existing = (combined_li != nodata_f) & (combined_li >= 0)

            mask_update = valid_new & (
                    ~valid_existing |
                    (result['pq_lim'] > combined_pq_lim)
            )
            combined_li[mask_update] = result['li'][mask_update]
            combined_backlink_li[mask_update] = result['backlink_li'][mask_update]

            # FRI - keep from source with highest PQ_LIM
            valid_new = (result['fri'] != nodata_f) & (result['fri'] >= 0)
            valid_existing = (combined_fri != nodata_f) & (combined_fri >= 0)

            mask_update = valid_new & (
                    ~valid_existing |
                    (result['pq_lim'] > combined_pq_lim)
            )
            combined_fri[mask_update] = result['fri'][mask_update]
            combined_backlink_fri[mask_update] = result['backlink_fri'][mask_update]

    print(f"  ✓ Parallel processing completed")

    valid_pqlim = ((combined_pq_lim != nodata_f) & (combined_pq_lim > 0)).sum()
    print(f"    Final cells with PQ_LIM: {valid_pqlim:,}")

    return {
        'pq_lim': combined_pq_lim,
        'li': combined_li,
        'backlink_li': combined_backlink_li,
        'fri': combined_fri,
        'backlink_fri': combined_backlink_fri,
        'nodata_float': nodata_f,
        'nodata_int': nodata_i
    }


# =========================================================================
# BATCH PROCESSING FOR REGIONAL SCALE
# =========================================================================

def process_source_batch(batch_indices, dtm, dtm_mask, fdir_deg, fdir_mask,
                         source_raster, src_nodata, cellsize, cfg):
    """
    Process a batch of source points, EACH INDIVIDUALLY, and combine with MAX

    ⚠️  IMPORTANT: Each source point is processed SEPARATELY, not as a multisource.
        This ensures PQ_LIM values remain in the expected range (~0-2).

    Args:
        batch_indices: List of (row, col) tuples for source points in this batch
        dtm: Digital terrain model
        dtm_mask: DTM nodata mask
        fdir_deg: Flow direction in degrees
        fdir_mask: Flow direction mask
        source_raster: Full source raster (not used but kept for compatibility)
        src_nodata: Source nodata value (not used but kept for compatibility)
        cellsize: Cell size
        cfg: Configuration object

    Returns:
        dict containing combined rasters from all points in batch using MAX strategy
    """
    nodata_f = -9999.0
    nodata_i = 32767

    # Initialize combined rasters with nodata
    combined_pq_lim = np.full(dtm.shape, nodata_f, dtype=np.float32)
    combined_li = np.full(dtm.shape, nodata_f, dtype=np.float32)
    combined_backlink_li = np.full(dtm.shape, nodata_i, dtype=np.int16)
    combined_fri = np.full(dtm.shape, nodata_f, dtype=np.float32)
    combined_backlink_fri = np.full(dtm.shape, nodata_i, dtype=np.int16)

    # Process each source point INDIVIDUALLY
    for point_idx, (sr, sc) in enumerate(batch_indices):
        if (point_idx + 1) % 10 == 0 or point_idx == len(batch_indices) - 1:
            print(f"      Point {point_idx + 1}/{len(batch_indices)}")
            sys.stdout.flush()
            sys.stderr.flush()

        # Process this SINGLE point
        result = process_single_source_point(
            sr, sc, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg
        )

        # Combine with previous results using MAX
        # For PQ_LIM
        valid_new = (result['pq_lim'] != nodata_f) & (result['pq_lim'] > 0)
        valid_existing = (combined_pq_lim != nodata_f) & (combined_pq_lim > 0)

        # Where both exist, take max
        both_valid = valid_new & valid_existing
        combined_pq_lim[both_valid] = np.maximum(combined_pq_lim[both_valid],
                                                 result['pq_lim'][both_valid])

        # Where only new exists, use new
        only_new = valid_new & ~valid_existing
        combined_pq_lim[only_new] = result['pq_lim'][only_new]

        # For LI
        valid_new = (result['li'] != nodata_f) & (result['li'] > 0)
        valid_existing = (combined_li != nodata_f) & (combined_li > 0)
        both_valid = valid_new & valid_existing
        combined_li[both_valid] = np.maximum(combined_li[both_valid],
                                             result['li'][both_valid])
        only_new = valid_new & ~valid_existing
        combined_li[only_new] = result['li'][only_new]

        # For FRI
        valid_new = (result['fri'] != nodata_f) & (result['fri'] > 0)
        valid_existing = (combined_fri != nodata_f) & (combined_fri > 0)
        both_valid = valid_new & valid_existing
        combined_fri[both_valid] = np.maximum(combined_fri[both_valid],
                                              result['fri'][both_valid])
        only_new = valid_new & ~valid_existing
        combined_fri[only_new] = result['fri'][only_new]

        # For backlinks, keep from the highest value
        mask_update_li = (result['pq_lim'] > combined_pq_lim)
        combined_backlink_li[mask_update_li] = result['backlink_li'][mask_update_li]

        mask_update_fri = (result['fri'] > combined_fri)
        combined_backlink_fri[mask_update_fri] = result['backlink_fri'][mask_update_fri]

    return {
        'pq_lim': combined_pq_lim,
        'li': combined_li,
        'backlink_li': combined_backlink_li,
        'fri': combined_fri,
        'backlink_fri': combined_backlink_fri,
        'nodata_float': nodata_f,
        'nodata_int': nodata_i
    }


def combine_rasters_max(raster_arrays, nodata):
    """
    Combine multiple raster arrays taking the MAXIMUM value where they overlap

    Args:
        raster_arrays: List of raster arrays
        nodata: NoData value

    Returns:
        combined: Combined raster with maximum values
    """
    if len(raster_arrays) == 0:
        raise RuntimeError("No rasters to combine")

    if len(raster_arrays) == 1:
        return raster_arrays[0]

    # Initialize with first array
    combined = raster_arrays[0].copy()

    # For each subsequent array, take max where both have valid values
    for i, raster in enumerate(raster_arrays[1:], 2):
        # Valid cells in current combined
        valid_combined = (combined != nodata) & (combined > 0)

        # Valid cells in new array
        valid_new = (raster != nodata) & (raster > 0)

        # Where both are valid, take maximum
        both_valid = valid_combined & valid_new
        combined[both_valid] = np.maximum(combined[both_valid], raster[both_valid])

        # Where only new is valid, use new
        only_new = valid_new & ~valid_combined
        combined[only_new] = raster[only_new]

    return combined


def combine_batch_results(batch_results, nodata_float, nodata_int):
    """
    Combine all batch results using MAX for overlapping zones

    Args:
        batch_results: List of result dicts from process_source_batch
        nodata_float: NoData value for float rasters
        nodata_int: NoData value for int rasters

    Returns:
        dict with combined results
    """
    print(f"\n  Combining {len(batch_results)} batch results (using MAX)...")
    sys.stdout.flush()
    sys.stderr.flush()

    # Extract arrays from results
    pq_lim_arrays = [r['pq_lim'] for r in batch_results]
    li_arrays = [r['li'] for r in batch_results]
    backlink_li_arrays = [r['backlink_li'] for r in batch_results]
    fri_arrays = [r['fri'] for r in batch_results]
    backlink_fri_arrays = [r['backlink_fri'] for r in batch_results]

    # Combine PQ_LIM
    print(f"    Combining PQ_LIM arrays...")
    pq_lim_final = combine_rasters_max(pq_lim_arrays, nodata_float)
    valid_pqlim = ((pq_lim_final != nodata_float) & (pq_lim_final > 0)).sum()
    print(f"    ✓ PQ_LIM combined: {valid_pqlim:,} valid cells")

    # Combine LI
    print(f"    Combining LI arrays...")
    li_final = combine_rasters_max(li_arrays, nodata_float)
    valid_li = ((li_final != nodata_float) & (li_final > 0)).sum()
    print(f"    ✓ LI combined: {valid_li:,} valid cells")

    # Combine FRI
    print(f"    Combining FRI arrays...")
    fri_final = combine_rasters_max(fri_arrays, nodata_float)
    valid_fri = ((fri_final != nodata_float) & (fri_final > 0)).sum()
    print(f"    ✓ FRI combined: {valid_fri:,} valid cells")

    # For backlink, keep from the highest PQ_LIM value at each location
    print(f"    Processing backlink arrays...")
    backlink_li_final = backlink_li_arrays[0].copy()
    backlink_fri_final = backlink_fri_arrays[0].copy()

    for i in range(1, len(batch_results)):
        # For LI backlink, keep where PQ_LIM is highest
        mask_update_li = (pq_lim_arrays[i] > pq_lim_arrays[0])
        backlink_li_final[mask_update_li] = backlink_li_arrays[i][mask_update_li]

        # For FRI backlink, keep where LI is highest
        mask_update_fri = (li_arrays[i] > li_arrays[0])
        backlink_fri_final[mask_update_fri] = backlink_fri_arrays[i][mask_update_fri]

    valid_bl_li = ((backlink_li_final != nodata_int) & (backlink_li_final > -32768)).sum()
    valid_bl_fri = ((backlink_fri_final != nodata_int) & (backlink_fri_final > -32768)).sum()
    print(f"    ✓ Backlink LI: {valid_bl_li:,} valid cells")
    print(f"    ✓ Backlink FRI: {valid_bl_fri:,} valid cells")

    return {
        'pq_lim': pq_lim_final,
        'li': li_final,
        'backlink_li': backlink_li_final,
        'fri': fri_final,
        'backlink_fri': backlink_fri_final,
        'nodata_float': nodata_float,  # AGGIUNTO
        'nodata_int': nodata_int
    }


# =========================================================================
# MAIN WORKFLOW
# =========================================================================

def main():
    """Complete MSF workflow for regional scale analysis"""

    cfg = Config()

    print_header("MSF REGIONAL SCALE WORKFLOW v3.2")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Print configuration
    print("\n📋 CONFIGURATION:")
    print(f"  Source input: {cfg.SOURCE_INPUT_TYPE}")

    if cfg.ENABLE_PARALLEL_PROCESSING:
        print(f"  Processing mode: PARALLEL ({cfg.NUM_WORKERS} workers)")
    else:
        print(f"  Processing mode: SEQUENTIAL BATCH (size: {cfg.BATCH_SIZE})")

    print(f"  Overlap method: {cfg.OVERLAP_METHOD} (maximum values)")

    if cfg.RESAMPLE_DTM:
        print(f"  DTM Resampling: YES → {cfg.TARGET_RESOLUTION}m (method: {cfg.AGGREGATION_METHOD})")
        print(f"    Pit filling: AUTOMATIC (after resampling)")
        print(f"    Flow direction: AUTOMATIC (after resampling)")
    else:
        print(f"  DTM Resampling: NO")
        print(f"  Pit filling: {'YES' if cfg.DO_PIT_FILLING else 'NO'}")
        print(f"  Flow direction: {'CALCULATE' if cfg.CALCULATE_FLOW_DIRECTION else 'USE EXISTING'}")

    print(f"  H/L threshold: {cfg.H_L_THRESHOLD}")
    print(f"  H/L calculation: {'EUCLIDEAN DISTANCE' if cfg.USE_DIRECT_DISTANCE_FOR_HL else 'PATH DISTANCE'}")

    print("\n📊 OPTIONAL OUTPUTS:")
    print(f"  Save LI raster: {'YES' if cfg.SAVE_LI_RASTER else 'NO'}")
    print(f"  Save LI backlink: {'YES' if cfg.SAVE_LI_BACKLINK else 'NO'}")
    print(f"  Save FRI raster: {'YES' if cfg.SAVE_FRI_RASTER else 'NO'}")
    print(f"  Save FRI backlink: {'YES' if cfg.SAVE_FRI_BACKLINK else 'NO'}")

    os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)

    total_steps = 14
    if cfg.RESAMPLE_DTM:
        total_steps += 1

    current_step = 0

    # -------------------------------------------------------------------------
    # STEP: Read input DTM
    # -------------------------------------------------------------------------
    current_step += 1
    print_step(current_step, total_steps, "Reading input DTM")

    # If we are resampling or filling pits, we MUST start from original DTM
    # If we are NOT filling pits, we check if a filled DTM is provided; if not, we use original.
    if cfg.RESAMPLE_DTM or cfg.DO_PIT_FILLING or not cfg.DTM_FILLED_PATH:
        dtm_input_path = cfg.DTM_ORIGINAL_PATH
        print(f"  Reading base DTM: {dtm_input_path}")
    else:
        dtm_input_path = cfg.DTM_FILLED_PATH
        print(f"  Reading provided filled DTM: {dtm_input_path}")

    with rasterio.open(dtm_input_path) as src:
        dtm_input = src.read(1).astype(np.float32)
        input_prof = src.profile
        dtm_nodata = src.nodata
        original_cellsize = abs(input_prof["transform"].a)

    print(f"  DTM shape: {dtm_input.shape[0]} x {dtm_input.shape[1]}")
    print(f"  Original cellsize: {original_cellsize}m")

    dtm_mask_input = make_mask(dtm_input, dtm_nodata)
    print(f"  Valid cells: {(~dtm_mask_input).sum():,}")

    # -------------------------------------------------------------------------
    # STEP: Resample DTM (if requested)
    # -------------------------------------------------------------------------
    if cfg.RESAMPLE_DTM:
        current_step += 1
        print_step(current_step, total_steps, f"Resampling DTM to {cfg.TARGET_RESOLUTION}m")

        temp_input_path = os.path.join(cfg.OUTPUT_DIR, "dtm_input_temp.tif")
        save_raster(dtm_input, input_prof, temp_input_path, dtm_nodata, cfg.COMPRESS_OUTPUTS)

        resampled_output_path = os.path.join(cfg.OUTPUT_DIR, f"dtm_resampled_{cfg.TARGET_RESOLUTION}m.tif")
        dtm, ref_prof, original_prof = resample_dtm_aggregate(
            temp_input_path,
            cfg.TARGET_RESOLUTION,
            cfg.AGGREGATION_METHOD,
            resampled_output_path
        )

        if os.path.exists(temp_input_path):
            os.remove(temp_input_path)

        dtm_mask = make_mask(dtm, dtm_nodata)
        cellsize = abs(ref_prof["transform"].a)

        force_pit_fill = True
        force_flow_dir = True
    else:
        dtm = dtm_input
        ref_prof = input_prof
        dtm_mask = dtm_mask_input
        cellsize = original_cellsize
        force_pit_fill = cfg.DO_PIT_FILLING
        force_flow_dir = cfg.CALCULATE_FLOW_DIRECTION

    # -------------------------------------------------------------------------
    # STEP: Fill pits
    # -------------------------------------------------------------------------
    if force_pit_fill:
        current_step += 1
        print_step(current_step, total_steps, "Filling pits in DTM")

        if cfg.USE_WHITEBOX_FILLING and WHITEBOX_AVAILABLE:
            dtm_filled_path = os.path.join(cfg.OUTPUT_DIR, "dtm_filled.tif")

            temp_dtm_path = os.path.join(cfg.OUTPUT_DIR, "dtm_temp.tif")
            save_raster(dtm, ref_prof, temp_dtm_path, dtm_nodata, cfg.COMPRESS_OUTPUTS)

            fill_pits_whitebox(temp_dtm_path, dtm_filled_path,
                               cfg.WBT_BREACH_DIST, cfg.WBT_FILL_DEPS)

            with rasterio.open(dtm_filled_path) as src:
                dtm = src.read(1).astype(np.float32)

            if os.path.exists(temp_dtm_path):
                os.remove(temp_dtm_path)
        else:
            dtm = fill_pits_custom(dtm, dtm_mask, dtm_nodata)

            if cfg.SAVE_INTERMEDIATE_OUTPUTS:
                dtm_filled_path = os.path.join(cfg.OUTPUT_DIR, "dtm_filled.tif")
                save_raster(dtm, ref_prof, dtm_filled_path, dtm_nodata, cfg.COMPRESS_OUTPUTS)

        dtm_mask = make_mask(dtm, dtm_nodata)
        print(f"  ✓ DTM filled")

    # -------------------------------------------------------------------------
    # STEP: Calculate flow direction
    # -------------------------------------------------------------------------
    current_step += 1
    print_step(current_step, total_steps, "Flow direction")

    # If we are forced to calculate or if NO existing FDIR path is provided
    if force_flow_dir or not cfg.FDIR_PATH:
        if not force_flow_dir:
             print("  ℹ No external FDIR provided, calculating now...")
        
        if cfg.USE_WHITEBOX_FDIR and WHITEBOX_AVAILABLE:
            fdir_path = os.path.join(cfg.OUTPUT_DIR, "fdir_calculated.tif")

            temp_dtm_path = os.path.join(cfg.OUTPUT_DIR, "dtm_for_fdir.tif")
            if not os.path.exists(temp_dtm_path):
                save_raster(dtm, ref_prof, temp_dtm_path, dtm_nodata, cfg.COMPRESS_OUTPUTS)

            calculate_fdir_whitebox(temp_dtm_path, fdir_path)

            with rasterio.open(fdir_path) as src:
                fdir = src.read(1).astype(np.uint8)
                fdir_nodata = src.nodata if src.nodata is not None else 255
        else:
            fdir, fdir_nodata = calculate_d8_flow_direction(dtm, dtm_mask, cellsize)

            if cfg.SAVE_INTERMEDIATE_OUTPUTS:
                fdir_path = os.path.join(cfg.OUTPUT_DIR, "fdir_calculated.tif")
                prof = ref_prof.copy()
                prof.update(dtype="uint8", nodata=fdir_nodata)
                save_raster(fdir, prof, fdir_path, fdir_nodata, cfg.COMPRESS_OUTPUTS)
    else:
        print(f"  Using existing flow direction: {cfg.FDIR_PATH}")
        fdir, fdir_nodata = read_and_snap(cfg.FDIR_PATH, ref_prof)
        fdir = fdir.astype(np.uint8)
        if fdir_nodata is None:
            fdir_nodata = 255

    fdir_mask = make_mask(fdir, fdir_nodata)
    fdir_deg = fdir_to_degrees(fdir.astype(np.int32), fdir_nodata)

    valid_fdir = (~fdir_mask).sum()
    print(f"  ✓ Flow direction ready")
    print(f"    Valid cells: {valid_fdir:,} / {dtm.size:,}")

    # -------------------------------------------------------------------------
    # STEP: Prepare source raster
    # -------------------------------------------------------------------------
    current_step += 1
    print_step(current_step, total_steps, "Preparing source raster")

    if cfg.SOURCE_INPUT_TYPE.upper() == "SHAPEFILE":
        print(f"  Converting shapefile to raster...")
        source_raster, src_nodata = shapefile_to_raster(
            cfg.SOURCE_SHAPEFILE_PATH,
            ref_prof,
            cfg.SHAPEFILE_ELEV_FIELD
        )

        if cfg.SHAPEFILE_ELEV_FIELD is None:
            source_raster, src_nodata = replace_source_with_dtm_elevation(
                source_raster, dtm, dtm_mask, src_nodata
            )

        if cfg.SAVE_INTERMEDIATE_OUTPUTS:
            source_path = os.path.join(cfg.OUTPUT_DIR, "source_from_shapefile.tif")
            save_raster(source_raster, ref_prof, source_path, src_nodata, cfg.COMPRESS_OUTPUTS)
    else:
        print(f"  Reading source raster: {cfg.SOURCE_RASTER_PATH}")
        source_raster, src_nodata = read_and_snap(cfg.SOURCE_RASTER_PATH, ref_prof)

    src_mask = make_mask(source_raster, src_nodata)
    source_mask_full = (~src_mask) & (source_raster != 0) & (~dtm_mask)

    num_sources = source_mask_full.sum()
    if num_sources == 0:
        raise RuntimeError("No valid source pixels found!")

    print(f"  ✓ Source raster ready")
    print(f"    Total number of source points: {num_sources}")

    # Get all source point indices
    src_pix_all = np.argwhere(source_mask_full)

    # -------------------------------------------------------------------------
    # STEP: Process sources (parallel or batch)
    # -------------------------------------------------------------------------
    current_step += 1

    if cfg.ENABLE_PARALLEL_PROCESSING:
        print_step(current_step, total_steps, "Processing sources in PARALLEL")

        if not MULTIPROCESSING_AVAILABLE:
            print("  ⚠ WARNING: Multiprocessing not available, falling back to sequential processing")
            cfg.ENABLE_PARALLEL_PROCESSING = False

        if cfg.ENABLE_PARALLEL_PROCESSING:
            combined = process_sources_parallel(
                src_pix_all, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg
            )

    if not cfg.ENABLE_PARALLEL_PROCESSING:
        print_step(current_step, total_steps, "Processing sources in BATCHES (sequential)")

        # Divide sources into batches
        num_batches = int(np.ceil(num_sources / cfg.BATCH_SIZE))
        print(f"  Number of batches: {num_batches} (batch size: {cfg.BATCH_SIZE})")

        batch_results = []

        for batch_idx in range(num_batches):
            start_idx = batch_idx * cfg.BATCH_SIZE
            end_idx = min((batch_idx + 1) * cfg.BATCH_SIZE, num_sources)

            batch_sources = src_pix_all[start_idx:end_idx]

            print(f"\n  Processing batch {batch_idx + 1}/{num_batches}")
            print(f"  Sources in this batch: {len(batch_sources)}")

            # Show first few sources in batch
            for i, (sr, sc) in enumerate(batch_sources[:3]):
                print(f"    Source {i + 1}: row={sr}, col={sc}, elev={dtm[sr, sc]:.2f}m")
            if len(batch_sources) > 3:
                print(f"    ... and {len(batch_sources) - 3} more")

            # Process this batch
            batch_result = process_source_batch(
                batch_sources, dtm, dtm_mask, fdir_deg, fdir_mask,
                source_raster, src_nodata, cellsize, cfg
            )

            valid_cells = ((batch_result['pq_lim'] != batch_result['nodata_float']) &
                           (batch_result['pq_lim'] > 0)).sum()
            print(f"  ✓ Batch {batch_idx + 1} completed: {valid_cells:,} cells reached")

            batch_results.append(batch_result)

        # Combine batch results
        current_step += 1
        print_step(current_step, total_steps, "Combining batch results")

        if len(batch_results) > 0:
            nodata_f = batch_results[0]['nodata_float']
            nodata_i = batch_results[0]['nodata_int']
            combined = combine_batch_results(batch_results, nodata_f, nodata_i)
        else:
            raise RuntimeError("No batch results to combine!")

    # -------------------------------------------------------------------------
    # STEP: Save final outputs
    # -------------------------------------------------------------------------
    current_step += 1
    print_step(current_step, total_steps, "Saving outputs")

    prof = ref_prof.copy()
    nodata_f = combined['nodata_float']
    nodata_i = combined['nodata_int']

    # Save PQ_LIM (always)
    print("\n  Saving PQ_LIM...")
    prof_float = prof.copy()
    prof_float.update(dtype="float32", nodata=nodata_f)

    pq_lim_filename = getattr(cfg, "PQLIM_OUTPUT_FILENAME", "pq_lim.tif")
    if not pq_lim_filename.endswith(".tif"):
        pq_lim_filename += ".tif"

    pq_lim_path = os.path.join(cfg.OUTPUT_DIR, pq_lim_filename)
    save_raster(combined['pq_lim'], prof_float, pq_lim_path, nodata_f, cfg.COMPRESS_OUTPUTS)

    # Save LI (if enabled)
    if cfg.SAVE_LI_RASTER:
        print("  Saving LI raster...")
        li_filename = "li_distance.tif"
        li_path = os.path.join(cfg.OUTPUT_DIR, li_filename)
        save_raster(combined['li'], prof_float, li_path, nodata_f, cfg.COMPRESS_OUTPUTS)

    # Save LI backlink (if enabled)
    if cfg.SAVE_LI_BACKLINK:
        print("  Saving LI backlink...")
        prof_int = prof.copy()
        prof_int.update(dtype="int16", nodata=nodata_i)
        backlink_li_filename = "backlink_li.tif"
        backlink_li_path = os.path.join(cfg.OUTPUT_DIR, backlink_li_filename)
        save_raster(combined['backlink_li'], prof_int, backlink_li_path, nodata_i, cfg.COMPRESS_OUTPUTS)

    # Save FRI (if enabled)
    if cfg.SAVE_FRI_RASTER:
        print("  Saving FRI raster...")
        fri_filename = "fri_distance.tif"
        fri_path = os.path.join(cfg.OUTPUT_DIR, fri_filename)
        save_raster(combined['fri'], prof_float, fri_path, nodata_f, cfg.COMPRESS_OUTPUTS)

    # Save FRI backlink (if enabled)
    if cfg.SAVE_FRI_BACKLINK:
        print("  Saving FRI backlink...")
        prof_int = prof.copy()
        prof_int.update(dtype="int16", nodata=nodata_i)
        backlink_fri_filename = "backlink_fri.tif"
        backlink_fri_path = os.path.join(cfg.OUTPUT_DIR, backlink_fri_filename)
        save_raster(combined['backlink_fri'], prof_int, backlink_fri_path, nodata_i, cfg.COMPRESS_OUTPUTS)

    # -------------------------------------------------------------------------
    # STEP: Summary statistics
    # -------------------------------------------------------------------------
    current_step += 1
    print_step(current_step, total_steps, "Summary statistics")

    valid_pqlim = (combined['pq_lim'] != nodata_f) & (combined['pq_lim'] > 0)

    print(f"\n  📊 FINAL RESULTS:")
    print(f"    Total source points processed: {num_sources}")
    if cfg.ENABLE_PARALLEL_PROCESSING:
        print(f"    Processing mode: PARALLEL ({cfg.NUM_WORKERS} workers)")
    else:
        print(f"    Processing mode: SEQUENTIAL ({num_batches} batches)")
    print(f"    H/L calculation method: {'EUCLIDEAN' if cfg.USE_DIRECT_DISTANCE_FOR_HL else 'PATH DISTANCE'}")
    print(f"    Cells with PQ_LIM values: {valid_pqlim.sum():,}")
    print(f"    Coverage: {100 * valid_pqlim.sum() / (~dtm_mask).sum():.1f}% of valid terrain")

    if cfg.RESAMPLE_DTM:
        print(f"    Original resolution: {original_cellsize}m")
        print(f"    Final resolution: {cellsize}m")

    print(f"\n  📁 OUTPUT FILES:")
    print(f"    PQ_LIM: {pq_lim_filename}")
    if cfg.SAVE_LI_RASTER:
        print(f"    LI distance: li_distance.tif")
    if cfg.SAVE_LI_BACKLINK:
        print(f"    LI backlink: backlink_li.tif")
    if cfg.SAVE_FRI_RASTER:
        print(f"    FRI distance: fri_distance.tif")
    if cfg.SAVE_FRI_BACKLINK:
        print(f"    FRI backlink: backlink_fri.tif")

    print(f"\n✅ WORKFLOW COMPLETED - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()