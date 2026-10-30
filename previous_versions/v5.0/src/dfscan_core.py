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

# Ensure stdout and stderr are never None to prevent 'NoneType' has no attribute 'flush' under PyInstaller noconsole mode
class DummyWriter:
    def write(self, text):
        pass
    def flush(self):
        pass

if sys.stdout is None:
    sys.stdout = DummyWriter()
if sys.stderr is None:
    sys.stderr = DummyWriter()



# Ensure stdout/stderr are UTF-8 safe for Windows console emoji prints

if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):

    try:

        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    except:

        pass

if sys.stderr is not None and hasattr(sys.stderr, 'reconfigure'):

    try:

        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

    except:

        pass



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

# Multiprocessing Log Capture globals and classes
worker_log_queue = None
parent_log_queue = None

class QueueWriter:
    def __init__(self, queue):
        self.queue = queue
    def write(self, text):
        if text:
            self.queue.put(text)
    def flush(self):
        pass

class WorkerFileLogger:
    def __init__(self, output_path, original_stdout):
        self.output_path = output_path
        self.original_stdout = original_stdout
    def write(self, text):
        if text:
            if self.original_stdout:
                try:
                    self.original_stdout.write(text)
                except Exception:
                    pass
            try:
                with open(self.output_path, "a", encoding="utf-8") as f:
                    f.write(text)
            except Exception as e:
                if self.original_stdout:
                    try:
                        self.original_stdout.write(f"\n[Logger Error] Failed to write to {self.output_path}: {e}\n")
                    except Exception:
                        pass
    def flush(self):
        if self.original_stdout and hasattr(self.original_stdout, 'flush'):
            try:
                self.original_stdout.flush()
            except Exception:
                pass

def init_worker(q):
    global worker_log_queue
    worker_log_queue = q



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



    DTM_ORIGINAL_PATH = r"C:\PRIN_Morpheus\Steano_final_analysis\raster\DTM_BUT_median_5m.tif"

    DTM_FILLED_PATH = r"C:\PRIN_Morpheus\Steano_final_analysis\raster\dtm5fell_r.tif"  # Optional

    FDIR_PATH = r"C:\PRIN_Morpheus\Steano_final_analysis\raster\fdir.tif"  # Optional



    SOURCE_SHAPEFILE_PATH = r"C:\PRIN_Morpheus\Steano_final_analysis\DOD\DOD_filtrato\Punti_Channelized_Final_v7.shp"

    # SOURCE_RASTER_PATH = r"C:\PRIN_Morpheus\Steano_final_analysis\raster\source_int_nulll_r.tif"  # Optional



    SHAPEFILE_ELEV_FIELD = "elev"



    PQLIM_REF_PATH = r"C:\PRIN_Morpheus\Steano_final_analysis\raster\pq_lim.tif"



    OUTPUT_DIR = r"C:\PRIN_Morpheus\Steano_final_analysis\raster\outputs"



    # =====================================================================

    # DTM RESAMPLING OPTIONS

    # =====================================================================



    RESAMPLE_DTM = True  # Set to True to resample

    TARGET_RESOLUTION = 15  # Target resolution in meters

    AGGREGATION_METHOD = "bilinear"  # "median", "mean", or "bilinear"

    

    # Trigger Point Snapping Options (New in v2)

    SNAP_TRIGGERS = True

    SNAP_RADIUS = 2

    ADD_ELEVATION_METERS = 1.0



    # Optional custom suffix appended at the very end of the PQ_LIM filename,

    # before the .tif extension, e.g. "_BUT_5m", "_run3"

    PQLIM_CUSTOM_SUFFIX = "_v_test"  # set to "" if you don't want anything extra

    # =====================================================================

    # BATCH PROCESSING OPTIONS

    # =====================================================================



    # Maximum number of source points to process simultaneously

    BATCH_SIZE = 200  # Reduce if memory issues, increase for faster processing



    # Combination method for overlapping zones

    OVERLAP_METHOD = "MAX"  # Always use MAX for highest susceptibility value



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

    H_L_THRESHOLD = 0.25
    FILL_HL_HOLES = True

    USE_DIRECTION_AWARE_UPHILL = False



    HRMA_FROM_THRESH_LI = 90

    HRMA_TO_THRESH_LI = 90



    ZERO_FACTOR = 0.5

    CUT_ANGLE = 45

    SLOPE = 0.011111



    # MSF Path Pruning Options

    ENABLE_MSF_PRUNING = False

    MSF_PRUNING_THRESHOLD = 1.5



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

    # =====================================================================
    # runoutSIM OPTIONS (NEW in v3)
    # =====================================================================
    RUN_MSF = True
    RUN_RUNOUTSIM = False
    RUNOUTSIM_E_DIV = 2.1
    RUNOUTSIM_PERSISTENCE = 1.6
    RUNOUTSIM_SLOPE_THRESH = 40.0
    RUNOUTSIM_WALKS = 1000
    RUNOUTSIM_FRICTION = 0.06
    RUNOUTSIM_MASS_DRAG = 45.0
    RUNOUTSIM_INT_VEL = 1.0
    RUNOUTSIM_P_SOURCE_PATH = ""
    RUNOUTSIM_CONN_FEATURE_PATH = ""
    RUNOUTSIM_FRICTION_RASTER = ""
    RUNOUTSIM_PQLIM_FILENAME = ""

    # Optional output file configurations persisted by GUI
    SAVE_HL_RASTER = False
    HL_FILENAME = "hl_ratio.tif"
    LI_FILENAME = "li_distance.tif"
    LI_BACKLINK_FILENAME = "backlink_li.tif"
    FRI_FILENAME = "fri_distance.tif"
    FRI_BACKLINK_FILENAME = "backlink_fri.tif"
    PQLIM_FILENAME = "pq_lim.tif"
    SHOW_MAP_PREVIEW = True





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

    """Resample DTM to target resolution using aggregation or interpolation"""

    print(f"  Resampling DTM to {target_resolution}m resolution...")

    print(f"  Method: {method}")



    with rasterio.open(dtm_path) as src:

        original_profile = src.profile

        dtm = src.read(1)

        nodata = src.nodata

        original_transform = src.transform

        original_crs = src.crs



        original_resolution = abs(original_transform.a)



        print(f"  Original resolution: {original_resolution}m")

        print(f"  Original shape: {dtm.shape}")



        if abs(target_resolution - original_resolution) < 1e-5:

            print("  Target resolution matches original resolution, no resampling performed")

            return dtm, original_profile, original_profile



        # Determine if up-sampling or down-sampling

        is_upsampling = target_resolution < original_resolution



        if is_upsampling:

            # For up-sampling (e.g., 10m to 5m), we MUST use geometric interpolation

            print("  Up-sampling detected. Forcing bilinear interpolation.")

            method = "bilinear"

            factor = target_resolution / original_resolution

            new_height = int(round(src.height / factor))

            new_width = int(round(src.width / factor))

        else:

            # For down-sampling (e.g., 5m to 15m), we can use aggregation

            factor = int(round(target_resolution / original_resolution))

            print(f"  Aggregation factor: {factor}x{factor}")

            new_height = dtm.shape[0] // factor

            new_width = dtm.shape[1] // factor



        print(f"  New shape: ({new_height}, {new_width})")

        mask = make_mask(dtm, nodata)



        if method == "median" and not is_upsampling:

            resampled = aggregate_median(dtm, mask, factor, nodata)

            new_transform = original_transform * original_transform.scale(factor, factor)

        elif method == "mean" and not is_upsampling:

            resampled = aggregate_mean(dtm, mask, factor, nodata)

            new_transform = original_transform * original_transform.scale(factor, factor)

        elif method == "bilinear" or is_upsampling:

            # Geometric scale transform for reprojection

            scale_x = target_resolution / original_resolution

            scale_y = target_resolution / original_resolution

            new_transform = original_transform * original_transform.scale(scale_x, scale_y)

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



def fill_pits_whitebox(dtm_path, output_path, breach_dist=5, fill_deps=True):

    """Fill pits using WhiteboxTools"""

    if not WHITEBOX_AVAILABLE:

        raise RuntimeError("WhiteboxTools not available. Install with: pip install whitebox")



    print("  Using WhiteboxTools for pit filling...")

    wbt = WhiteboxTools()



    # If running as compiled exe, find bundled WhiteboxTools binary

    if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS'):

        if hasattr(sys, '_MEIPASS'):

            base_path = sys._MEIPASS

        else:

            base_path = os.path.dirname(sys.executable)



        wbt_exe = os.path.join(base_path, 'WBT', 'whitebox_tools.exe')

        if os.path.exists(wbt_exe):

            print(f"    Using bundled WhiteboxTools: {wbt_exe}")

            wbt.set_whitebox_dir(os.path.dirname(wbt_exe))

        else:

            print(f"    Warning: WhiteboxTools not found at {wbt_exe}, using default")



    wbt.set_verbose_mode(False)



    temp_breached = output_path.replace(".tif", "_breached_temp.tif")

    wbt.breach_depressions(

        dem=dtm_path,

        output=temp_breached,

        max_depth=None,

        max_length=breach_dist,

        flat_increment=None,

        fill_pits=False

    )



    if fill_deps:

        wbt.fill_depressions_wang_and_liu(

            dem=temp_breached,

            output=output_path,

            fix_flats=True

        )

        if os.path.exists(temp_breached):

            os.remove(temp_breached)

    else:

        os.rename(temp_breached, output_path)



    print("  ✓ Pit filling completed")





def fill_pits_custom(dtm, dtm_mask, nodata):

    """Custom pit filling using priority flood algorithm (8-connected with gradient offset)"""

    print("  Using custom priority flood algorithm (8-connected, ArcGIS-like)...")

    print("  ⚠ This may take several minutes for large datasets...")



    nrows, ncols = dtm.shape

    filled = dtm.copy()



    pq = []

    visited = np.zeros((nrows, ncols), dtype=bool)



    # 8-connected neighbors (ArcGIS compatible)

    neighbors = [

        (-1, 0), (1, 0), (0, -1), (0, 1),

        (-1, -1), (-1, 1), (1, -1), (1, 1)

    ]



    # Initialize priority queue with all valid cells on the physical borders

    # OR adjacent to NoData (masked) cells, which act as study area outlets

    for r in range(nrows):

        for c in range(ncols):

            if dtm_mask[r, c]:

                continue

            is_boundary = (r == 0 or r == nrows - 1 or c == 0 or c == ncols - 1)

            if not is_boundary:

                for dr, dc in neighbors:

                    nr, nc = r + dr, c + dc

                    if dtm_mask[nr, nc]:

                        is_boundary = True

                        break

            if is_boundary:

                heapq.heappush(pq, (dtm[r, c], r, c))

                visited[r, c] = True

    processed = 0

    epsilon = 1e-5 # Tiny gradient offset to avoid perfectly flat pool cells



    while pq:

        elev, r, c = heapq.heappop(pq)



        processed += 1

        if processed % 50000 == 0:

            print(f"    Processed {processed:,} cells...")



        for dr, dc in neighbors:

            nr, nc = r + dr, c + dc



            if 0 <= nr < nrows and 0 <= nc < ncols:

                if not visited[nr, nc] and not dtm_mask[nr, nc]:

                    visited[nr, nc] = True

                    # If neighbor is lower than center spill elevation, raise it to center + epsilon

                    new_elev = max(dtm[nr, nc], elev + epsilon)

                    filled[nr, nc] = new_elev

                    heapq.heappush(pq, (new_elev, nr, nc))



    print(f"  ✓ Priority flood completed ({processed:,} cells processed)")



    return filled





def calculate_flow_accumulation(fdir, fdir_nodata, dtm, dtm_mask):

    """Calculate flow accumulation using D8 flow direction and topologically sorted elevations"""

    print("  Calculating D8 flow accumulation...")

    nrows, ncols = fdir.shape

    fac = np.zeros((nrows, ncols), dtype=np.float32)

    

    # Valid indices

    valid_idx = np.argwhere((~dtm_mask) & (fdir != fdir_nodata))

    if len(valid_idx) == 0:

        return fac

        

    # Sort cells by elevation descending (highest to lowest)

    elevations = dtm[valid_idx[:, 0], valid_idx[:, 1]]

    sort_order = np.argsort(elevations)[::-1]

    sorted_cells = valid_idx[sort_order]

    

    # D8 codes to offset mapping:

    # 1: East (0, 1), 2: Southeast (1, 1), 4: South (1, 0), 8: Southwest (1, -1)

    # 16: West (0, -1), 32: Northwest (-1, -1), 64: North (-1, 0), 128: Northeast (-1, 1)

    neighbors_offset = {

        1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1),

        16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)

    }

    

    for r, c in sorted_cells:

        code = fdir[r, c]

        if code in neighbors_offset:

            dr, dc = neighbors_offset[code]

            nr, nc = r + dr, c + dc

            if 0 <= nr < nrows and 0 <= nc < ncols:

                if not dtm_mask[nr, nc]:

                    fac[nr, nc] += 1.0 + fac[r, c]

                    

    print(f"    ✓ Flow accumulation calculated (max accumulation: {np.max(fac):.1f} cells)")

    return fac





# =========================================================================

# FLOW DIRECTION CALCULATION

# =========================================================================



def calculate_fdir_whitebox(dtm_path, output_path):

    """Calculate flow direction using WhiteboxTools (D8)"""

    if not WHITEBOX_AVAILABLE:

        raise RuntimeError("WhiteboxTools not available. Install with: pip install whitebox")



    print("  Using WhiteboxTools D8 flow direction...")

    wbt = WhiteboxTools()



    # If running as compiled exe, find bundled WhiteboxTools binary

    if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS'):

        if hasattr(sys, '_MEIPASS'):

            base_path = sys._MEIPASS

        else:

            base_path = os.path.dirname(sys.executable)



        wbt_exe = os.path.join(base_path, 'WBT', 'whitebox_tools.exe')

        if os.path.exists(wbt_exe):

            print(f"    Using bundled WhiteboxTools: {wbt_exe}")

            wbt.set_whitebox_dir(os.path.dirname(wbt_exe))

        else:

            print(f"    Warning: WhiteboxTools not found at {wbt_exe}, using default")



    wbt.set_verbose_mode(False)



    wbt.d8_pointer(

        dem=dtm_path,

        output=output_path,

        esri_pntr=True

    )



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





def path_allocation_fri_pruned(dtm, dtm_mask, fdir_deg, fdir_mask, source_mask, cellsize,

                               max_slope_deg, use_direction_aware_uphill, zero_factor, cut_angle, slope,

                               li, pruning_threshold, fdir):

    """

    Geomorphologically-aware path pruning: steepest descent (D8) path is exempt from pruning,

    while lateral dispersion paths are cut if traverse probability falls below pruning_threshold.

    """

    height, width = dtm.shape

    visited = np.zeros((height, width), dtype=bool)

    dist = np.full((height, width), np.inf, dtype=np.float32)

    backlink = np.full((height, width), -1, dtype=np.int16)



    heap = []

    start_r, start_c = np.where(source_mask)

    if len(start_r) == 0:

        return dist, backlink, -3.4028234663852886e+38, 32767



    # Direction vectors for 8 neighbors (starts at N, goes clockwise)

    dr = [-1, -1, 0, 1, 1, 1, 0, -1]

    dc = [0, 1, 1, 1, 0, -1, -1, -1]

    d8_to_idx = {64: 0, 128: 1, 1: 2, 2: 3, 4: 4, 8: 5, 16: 6, 32: 7}

    move_angles = [0, 45, 90, 135, 180, 225, 270, 315]

    root2 = math.sqrt(2.0)

    move_distances = [cellsize, cellsize * root2, cellsize, cellsize * root2,

                      cellsize, cellsize * root2, cellsize, cellsize * root2]



    # Precalculate uphill tolerances

    uphill_tolerances = []

    for i in range(8):

        uphill_tol = calculate_uphill_tolerance(

            cellsize, max_slope_deg, direction_idx=i,

            use_direction_aware=use_direction_aware_uphill

        )

        uphill_tolerances.append(uphill_tol)



    for r, c in zip(start_r, start_c):

        dist[r, c] = 0.0

        backlink[r, c] = 0

        heapq.heappush(heap, (0.0, int(r), int(c)))



    while heap:

        d, r, c = heapq.heappop(heap)

        if visited[r, c]:

            continue

        visited[r, c] = True



        # Get D8 flow direction code

        code = fdir[r, c]

        d8_idx = d8_to_idx.get(code, -1)



        z_curr = dtm[r, c]

        fdir_curr = fdir_deg[r, c]



        for dir_idx in range(8):

            nr, nc = r + dr[dir_idx], c + dc[dir_idx]

            if not (0 <= nr < height and 0 <= nc < width):

                continue

            if visited[nr, nc] or dtm_mask[nr, nc] or fdir_mask[nr, nc]:

                continue



            # Uphill check

            z_next = dtm[nr, nc]

            dz = z_next - z_curr

            if dz > uphill_tolerances[dir_idx]:

                continue



            # Calculate traverse probability

            # Use current accumulated FRI (d) as the denominator

            # If we are at the source, d is 0.0, so pqi is not pruned

            l_val = li[nr, nc]

            pqi = l_val / d if d > 0 else 9999.0



            # Pruning condition: if pqi < threshold AND it is NOT the D8 steepest descent path

            if pqi < pruning_threshold and dir_idx != d8_idx:

                continue



            # Calculate cost

            surf_dist = move_distances[dir_idx]

            move_angle = move_angles[dir_idx]

            fdir_next = fdir_deg[nr, nc]



            angle_from = None

            angle_to = None



            if not np.isnan(fdir_curr):

                angle_diff_from = move_angle - fdir_curr

                while angle_diff_from > 180: angle_diff_from -= 360

                while angle_diff_from < -180: angle_diff_from += 360

                angle_from = abs(angle_diff_from)



            if not np.isnan(fdir_next):

                angle_diff_to = move_angle - fdir_next

                while angle_diff_to > 180: angle_diff_to -= 360

                while angle_diff_to < -180: angle_diff_to += 360

                angle_to = abs(angle_diff_to)



            if angle_from is not None and angle_to is not None:

                if angle_from > cut_angle or angle_to > cut_angle: continue

                avg_angle = (angle_from + angle_to) / 2.0

            elif angle_from is not None:

                if angle_from > cut_angle: continue

                avg_angle = angle_from

            elif angle_to is not None:

                if angle_to > cut_angle: continue

                avg_angle = angle_to

            else:

                avg_angle = 0.0



            hf = zero_factor + avg_angle * slope

            cost = surf_dist * hf

            new_dist = d + cost



            if new_dist < dist[nr, nc]:

                dist[nr, nc] = new_dist

                backlink[nr, nc] = (dir_idx + 4) % 8 + 1

                heapq.heappush(heap, (new_dist, nr, nc))



    nodata_f = -3.4028234663852886e+38

    nodata_i = 32767

    dist[~visited | dtm_mask] = nodata_f

    backlink[~visited | dtm_mask] = nodata_i



    return dist, backlink, nodata_f, nodata_i





# =========================================================================

# runoutSIM PHYSICS & ROUTING ENGINE (NEW in v3)

# =========================================================================



def pcm(mu, md, v_p, theta_p, theta_i, l):

    """

    Implements the Perla-Cheng-McClung (PCM) friction model for velocity updates.

    Includes velocity correction for concave slope transitions as per Wichmann (2017).

    """

    g = 9.80665  # Gravitational acceleration (m/s^2)

    

    alpha = g * (math.sin(theta_i * math.pi / 180.0) - mu * math.cos(theta_i * math.pi / 180.0))  # Acceleration

    beta = -2.0 * l / md  # Adjustment factor

    

    # Velocity correction for concave transitions (slope decreases)

    delta_theta = (theta_p - theta_i) if theta_p > theta_i else 0.0

    

    # Compute velocity

    velocity_sq = alpha * md * (1.0 - math.exp(beta)) + (v_p**2 * math.exp(beta) * math.cos(delta_theta * math.pi / 180.0))

    

    if velocity_sq < 0:

        return float('nan')

    else:

        return math.sqrt(velocity_sq)





def runout_sim_walks(sr, sc, dtm, dtm_mask, cellsize, cfg_dict, mu_matrix=None, connect_feature_matrix=None):

    """

    Simulates runout paths using stochasitc random walk and PCM physics from a single source point (sr, sc).

    Replicates the R package runoutSIM implementation.

    """

    nrows, ncols = dtm.shape

    

    # Extract parameters from cfg dict

    mu = cfg_dict.get('RUNOUTSIM_FRICTION', 0.06)

    md = cfg_dict.get('RUNOUTSIM_MASS_DRAG', 45.0)

    int_vel = cfg_dict.get('RUNOUTSIM_INT_VEL', 1.0)

    slp_thresh = cfg_dict.get('RUNOUTSIM_SLOPE_THRESH', 40.0)

    exp_div = cfg_dict.get('RUNOUTSIM_E_DIV', 2.1)

    per_fct = cfg_dict.get('RUNOUTSIM_PERSISTENCE', 1.6)

    walks = cfg_dict.get('RUNOUTSIM_WALKS', 1000)

    

    is_sp_mu = mu_matrix is not None

    

    # Neighbor cell offsets in GPP/SAGA layout:

    # 0: up-left, 1: left, 2: down-left, 3: up-right, 4: right, 5: down-right, 6: up, 7: down

    OFFSETS = [

        (-1, -1),

        (0, -1),

        (1, -1),

        (-1, 1),

        (0, 1),

        (1, 1),

        (-1, 0),

        (1, 0)

    ]

    

    DIST_FACTORS = [math.sqrt(2.0), 1.0, math.sqrt(2.0), math.sqrt(2.0), 1.0, math.sqrt(2.0), 1.0, 1.0]

    cell_dist = [cellsize * f for f in DIST_FACTORS]

    

    sim_paths = []

    sim_velocity = []

    

    # Seed a local random generator (multiprocess-safe)

    rng = np.random.default_rng()

    

    for k in range(walks):

        path_cells = []

        vel_cells = []

        

        r_curr, c_curr = sr, sc

        prv_pos = None

        v_p = int_vel

        theta_p = 1.0

        

        while True:

            # Edge of raster checks

            if r_curr + 1 >= nrows or c_curr + 1 >= ncols or r_curr - 1 < 0 or c_curr - 1 < 0:

                break

                

            # Read all 8 neighbors' elevations

            neighbor_elvs = []

            has_nan = False

            for idx, (dr, dc) in enumerate(OFFSETS):

                nr, nc = r_curr + dr, c_curr + dc

                elv = dtm[nr, nc]

                if np.isnan(elv) or dtm_mask[nr, nc]:

                    has_nan = True

                    break

                neighbor_elvs.append(elv)

                

            if has_nan or len(neighbor_elvs) < 8:

                break

                

            elv_cntr = dtm[r_curr, c_curr]

            

            # Keep neighbors lower than center

            lower_elv = []

            lower_indices = []

            for idx, elv in enumerate(neighbor_elvs):

                if elv < elv_cntr:

                    lower_elv.append(elv)

                    lower_indices.append(idx)

                    

            if not lower_elv:

                break

                

            # Calculate slope angles in degrees

            beta_ngh = []

            for idx in lower_indices:

                dh = elv_cntr - neighbor_elvs[idx]

                dist = cell_dist[idx]

                slope_angle = math.atan(dh / dist) * 180.0 / math.pi

                beta_ngh.append(slope_angle)

                

            # Slope ratio values relative to thresh

            tan_slp_thresh = math.tan(slp_thresh * math.pi / 180.0)

            gamma_i = [math.tan(beta * math.pi / 180.0) / tan_slp_thresh for beta in beta_ngh]

            

            # Directional persistence

            f = [1.0] * 8

            if prv_pos is not None:

                f[prv_pos] = per_fct

                

            f_lower = [f[idx] for idx in lower_indices]

            

            # Calculate transition weights

            fj = [f_lower[j] * math.tan(beta_ngh[j] * math.pi / 180.0) for j in range(len(lower_indices))]

            sum_fj = sum(fj)

            if sum_fj <= 0:

                break

                

            prob = [val / sum_fj for val in fj]

            gamma_max = max(gamma_i)

            

            if gamma_max > 1.0:

                # Forced D8 steepest descent

                ties = [j for j, val in enumerate(gamma_i) if val == gamma_max]

                if len(ties) > 1:

                    chosen_idx = rng.choice(ties)

                else:

                    chosen_idx = ties[0]

            else:

                # Stochastic random walk divergence

                threshold_val = gamma_max ** exp_div

                candidates = [j for j, val in enumerate(gamma_i) if val >= threshold_val]

                

                if not candidates:

                    break

                    

                cand_probs = [prob[j] for j in candidates]

                sum_cand_probs = sum(cand_probs)

                if sum_cand_probs <= 0:

                    cand_probs = [1.0 / len(candidates)] * len(candidates)

                else:

                    cand_probs = [p / sum_cand_probs for p in cand_probs]

                    

                chosen_idx = rng.choice(candidates, p=cand_probs)

                

            # Chosen neighbor index (0 to 7)

            nxt_cell_pos = lower_indices[chosen_idx]

            prv_pos = nxt_cell_pos

            

            # Extract sliding friction

            if is_sp_mu:

                mu_in = mu_matrix[r_curr + OFFSETS[nxt_cell_pos][0], c_curr + OFFSETS[nxt_cell_pos][1]]

            else:

                mu_in = mu

                

            theta_i = beta_ngh[chosen_idx]

            step_dist = cell_dist[nxt_cell_pos]

            

            v_i = pcm(mu_in, md, v_p, theta_p, theta_i, step_dist)

            

            if math.isnan(v_i) or v_i <= 0:

                vel_cells.append(0.0)

                break

                

            vel_cells.append(v_i)

            v_p = v_i

            theta_p = theta_i

            

            # Advance coordinates

            r_curr += OFFSETS[nxt_cell_pos][0]

            c_curr += OFFSETS[nxt_cell_pos][1]

            path_cells.append((r_curr, c_curr))

            

        if path_cells:

            sim_paths.append(path_cells)

            sim_velocity.append(vel_cells)

            

    if not sim_paths:

        return {

            'start_cell': (sr, sc),

            'cell_trav_freq': {},

            'cell_max_vel': {},

            'prob_connect': 0.0 if connect_feature_matrix is not None else None

        }

        

    cell_counts = {}

    cell_max_vel = {}

    

    for path, vels in zip(sim_paths, sim_velocity):

        visited_in_walk = set()

        for idx, (r, c) in enumerate(path):

            cell = (r, c)

            visited_in_walk.add(cell)

            vel = vels[idx]

            cell_max_vel[cell] = max(cell_max_vel.get(cell, 0.0), vel)

            

        for cell in visited_in_walk:

            cell_counts[cell] = cell_counts.get(cell, 0) + 1

            

    prob_connect = None

    if connect_feature_matrix is not None:

        intersect_count = 0

        for path in sim_paths:

            intersects = False

            for r, c in path:

                if connect_feature_matrix[r, c] == 1:

                    intersects = True

                    break

            if intersects:

                intersect_count += 1

        prob_connect = intersect_count / len(sim_paths)

        

    return {

        'start_cell': (sr, sc),

        'cell_trav_freq': cell_counts,

        'cell_max_vel': cell_max_vel,

        'prob_connect': prob_connect

    }





def calculate_ecdf(frequencies, dtm_mask, nodata):

    """

    Applies empirical cumulative distribution function (ECDF) to frequencies.

    Matches R package rasterCdf function.

    """

    valid_mask = (frequencies != nodata) & (frequencies > 0) & (~dtm_mask)

    valid_freqs = frequencies[valid_mask]

    

    if len(valid_freqs) == 0:

        return np.zeros_like(frequencies)

        

    sorted_freqs = np.sort(valid_freqs)

    ranks = np.searchsorted(sorted_freqs, valid_freqs, side='right')

    ecdf_vals = ranks / len(sorted_freqs)

    

    probabilities = np.full(frequencies.shape, nodata, dtype=np.float32)

    probabilities[valid_mask] = ecdf_vals

    probabilities[~valid_mask] = 0.0

    probabilities[dtm_mask] = nodata

    return probabilities





# =========================================================================

# SINGLE SOURCE PROCESSING

# =========================================================================





def process_single_source_point(sr, sc, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg, fdir=None):

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

        fdir: Optional D8 integer flow direction array for path pruning



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



    # Run FRI standard (always needed)
    fri_std, backlink_fri_std, nd_f_fri, nd_i_fri = path_allocation_fri(
        dtm, dtm_mask, fdir_deg, fdir_mask, source_mask, cellsize,
        cfg.MAX_SLOPE_DEGREES, cfg.USE_DIRECTION_AWARE_UPHILL,
        cfg.ZERO_FACTOR, cfg.CUT_ANGLE, cfg.SLOPE
    )

    # Run FRI pruned (only if enabled AND fdir available)
    fri_pruned = None
    backlink_fri_pruned = None
    if getattr(cfg, "ENABLE_MSF_PRUNING", False) and fdir is not None:
        fri_pruned, backlink_fri_pruned, _nd_fp, _nd_ip = path_allocation_fri_pruned(
            dtm, dtm_mask, fdir_deg, fdir_mask, source_mask, cellsize,
            cfg.MAX_SLOPE_DEGREES, cfg.USE_DIRECTION_AWARE_UPHILL,
            cfg.ZERO_FACTOR, cfg.CUT_ANGLE, cfg.SLOPE,
            li=li, pruning_threshold=cfg.MSF_PRUNING_THRESHOLD, fdir=fdir
        )

    # Use standard FRI as default fri/backlink_fri for output
    fri = fri_std
    backlink_fri = backlink_fri_std



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



    # Apply H/L threshold (with downstream-to-upstream hole filling to guarantee path continuity)
    h_l_lim = np.full(dtm.shape, nd_f_li, dtype=np.float32)
    fill_hl_holes = getattr(cfg, 'FILL_HL_HOLES', True)
    
    if fill_hl_holes:
        rows, cols = dtm.shape
        keep = (h_l != nd_f_li) & (h_l >= cfg.H_L_THRESHOLD)
        
        valid_li_mask = (li != nd_f_li) & (li > 0)
        valid_li_indices = np.argwhere(valid_li_mask)
        if valid_li_indices.size > 0:
            li_values = li[valid_li_indices[:, 0], valid_li_indices[:, 1]]
            sorted_indices = valid_li_indices[np.argsort(-li_values)]
            
            neighbors_offsets = [
                (0, 1), (1, 1), (1, 0), (1, -1),
                (0, -1), (-1, -1), (-1, 0), (-1, 1)
            ]
            
            for r, c in sorted_indices:
                b = backlink_li[r, c]
                if 1 <= b <= 8:
                    dr, dc = neighbors_offsets[b - 1]
                    # Upstream parent is child minus step offset
                    pr, pc = r - dr, c - dc
                    if 0 <= pr < rows and 0 <= pc < cols:
                        if keep[r, c]:
                            keep[pr, pc] = True
        valid_lim = keep
    else:
        valid_lim = (h_l != nd_f_li) & (h_l >= cfg.H_L_THRESHOLD)

    h_l_lim[valid_lim] = h_l[valid_lim]





    # Calculate PQI standard

    pqi = np.full(dtm.shape, nd_f_li, dtype=np.float32)

    valid_pqi = valid_li & (fri_std != nd_f_fri) & (fri_std > 0)

    pqi[valid_pqi] = li[valid_pqi] / fri_std[valid_pqi]



    # Calculate PQ_LIM standard - CRITICAL: only where H/L threshold is met

    pq_lim = np.full(dtm.shape, nd_f_li, dtype=np.float32)

    valid_pqlim = valid_lim & valid_pqi

    pq_lim[valid_pqlim] = pqi[valid_pqlim]

    # Calculate PQ_LIM pruned (if pruning enabled)
    pq_lim_pruned = np.full(dtm.shape, nd_f_li, dtype=np.float32)
    if fri_pruned is not None:
        valid_pqi_p = valid_li & (fri_pruned != nd_f_fri) & (fri_pruned > 0)
        pqi_p = np.full(dtm.shape, nd_f_li, dtype=np.float32)
        pqi_p[valid_pqi_p] = li[valid_pqi_p] / fri_pruned[valid_pqi_p]
        valid_pqlim_p = valid_lim & valid_pqi_p
        pq_lim_pruned[valid_pqlim_p] = pqi_p[valid_pqlim_p]



    return {

        'pq_lim': pq_lim,

        'pq_lim_pruned': pq_lim_pruned,

        'li': li,

        'backlink_li': backlink_li,

        'fri': fri_std,

        'backlink_fri': backlink_fri_std,

        'fri_pruned': fri_pruned,

        'backlink_fri_pruned': backlink_fri_pruned,

        'nodata_float': nd_f_li,

        'nodata_int': nd_i_li,

        'source_row': sr,

        'source_col': sc,

        'h_l': h_l

    }





# =========================================================================

# PARALLEL PROCESSING WORKER

# =========================================================================



def process_single_point_worker(point_info, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg_dict,
                                mu_matrix=None, connect_feature_matrix=None, source_prob_matrix=None,
                                fdir_matrix=None):
    """
    Worker function for parallel processing of a single source point.
    Supports either standard MSF or runoutSIM based on RUN_RUNOUTSIM config.
    """
    sr, sc, point_idx = point_info

    # Setup file-based logger for worker to capture output in PyQt GUI
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    output_dir = cfg_dict.get('OUTPUT_DIR', '')
    if output_dir and os.path.exists(output_dir):
        log_file_path = os.path.join(output_dir, f"worker_{os.getpid()}.log")
        logger = WorkerFileLogger(log_file_path, original_stdout)
        sys.stdout = sys.stderr = logger

    try:
        global worker_log_queue
        if worker_log_queue is not None:
            sys.stdout = sys.stderr = QueueWriter(worker_log_queue)

        # Reconstruct config object from dict
        class TempConfig:
            def __init__(self, d):
                for k, v in d.items():
                    setattr(self, k, v)

        cfg = TempConfig(cfg_dict)

        if getattr(cfg, 'RUN_RUNOUTSIM', False):
            # Run runoutSIM random walks
            weight = 1.0
            if source_prob_matrix is not None:
                weight = float(source_prob_matrix[sr, sc])
                if np.isnan(weight):
                    weight = 0.0

            result = runout_sim_walks(sr, sc, dtm, dtm_mask, cellsize, cfg_dict,
                                      mu_matrix=mu_matrix,
                                      connect_feature_matrix=connect_feature_matrix)

            # Apply source probability weight
            if weight != 1.0 and result.get('cell_trav_freq'):
                weighted_counts = {}
                for cell, count in result['cell_trav_freq'].items():
                    weighted_counts[cell] = count * weight
                result['cell_trav_freq'] = weighted_counts

            result['point_index'] = point_idx
            return result
        else:
            # Run standard MSF (potentially pruned)
            result = process_single_source_point(sr, sc, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg, fdir=fdir_matrix)
            result['point_index'] = point_idx
            return result
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr




def process_sources_parallel(src_pix_all, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg, ref_profile=None, fdir_matrix=None):
    """
    Process all source points using parallel workers.
    Supports both MSF and runoutSIM.
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
        'USE_DIRECT_DISTANCE_FOR_HL': cfg.USE_DIRECT_DISTANCE_FOR_HL,
        'FILL_HL_HOLES': getattr(cfg, 'FILL_HL_HOLES', True),
        'ENABLE_MSF_PRUNING': getattr(cfg, 'ENABLE_MSF_PRUNING', False),
        'MSF_PRUNING_THRESHOLD': getattr(cfg, 'MSF_PRUNING_THRESHOLD', 1.5),
        'OUTPUT_DIR': getattr(cfg, 'OUTPUT_DIR', ''),
        
        # runoutSIM parameters
        'RUN_RUNOUTSIM': getattr(cfg, 'RUN_RUNOUTSIM', False),
        'RUNOUTSIM_E_DIV': getattr(cfg, 'RUNOUTSIM_E_DIV', 2.1),
        'RUNOUTSIM_PERSISTENCE': getattr(cfg, 'RUNOUTSIM_PERSISTENCE', 1.6),
        'RUNOUTSIM_SLOPE_THRESH': getattr(cfg, 'RUNOUTSIM_SLOPE_THRESH', 40.0),
        'RUNOUTSIM_WALKS': getattr(cfg, 'RUNOUTSIM_WALKS', 1000),
        'RUNOUTSIM_FRICTION': getattr(cfg, 'RUNOUTSIM_FRICTION', 0.06),
        'RUNOUTSIM_MASS_DRAG': getattr(cfg, 'RUNOUTSIM_MASS_DRAG', 45.0),
        'RUNOUTSIM_INT_VEL': getattr(cfg, 'RUNOUTSIM_INT_VEL', 1.0)
    }

    # Load matrices for runoutSIM if enabled
    mu_matrix = None
    connect_feature_matrix = None
    source_prob_matrix = None

    if getattr(cfg, 'RUN_RUNOUTSIM', False):
        fric_param = getattr(cfg, 'RUNOUTSIM_FRICTION', 0.06)
        if isinstance(fric_param, str) and fric_param and os.path.exists(fric_param):
            print(f"  Loading spatially varying friction raster: {fric_param}")
            with rasterio.open(fric_param) as src:
                if src.shape == dtm.shape:
                    mu_matrix = src.read(1).astype(np.float32)
                else:
                    print("    Friction raster size mismatch, reprojecting...")
                    mu_matrix = np.full(dtm.shape, 0.06, dtype=np.float32)
                    reproject(
                        source=rasterio.band(src, 1), destination=mu_matrix,
                        src_transform=src.transform, src_crs=src.crs,
                        dst_transform=ref_profile['transform'] if ref_profile is not None else None,
                        dst_crs=ref_profile['crs'] if ref_profile is not None else None,
                        resampling=Resampling.bilinear
                    )
        sp_path = getattr(cfg, 'RUNOUTSIM_P_SOURCE_PATH', "")
        if sp_path and os.path.exists(sp_path):
            print(f"  Loading source probability raster: {sp_path}")
            with rasterio.open(sp_path) as src:
                if src.shape == dtm.shape:
                    source_prob_matrix = src.read(1).astype(np.float32)
                else:
                    print("    Source probability raster size mismatch, reprojecting...")
                    source_prob_matrix = np.full(dtm.shape, 1.0, dtype=np.float32)
                    reproject(
                        source=rasterio.band(src, 1), destination=source_prob_matrix,
                        src_transform=src.transform, src_crs=src.crs,
                        dst_transform=ref_profile['transform'] if ref_profile is not None else None,
                        dst_crs=ref_profile['crs'] if ref_profile is not None else None,
                        resampling=Resampling.bilinear
                    )
        cf_path = getattr(cfg, 'RUNOUTSIM_CONN_FEATURE_PATH', "")
        if cf_path and os.path.exists(cf_path):
            print(f"  Loading connectivity feature: {cf_path}")
            if cf_path.lower().endswith('.shp'):
                if GEOPANDAS_AVAILABLE and ref_profile is not None:
                    gdf = gpd.read_file(cf_path)
                    connect_feature_matrix = rasterize(
                        [(geom, 1) for geom in gdf.geometry],
                        out_shape=dtm.shape,
                        transform=ref_profile['transform'],
                        fill=0,
                        all_touched=True,
                        dtype=np.uint8
                    )
                else:
                    print("    ⚠ Error: geopandas or ref_profile not available. Cannot rasterize shapefile.")
            else:
                with rasterio.open(cf_path) as src:
                    if src.shape == dtm.shape:
                        connect_feature_matrix = src.read(1).astype(np.uint8)
                    else:
                        print("    Connectivity raster size mismatch, reprojecting...")
                        connect_feature_matrix = np.zeros(dtm.shape, dtype=np.uint8)
                        reproject(
                            source=rasterio.band(src, 1), destination=connect_feature_matrix,
                            src_transform=src.transform, src_crs=src.crs,
                            dst_transform=ref_profile['transform'] if ref_profile is not None else None,
                            dst_crs=ref_profile['crs'] if ref_profile is not None else None,
                            resampling=Resampling.nearest
                        )
                connect_feature_matrix = (connect_feature_matrix > 0).astype(np.uint8)

    # Prepare point info list
    points_info = [(int(sr), int(sc), i) for i, (sr, sc) in enumerate(src_pix_all)]

    nodata_f = -9999.0
    nodata_i = 32767

    # Create worker function
    worker_func = partial(
        process_single_point_worker,
        dtm=dtm,
        dtm_mask=dtm_mask,
        fdir_deg=fdir_deg,
        fdir_mask=fdir_mask,
        cellsize=cellsize,
        cfg_dict=cfg_dict,
        mu_matrix=mu_matrix,
        connect_feature_matrix=connect_feature_matrix,
        source_prob_matrix=source_prob_matrix,
        fdir_matrix=fdir_matrix
    )

    global parent_log_queue
    pool_kwargs = {}
    if parent_log_queue is not None:
        pool_kwargs['initializer'] = init_worker
        pool_kwargs['initargs'] = (parent_log_queue,)

    if getattr(cfg, 'RUN_RUNOUTSIM', False):
        combined_frequencies = np.zeros(dtm.shape, dtype=np.float32)
        combined_max_velocity = np.zeros(dtm.shape, dtype=np.float32)
        source_connectivity = {}

        with mp.Pool(processes=cfg.NUM_WORKERS, **pool_kwargs) as pool:
            results_iter = pool.imap(worker_func, points_info)
            processed = 0
            for result in results_iter:
                processed += 1
                if processed % 10 == 0 or processed == num_sources:
                    print(f"    Progress: {processed}/{num_sources} points ({100 * processed / num_sources:.1f}%)")
                    sys.stdout.flush()
                    sys.stderr.flush()

                # Sum frequencies
                for cell, freq in result['cell_trav_freq'].items():
                    combined_frequencies[cell[0], cell[1]] += freq

                # Max velocities
                for cell, vel in result['cell_max_vel'].items():
                    combined_max_velocity[cell[0], cell[1]] = max(combined_max_velocity[cell[0], cell[1]], vel)

                if result['prob_connect'] is not None:
                    source_connectivity[result['start_cell']] = result['prob_connect']

        print(f"  ✓ Parallel processing completed")
        
        print("  Calculating ECDF Traverse Probabilities...")
        combined_pq_lim = calculate_ecdf(combined_frequencies, dtm_mask, nodata_f)
        combined_max_velocity[combined_frequencies == 0] = nodata_f
        combined_max_velocity[dtm_mask] = nodata_f
        combined_hl = combined_max_velocity

        if source_connectivity:
            Config.SOURCE_CONNECTIVITY = source_connectivity
            avg_conn = np.mean(list(source_connectivity.values()))
            print(f"    Average Source Connectivity Probability: {avg_conn:.4f}")

        return {
            'pq_lim': combined_pq_lim,
            'li': combined_frequencies,
            'backlink_li': np.full(dtm.shape, nodata_i, dtype=np.int16),
            'fri': np.full(dtm.shape, nodata_f, dtype=np.float32),
            'backlink_fri': np.full(dtm.shape, nodata_i, dtype=np.int16),
            'h_l': combined_hl,
            'nodata_float': nodata_f,
            'nodata_int': nodata_i
        }
    else:
        # Standard MSF parallel aggregation
        combined_pq_lim = np.full(dtm.shape, nodata_f, dtype=np.float32)
        combined_pq_lim_pruned = np.full(dtm.shape, nodata_f, dtype=np.float32)
        combined_li = np.full(dtm.shape, nodata_f, dtype=np.float32)
        combined_backlink_li = np.full(dtm.shape, nodata_i, dtype=np.int16)
        combined_fri = np.full(dtm.shape, nodata_f, dtype=np.float32)
        combined_backlink_fri = np.full(dtm.shape, nodata_i, dtype=np.int16)
        combined_hl = np.full(dtm.shape, nodata_f, dtype=np.float32)

        with mp.Pool(processes=cfg.NUM_WORKERS, **pool_kwargs) as pool:
            results_iter = pool.imap(worker_func, points_info)
            processed = 0
            for result in results_iter:
                processed += 1
                if processed % 10 == 0 or processed == num_sources:
                    print(f"    Progress: {processed}/{num_sources} points ({100 * processed / num_sources:.1f}%)")
                    sys.stdout.flush()
                    sys.stderr.flush()

                # PQ_LIM standard
                valid_new = (result['pq_lim'] != nodata_f) & (result['pq_lim'] > 0)
                valid_existing = (combined_pq_lim != nodata_f) & (combined_pq_lim > 0)
                both_valid = valid_new & valid_existing
                combined_pq_lim[both_valid] = np.maximum(combined_pq_lim[both_valid], result['pq_lim'][both_valid])
                only_new = valid_new & ~valid_existing
                combined_pq_lim[only_new] = result['pq_lim'][only_new]

                # PQ_LIM pruned
                pq_lim_p = result.get('pq_lim_pruned', np.full(dtm.shape, nodata_f, dtype=np.float32))
                valid_new_p = (pq_lim_p != nodata_f) & (pq_lim_p > 0)
                valid_existing_p = (combined_pq_lim_pruned != nodata_f) & (combined_pq_lim_pruned > 0)
                both_valid_p = valid_new_p & valid_existing_p
                combined_pq_lim_pruned[both_valid_p] = np.maximum(combined_pq_lim_pruned[both_valid_p], pq_lim_p[both_valid_p])
                only_new_p = valid_new_p & ~valid_existing_p
                combined_pq_lim_pruned[only_new_p] = pq_lim_p[only_new_p]

                # LI
                valid_new = (result['li'] != nodata_f) & (result['li'] >= 0)
                valid_existing = (combined_li != nodata_f) & (combined_li >= 0)
                mask_update = valid_new & (~valid_existing | (result['pq_lim'] > combined_pq_lim))
                combined_li[mask_update] = result['li'][mask_update]
                combined_backlink_li[mask_update] = result['backlink_li'][mask_update]

                # FRI
                valid_new = (result['fri'] != nodata_f) & (result['fri'] >= 0)
                valid_existing = (combined_fri != nodata_f) & (combined_fri >= 0)
                mask_update = valid_new & (~valid_existing | (result['pq_lim'] > combined_pq_lim))
                combined_fri[mask_update] = result['fri'][mask_update]
                combined_backlink_fri[mask_update] = result['backlink_fri'][mask_update]

                # HL
                valid_new = (result['h_l'] != nodata_f) & (result['h_l'] >= 0)
                valid_existing = (combined_hl != nodata_f) & (combined_hl >= 0)
                mask_update = valid_new & (~valid_existing | (result['pq_lim'] > combined_pq_lim))
                combined_hl[mask_update] = result['h_l'][mask_update]

        print(f"  ✓ Parallel processing completed")
        valid_pqlim = ((combined_pq_lim != nodata_f) & (combined_pq_lim > 0)).sum()
        print(f"    Final cells with PQ_LIM: {valid_pqlim:,}")

        return {
            'pq_lim': combined_pq_lim,
            'pq_lim_pruned': combined_pq_lim_pruned,
            'li': combined_li,
            'backlink_li': combined_backlink_li,
            'fri': combined_fri,
            'backlink_fri': combined_backlink_fri,
            'h_l': combined_hl,
            'nodata_float': nodata_f,
            'nodata_int': nodata_i
        }


# =========================================================================
# BATCH PROCESSING FOR REGIONAL SCALE
# =========================================================================

def process_source_batch(batch_indices, dtm, dtm_mask, fdir_deg, fdir_mask,
                         source_raster, src_nodata, cellsize, cfg, fdir_matrix=None):
    """
    Process a batch of source points, EACH INDIVIDUALLY, and combine.


    Supports runoutSIM and standard MSF.
    """
    nodata_f = -9999.0
    nodata_i = 32767

    if getattr(cfg, 'RUN_RUNOUTSIM', False):
        # Run runoutSIM sequentially for this batch
        mu_matrix = None
        connect_feature_matrix = None
        source_prob_matrix = None
        
        fric_param = getattr(cfg, 'RUNOUTSIM_FRICTION', 0.06)
        if isinstance(fric_param, str) and fric_param and os.path.exists(fric_param):
            with rasterio.open(fric_param) as src:
                if src.shape == dtm.shape:
                    mu_matrix = src.read(1).astype(np.float32)
                else:
                    mu_matrix = np.full(dtm.shape, 0.06, dtype=np.float32)
                    reproject(
                        source=rasterio.band(src, 1), destination=mu_matrix,
                        src_transform=src.transform, src_crs=src.crs,
                        dst_transform=cfg.ref_profile['transform'] if hasattr(cfg, 'ref_profile') else None,
                        dst_crs=cfg.ref_profile['crs'] if hasattr(cfg, 'ref_profile') else None,
                        resampling=Resampling.bilinear
                    )
        sp_path = getattr(cfg, 'RUNOUTSIM_P_SOURCE_PATH', "")
        if sp_path and os.path.exists(sp_path):
            with rasterio.open(sp_path) as src:
                if src.shape == dtm.shape:
                    source_prob_matrix = src.read(1).astype(np.float32)
                else:
                    source_prob_matrix = np.full(dtm.shape, 1.0, dtype=np.float32)
                    reproject(
                        source=rasterio.band(src, 1), destination=source_prob_matrix,
                        src_transform=src.transform, src_crs=src.crs,
                        resampling=Resampling.bilinear
                    )
        cf_path = getattr(cfg, 'RUNOUTSIM_CONN_FEATURE_PATH', "")
        if cf_path and os.path.exists(cf_path):
            if cf_path.lower().endswith('.shp'):
                if GEOPANDAS_AVAILABLE and hasattr(cfg, 'ref_profile') and cfg.ref_profile is not None:
                    gdf = gpd.read_file(cf_path)
                    connect_feature_matrix = rasterize(
                        [(geom, 1) for geom in gdf.geometry],
                        out_shape=dtm.shape,
                        transform=cfg.ref_profile['transform'],
                        fill=0,
                        all_touched=True,
                        dtype=np.uint8
                    )
            else:
                with rasterio.open(cf_path) as src:
                    if src.shape == dtm.shape:
                        connect_feature_matrix = src.read(1).astype(np.uint8)
                    else:
                        connect_feature_matrix = np.zeros(dtm.shape, dtype=np.uint8)
                        reproject(
                            source=rasterio.band(src, 1), destination=connect_feature_matrix,
                            src_transform=src.transform, src_crs=src.crs,
                            dst_transform=cfg.ref_profile['transform'] if hasattr(cfg, 'ref_profile') else None,
                            dst_crs=cfg.ref_profile['crs'] if hasattr(cfg, 'ref_profile') else None,
                            resampling=Resampling.nearest
                        )
                connect_feature_matrix = (connect_feature_matrix > 0).astype(np.uint8)

        combined_frequencies = np.zeros(dtm.shape, dtype=np.float32)
        combined_hl = np.full(dtm.shape, nodata_f, dtype=np.float32)
        source_connectivity = {}

        cfg_dict = {
            'RUNOUTSIM_E_DIV': getattr(cfg, 'RUNOUTSIM_E_DIV', 2.1),
            'RUNOUTSIM_PERSISTENCE': getattr(cfg, 'RUNOUTSIM_PERSISTENCE', 1.6),
            'RUNOUTSIM_SLOPE_THRESH': getattr(cfg, 'RUNOUTSIM_SLOPE_THRESH', 40.0),
            'RUNOUTSIM_WALKS': getattr(cfg, 'RUNOUTSIM_WALKS', 1000),
            'RUNOUTSIM_FRICTION': getattr(cfg, 'RUNOUTSIM_FRICTION', 0.06),
            'RUNOUTSIM_MASS_DRAG': getattr(cfg, 'RUNOUTSIM_MASS_DRAG', 45.0),
            'RUNOUTSIM_INT_VEL': getattr(cfg, 'RUNOUTSIM_INT_VEL', 1.0)
        }

        for point_idx, (sr, sc) in enumerate(batch_indices):
            if (point_idx + 1) % 10 == 0 or point_idx == len(batch_indices) - 1:
                print(f"      Point {point_idx + 1}/{len(batch_indices)}")
                sys.stdout.flush()
                sys.stderr.flush()

            weight = 1.0
            if source_prob_matrix is not None:
                weight = float(source_prob_matrix[sr, sc])
                if np.isnan(weight):
                    weight = 0.0

            result = runout_sim_walks(sr, sc, dtm, dtm_mask, cellsize, cfg_dict,
                                      mu_matrix=mu_matrix,
                                      connect_feature_matrix=connect_feature_matrix)

            for cell, count in result['cell_trav_freq'].items():
                combined_frequencies[cell[0], cell[1]] += count * weight

            for cell, vel in result['cell_max_vel'].items():
                combined_hl[cell[0], cell[1]] = max(combined_hl[cell[0], cell[1]], vel)

            if result['prob_connect'] is not None:
                source_connectivity[(sr, sc)] = result['prob_connect']

        if source_connectivity:
            if not hasattr(Config, 'SOURCE_CONNECTIVITY'):
                Config.SOURCE_CONNECTIVITY = {}
            Config.SOURCE_CONNECTIVITY.update(source_connectivity)

        return {
            'pq_lim': np.full(dtm.shape, nodata_f, dtype=np.float32),
            'li': combined_frequencies,
            'backlink_li': np.full(dtm.shape, nodata_i, dtype=np.int16),
            'fri': np.full(dtm.shape, nodata_f, dtype=np.float32),
            'backlink_fri': np.full(dtm.shape, nodata_i, dtype=np.int16),
            'h_l': combined_hl,
            'nodata_float': nodata_f,
            'nodata_int': nodata_i
        }

    else:
        # Initialize combined rasters with nodata
        combined_pq_lim = np.full(dtm.shape, nodata_f, dtype=np.float32)
        combined_pq_lim_pruned = np.full(dtm.shape, nodata_f, dtype=np.float32)
        combined_li = np.full(dtm.shape, nodata_f, dtype=np.float32)
        combined_backlink_li = np.full(dtm.shape, nodata_i, dtype=np.int16)
        combined_fri = np.full(dtm.shape, nodata_f, dtype=np.float32)
        combined_backlink_fri = np.full(dtm.shape, nodata_i, dtype=np.int16)
        combined_hl = np.full(dtm.shape, nodata_f, dtype=np.float32)

        # Process each source point INDIVIDUALLY
        for point_idx, (sr, sc) in enumerate(batch_indices):
            if (point_idx + 1) % 10 == 0 or point_idx == len(batch_indices) - 1:
                print(f"      Point {point_idx + 1}/{len(batch_indices)}")
                sys.stdout.flush()
                sys.stderr.flush()

            # Process this SINGLE point
            result = process_single_source_point(
                sr, sc, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg, fdir=fdir_matrix
            )

            # Combine standard PQ_LIM with MAX
            valid_new = (result['pq_lim'] != nodata_f) & (result['pq_lim'] > 0)
            valid_existing = (combined_pq_lim != nodata_f) & (combined_pq_lim > 0)
            both_valid = valid_new & valid_existing
            combined_pq_lim[both_valid] = np.maximum(combined_pq_lim[both_valid], result['pq_lim'][both_valid])
            only_new = valid_new & ~valid_existing
            combined_pq_lim[only_new] = result['pq_lim'][only_new]

            # Combine pruned PQ_LIM with MAX
            pq_lim_p = result.get('pq_lim_pruned', np.full(dtm.shape, nodata_f, dtype=np.float32))
            valid_new_p = (pq_lim_p != nodata_f) & (pq_lim_p > 0)
            valid_existing_p = (combined_pq_lim_pruned != nodata_f) & (combined_pq_lim_pruned > 0)
            both_valid_p = valid_new_p & valid_existing_p
            combined_pq_lim_pruned[both_valid_p] = np.maximum(combined_pq_lim_pruned[both_valid_p], pq_lim_p[both_valid_p])
            only_new_p = valid_new_p & ~valid_existing_p
            combined_pq_lim_pruned[only_new_p] = pq_lim_p[only_new_p]

            valid_new = (result['li'] != nodata_f) & (result['li'] > 0)
            valid_existing = (combined_li != nodata_f) & (combined_li > 0)
            both_valid = valid_new & valid_existing
            combined_li[both_valid] = np.maximum(combined_li[both_valid], result['li'][both_valid])
            only_new = valid_new & ~valid_existing
            combined_li[only_new] = result['li'][only_new]

            valid_new = (result['fri'] != nodata_f) & (result['fri'] > 0)
            valid_existing = (combined_fri != nodata_f) & (combined_fri > 0)
            both_valid = valid_new & valid_existing
            combined_fri[both_valid] = np.maximum(combined_fri[both_valid], result['fri'][both_valid])
            only_new = valid_new & ~valid_existing
            combined_fri[only_new] = result['fri'][only_new]

            mask_update_li = (result['pq_lim'] > combined_pq_lim)
            combined_backlink_li[mask_update_li] = result['backlink_li'][mask_update_li]

            valid_new = (result['h_l'] != nodata_f) & (result['h_l'] >= 0)
            valid_existing = (combined_hl != nodata_f) & (combined_hl >= 0)
            mask_update = valid_new & (~valid_existing | (result['pq_lim'] > combined_pq_lim))
            combined_hl[mask_update] = result['h_l'][mask_update]

            mask_update_fri = (result['fri'] > combined_fri)
            combined_backlink_fri[mask_update_fri] = result['backlink_fri'][mask_update_fri]

        return {
            'pq_lim': combined_pq_lim,
            'pq_lim_pruned': combined_pq_lim_pruned,
            'li': combined_li,
            'backlink_li': combined_backlink_li,
            'fri': combined_fri,
            'backlink_fri': combined_backlink_fri,
            'h_l': combined_hl,
            'nodata_float': nodata_f,
            'nodata_int': nodata_i
        }


def combine_rasters_max(raster_arrays, nodata):
    """
    Combine multiple raster arrays taking the MAXIMUM value where they overlap.
    """
    if len(raster_arrays) == 0:
        raise RuntimeError("No rasters to combine")

    if len(raster_arrays) == 1:
        return raster_arrays[0]

    combined = raster_arrays[0].copy()

    for i, raster in enumerate(raster_arrays[1:], 2):
        valid_combined = (combined != nodata) & (combined > 0)
        valid_new = (raster != nodata) & (raster > 0)

        both_valid = valid_combined & valid_new
        combined[both_valid] = np.maximum(combined[both_valid], raster[both_valid])

        only_new = valid_new & ~valid_combined
        combined[only_new] = raster[only_new]

    return combined




def combine_batch_results(batch_results, nodata_float, nodata_int):
    """
    Combine all batch results. Supports runoutSIM and standard MSF.
    """
    if Config.RUN_RUNOUTSIM:
        print(f"\n  Combining {len(batch_results)} batch results for runoutSIM...")
        sys.stdout.flush()
        sys.stderr.flush()

        combined_frequencies = np.zeros(batch_results[0]['li'].shape, dtype=np.float32)
        combined_hl = np.full(batch_results[0]['h_l'].shape, nodata_float, dtype=np.float32)

        for r in batch_results:
            valid_freq = (r['li'] != nodata_float) & (r['li'] > 0)
            combined_frequencies[valid_freq] += r['li'][valid_freq]
            
            valid_vel = (r['h_l'] != nodata_float) & (r['h_l'] >= 0)
            valid_existing = (combined_hl != nodata_float) & (combined_hl >= 0)
            both_valid = valid_vel & valid_existing
            combined_hl[both_valid] = np.maximum(combined_hl[both_valid], r['h_l'][both_valid])
            only_new = valid_vel & ~valid_existing
            combined_hl[only_new] = r['h_l'][only_new]

        # Calculate final ECDF
        print("  Calculating final ECDF Traverse Probabilities across batches...")
        # (Using a temporary mask for ECDF calculation)
        combined_pq_lim = calculate_ecdf(combined_frequencies, combined_frequencies == 0, nodata_float)

        return {
            'pq_lim': combined_pq_lim,
            'li': combined_frequencies,
            'backlink_li': np.full(combined_frequencies.shape, nodata_int, dtype=np.int16),
            'fri': np.full(combined_frequencies.shape, nodata_float, dtype=np.float32),
            'backlink_fri': np.full(combined_frequencies.shape, nodata_int, dtype=np.int16),
            'h_l': combined_hl,
            'nodata_float': nodata_float,
            'nodata_int': nodata_int
        }
    else:
        print(f"\n  Combining {len(batch_results)} batch results (using MAX)...")
        sys.stdout.flush()
        sys.stderr.flush()

        pq_lim_arrays = [r['pq_lim'] for r in batch_results]
        li_arrays = [r['li'] for r in batch_results]
        backlink_li_arrays = [r['backlink_li'] for r in batch_results]
        fri_arrays = [r['fri'] for r in batch_results]
        backlink_fri_arrays = [r['backlink_fri'] for r in batch_results]
        hl_arrays = [r['h_l'] for r in batch_results]

        print(f"    Combining PQ_LIM arrays...")
        pq_lim_final = combine_rasters_max(pq_lim_arrays, nodata_float)
        valid_pqlim = ((pq_lim_final != nodata_float) & (pq_lim_final > 0)).sum()
        print(f"    ✓ PQ_LIM combined: {valid_pqlim:,} valid cells")

        print(f"    Combining LI arrays...")
        li_final = combine_rasters_max(li_arrays, nodata_float)
        valid_li = ((li_final != nodata_float) & (li_final > 0)).sum()
        print(f"    ✓ LI combined: {valid_li:,} valid cells")

        print(f"    Combining FRI arrays...")
        fri_final = combine_rasters_max(fri_arrays, nodata_float)
        valid_fri = ((fri_final != nodata_float) & (fri_final > 0)).sum()
        print(f"    ✓ FRI combined: {valid_fri:,} valid cells")

        print(f"    Processing backlink and HL arrays...")
        backlink_li_final = backlink_li_arrays[0].copy()
        backlink_fri_final = backlink_fri_arrays[0].copy()
        hl_final = hl_arrays[0].copy()

        for i in range(1, len(batch_results)):
            mask_update_li = (pq_lim_arrays[i] > pq_lim_arrays[0])
            backlink_li_final[mask_update_li] = backlink_li_arrays[i][mask_update_li]
            hl_final[mask_update_li] = hl_arrays[i][mask_update_li]

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
            'h_l': hl_final,
            'nodata_float': nodata_float,
            'nodata_int': nodata_int
        }
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
    print(f"  H/L hole filling: {'YES' if getattr(cfg, 'FILL_HL_HOLES', True) else 'NO'}")
    print(f"  H/L calculation: {'EUCLIDEAN DISTANCE' if cfg.USE_DIRECT_DISTANCE_FOR_HL else 'PATH DISTANCE'}")

    print("\n\U0001f4ca OPTIONAL OUTPUTS:")
    print(f"  Save H/L raster: {'YES' if getattr(cfg, 'SAVE_HL_RASTER', False) else 'NO'}")
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

    if cfg.RESAMPLE_DTM or cfg.DO_PIT_FILLING:
        dtm_input_path = cfg.DTM_ORIGINAL_PATH
        print(f"  Reading original DTM: {dtm_input_path}")
    else:
        dtm_input_path = cfg.DTM_FILLED_PATH
        print(f"  Reading filled DTM: {dtm_input_path}")

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

    if force_flow_dir:
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
    else:
        print(f"  Reading source raster: {cfg.SOURCE_RASTER_PATH}")
        source_raster, src_nodata = read_and_snap(cfg.SOURCE_RASTER_PATH, ref_prof)

        # Snapping logic to move triggers to the local thalweg channels
    if getattr(cfg, "SNAP_TRIGGERS", False):
        print(f"  Snapping trigger points to local thalweg (radius: {cfg.SNAP_RADIUS}px)...")
        # 1. Calculate Flow Accumulation
        fac = calculate_flow_accumulation(fdir, fdir_nodata, dtm, dtm_mask)
        
        # 2. Find all source cells
        src_mask = make_mask(source_raster, src_nodata)
        source_cells = np.argwhere((~src_mask) & (source_raster != 0) & (~dtm_mask))
        
        snapped_raster = np.full(source_raster.shape, src_nodata, dtype=np.float32)
        snapped_count = 0
        
        nrows, ncols = dtm.shape
        r_dist = cfg.SNAP_RADIUS
        
        for r, c in source_cells:
            # Search in local neighborhood
            r_min = max(0, r - r_dist)
            r_max = min(nrows - 1, r + r_dist)
            c_min = max(0, c - r_dist)
            c_max = min(ncols - 1, c + r_dist)
            
            best_r, best_c = r, c
            max_fac = fac[r, c]
            
            for nr in range(r_min, r_max + 1):
                for nc in range(c_min, c_max + 1):
                    if dtm_mask[nr, nc]:
                        continue
                    if fac[nr, nc] > max_fac:
                        max_fac = fac[nr, nc]
                        best_r, best_c = nr, nc
            
            # Reassign elevation at best cell + 1.0 meter (or cfg.ADD_ELEVATION_METERS)
            new_elev = dtm[best_r, best_c] + getattr(cfg, "ADD_ELEVATION_METERS", 1.0)
            snapped_raster[best_r, best_c] = new_elev
            
            if (best_r != r) or (best_c != c):
                snapped_count += 1
                
        print(f"    Snapping complete: {snapped_count} / {len(source_cells)} points were moved.")
        source_raster = snapped_raster
        src_mask = make_mask(source_raster, src_nodata)
    else:
        # Standard replacement with DTM elevation if no snapping or no resample
        if cfg.SOURCE_INPUT_TYPE.upper() == "SHAPEFILE" and cfg.SHAPEFILE_ELEV_FIELD is None:
            source_raster, src_nodata = replace_source_with_dtm_elevation(
                source_raster, dtm, dtm_mask, src_nodata
            )

    if cfg.SAVE_INTERMEDIATE_OUTPUTS:
        source_path = os.path.join(cfg.OUTPUT_DIR, "source_final_processed.tif")
        save_raster(source_raster, ref_prof, source_path, src_nodata, cfg.COMPRESS_OUTPUTS)

    src_mask = make_mask(source_raster, src_nodata)
    source_mask_full = (~src_mask) & (source_raster != 0) & (~dtm_mask)

    num_sources = source_mask_full.sum()
    if num_sources == 0:
        raise RuntimeError("No valid source pixels found!")

    print(f"  ✓ Source raster ready")
    print(f"    Total number of source points: {num_sources}")

        # Get all source point indices
    src_pix_all = np.argwhere(source_mask_full)
    Config.SOURCE_PIXELS = src_pix_all

        # -------------------------------------------------------------------------
    # STEP: Process sources (parallel or batch)
    # -------------------------------------------------------------------------
    current_step += 1

    run_msf = getattr(cfg, "RUN_MSF", True)
    run_runoutsim = getattr(cfg, "RUN_RUNOUTSIM", False)

    if not run_msf and not run_runoutsim:
        run_msf = True  # Fallback to MSF

    combined_msf = None
    combined_msf_pruned = None
    combined_runoutsim = None
    # --- MSF Execution ---
    if run_msf:
        print_header("EXECUTING MSF (MODIFIED SINGLE FLOW) MODEL")
        cfg.RUN_RUNOUTSIM = False  # Force MSF in engine

        if cfg.ENABLE_PARALLEL_PROCESSING:
            print_step(current_step, total_steps, "Processing MSF sources in PARALLEL")
            if not MULTIPROCESSING_AVAILABLE:
                print("  WARNING: Multiprocessing not available, falling back to sequential processing")
                cfg.ENABLE_PARALLEL_PROCESSING = False

        # fdir integer raster (needed by pruning) — available if computed above
        fdir_int = fdir if 'fdir' in dir() else None

        if cfg.ENABLE_PARALLEL_PROCESSING:
            result_msf = process_sources_parallel(
                src_pix_all, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg,
                ref_profile=ref_prof, fdir_matrix=fdir_int
            )
        else:
            print_step(current_step, total_steps, "Processing MSF sources in BATCHES (sequential)")
            num_batches = int(np.ceil(num_sources / cfg.BATCH_SIZE))
            print(f"  Number of batches: {num_batches} (batch size: {cfg.BATCH_SIZE})")
            batch_results = []
            for batch_idx in range(num_batches):
                start_idx = batch_idx * cfg.BATCH_SIZE
                end_idx = min((batch_idx + 1) * cfg.BATCH_SIZE, num_sources)
                batch_sources = src_pix_all[start_idx:end_idx]
                print(f"\n  Processing MSF batch {batch_idx + 1}/{num_batches}")
                batch_result = process_source_batch(
                    batch_sources, dtm, dtm_mask, fdir_deg, fdir_mask,
                    source_raster, src_nodata, cellsize, cfg, fdir_matrix=fdir_int
                )
                valid_cells = ((batch_result['pq_lim'] != batch_result['nodata_float']) &
                               (batch_result['pq_lim'] > 0)).sum()
                print(f"  Batch {batch_idx + 1} completed: {valid_cells:,} cells reached")
                batch_results.append(batch_result)

            result_msf = combine_batch_results(batch_results, -9999.0, 32767)

        # Split standard MSF and pruned MSF from the unified result
        combined_msf = result_msf
        nodata_f_msf = result_msf.get('nodata_float', -9999.0)
        nodata_i_msf = result_msf.get('nodata_int', 32767)
        if getattr(cfg, 'ENABLE_MSF_PRUNING', False):
            pq_pruned = result_msf.get('pq_lim_pruned', None)
            if pq_pruned is not None:
                valid_pruned = (pq_pruned != nodata_f_msf) & (pq_pruned > 0)
                if valid_pruned.sum() > 0:
                    combined_msf_pruned = {
                        'pq_lim': pq_pruned,
                        'li': result_msf['li'],
                        'backlink_li': result_msf['backlink_li'],
                        'fri': result_msf['fri'],
                        'backlink_fri': result_msf['backlink_fri'],
                        'h_l': result_msf['h_l'],
                        'nodata_float': nodata_f_msf,
                        'nodata_int': nodata_i_msf
                    }
                    print(f"  MSF Pruned: {valid_pruned.sum():,} valid cells")
                else:
                    print("  WARNING: MSF Pruning enabled but no pruned cells found (check fdir input)")

        cfg.RUN_RUNOUTSIM = run_runoutsim  # Restore original value

    # --- runoutSIM Execution ---
    if run_runoutsim:
        print_header("EXECUTING RUNOUTSIM (STOCHASTIC RANDOM WALK & PCM) MODEL")
        cfg.RUN_RUNOUTSIM = True  # Force runoutSIM in engine
        
        if cfg.ENABLE_PARALLEL_PROCESSING:
            print_step(current_step, total_steps, "Processing runoutSIM sources in PARALLEL")
            if not MULTIPROCESSING_AVAILABLE:
                print("  ⚠ WARNING: Multiprocessing not available, falling back to sequential processing")
                cfg.ENABLE_PARALLEL_PROCESSING = False
                
        if cfg.ENABLE_PARALLEL_PROCESSING:
            combined_runoutsim = process_sources_parallel(
                src_pix_all, dtm, dtm_mask, fdir_deg, fdir_mask, cellsize, cfg, ref_profile=ref_prof
            )
        else:
            print_step(current_step, total_steps, "Processing runoutSIM sources in BATCHES (sequential)")
            num_batches = int(np.ceil(num_sources / cfg.BATCH_SIZE))
            print(f"  Number of batches: {num_batches} (batch size: {cfg.BATCH_SIZE})")
            batch_results = []
            for batch_idx in range(num_batches):
                start_idx = batch_idx * cfg.BATCH_SIZE
                end_idx = min((batch_idx + 1) * cfg.BATCH_SIZE, num_sources)
                batch_sources = src_pix_all[start_idx:end_idx]
                print(f"\n  Processing runoutSIM batch {batch_idx + 1}/{num_batches}")
                batch_result = process_source_batch(
                    batch_sources, dtm, dtm_mask, fdir_deg, fdir_mask,
                    source_raster, src_nodata, cellsize, cfg
                )
                valid_cells = (batch_result['li'] > 0).sum()
                print(f"  ✓ Batch {batch_idx + 1} completed: {valid_cells:,} cells reached")
                batch_results.append(batch_result)
                
            combined_runoutsim = combine_batch_results(batch_results, -9999.0, 32767)

    # -------------------------------------------------------------------------
    # STEP: Save final outputs
    # -------------------------------------------------------------------------
    current_step += 1
    print_step(current_step, total_steps, "Saving outputs")

    prof = ref_prof.copy()
    nodata_f = -9999.0
    nodata_i = 32767
    prof_float = prof.copy()
    prof_float.update(dtype="float32", nodata=nodata_f)

        # Save MSF Outputs
    if combined_msf is not None:
        if getattr(cfg, "PQLIM_FILENAME", ""):
            pq_lim_filename = cfg.PQLIM_FILENAME
        else:
            extra = getattr(cfg, "PQLIM_CUSTOM_SUFFIX", "")
            suffix = f"_msf{extra}" if run_runoutsim else extra
            if cfg.RESAMPLE_DTM:
                pq_lim_filename = f"pq_lim_{cfg.TARGET_RESOLUTION}m{suffix}.tif"
            else:
                pq_lim_filename = f"pq_lim{suffix}.tif"
                
        pq_lim_path = os.path.join(cfg.OUTPUT_DIR, pq_lim_filename)
        print(f"  Saving MSF PQ_LIM to: {pq_lim_filename}")
        save_raster(combined_msf['pq_lim'], prof_float, pq_lim_path, nodata_f, cfg.COMPRESS_OUTPUTS)

        # Save Pruned MSF if generated
        if combined_msf_pruned is not None:
            pq_pruned_path = pq_lim_path.replace(".tif", "_pruned.tif")
            pq_pruned_filename = os.path.basename(pq_pruned_path)
            print(f"  Saving Pruned MSF PQ_LIM to: {pq_pruned_filename}")
            save_raster(combined_msf_pruned['pq_lim'], prof_float, pq_pruned_path, nodata_f, cfg.COMPRESS_OUTPUTS)

        if getattr(cfg, "SAVE_HL_RASTER", False):
            hl_filename = getattr(cfg, "HL_FILENAME", "") or "hl_ratio.tif"
            if run_runoutsim:
                hl_filename = hl_filename.replace(".tif", "_msf.tif")
            hl_path = os.path.join(cfg.OUTPUT_DIR, hl_filename)
            print(f"  Saving MSF H/L ratio to: {hl_filename}")
            save_raster(combined_msf['h_l'], prof_float, hl_path, nodata_f, cfg.COMPRESS_OUTPUTS)

        if cfg.SAVE_LI_RASTER:
            li_filename = getattr(cfg, "LI_FILENAME", "") or "li_distance.tif"
            if run_runoutsim:
                li_filename = li_filename.replace(".tif", "_msf.tif")
            li_path = os.path.join(cfg.OUTPUT_DIR, li_filename)
            print(f"  Saving MSF LI to: {li_filename}")
            save_raster(combined_msf['li'], prof_float, li_path, nodata_f, cfg.COMPRESS_OUTPUTS)

        if cfg.SAVE_LI_BACKLINK:
            bl_filename = getattr(cfg, "LI_BACKLINK_FILENAME", "") or "backlink_li.tif"
            if run_runoutsim:
                bl_filename = bl_filename.replace(".tif", "_msf.tif")
            bl_path = os.path.join(cfg.OUTPUT_DIR, bl_filename)
            print(f"  Saving MSF LI Backlink to: {bl_filename}")
            prof_int = prof.copy()
            prof_int.update(dtype="int16", nodata=nodata_i)
            save_raster(combined_msf['backlink_li'], prof_int, bl_path, nodata_i, cfg.COMPRESS_OUTPUTS)

        if cfg.SAVE_FRI_RASTER:
            fri_filename = getattr(cfg, "FRI_FILENAME", "") or "fri_distance.tif"
            if run_runoutsim:
                fri_filename = fri_filename.replace(".tif", "_msf.tif")
            fri_path = os.path.join(cfg.OUTPUT_DIR, fri_filename)
            print(f"  Saving MSF FRI to: {fri_filename}")
            save_raster(combined_msf['fri'], prof_float, fri_path, nodata_f, cfg.COMPRESS_OUTPUTS)

        if cfg.SAVE_FRI_BACKLINK:
            bl_filename = getattr(cfg, "FRI_BACKLINK_FILENAME", "") or "backlink_fri.tif"
            if run_runoutsim:
                bl_filename = bl_filename.replace(".tif", "_msf.tif")
            bl_path = os.path.join(cfg.OUTPUT_DIR, bl_filename)
            print(f"  Saving MSF FRI Backlink to: {bl_filename}")
            prof_int = prof.copy()
            prof_int.update(dtype="int16", nodata=nodata_i)
            save_raster(combined_msf['backlink_fri'], prof_int, bl_path, nodata_i, cfg.COMPRESS_OUTPUTS)

    # Save runoutSIM Outputs
    if combined_runoutsim is not None:
        if getattr(cfg, "RUNOUTSIM_PQLIM_FILENAME", ""):
            ro_pq_lim_filename = cfg.RUNOUTSIM_PQLIM_FILENAME
        else:
            extra = getattr(cfg, "PQLIM_CUSTOM_SUFFIX", "")
            suffix = f"_runoutsim{extra}" if run_msf else f"_runoutsim{extra}" if extra else "_runoutsim"
            if cfg.RESAMPLE_DTM:
                ro_pq_lim_filename = f"pq_lim_{cfg.TARGET_RESOLUTION}m{suffix}.tif"
            else:
                ro_pq_lim_filename = f"pq_lim{suffix}.tif"

        pq_lim_path = os.path.join(cfg.OUTPUT_DIR, ro_pq_lim_filename)
        print(f"  Saving runoutSIM Traverse Probability (ECDF) to: {ro_pq_lim_filename}")
        save_raster(combined_runoutsim['pq_lim'], prof_float, pq_lim_path, nodata_f, cfg.COMPRESS_OUTPUTS)

        if cfg.SAVE_LI_RASTER:
            freq_filename = "runoutsim_traverse_frequency.tif"
            freq_path = os.path.join(cfg.OUTPUT_DIR, freq_filename)
            print(f"  Saving runoutSIM Traverse Frequency to: {freq_filename}")
            save_raster(combined_runoutsim['li'], prof_float, freq_path, nodata_f, cfg.COMPRESS_OUTPUTS)

        if getattr(cfg, "SAVE_HL_RASTER", False):
            vel_filename = "runoutsim_max_velocity.tif"
            vel_path = os.path.join(cfg.OUTPUT_DIR, vel_filename)
            print(f"  Saving runoutSIM Maximum Velocity (PCM) to: {vel_filename}")
            save_raster(combined_runoutsim['h_l'], prof_float, vel_path, nodata_f, cfg.COMPRESS_OUTPUTS)

        conn_path = getattr(cfg, 'RUNOUTSIM_CONN_FEATURE_PATH', "")
        if conn_path and hasattr(Config, 'SOURCE_CONNECTIVITY'):
            conn_filename = "runoutsim_source_connectivity.tif"
            conn_raster_path = os.path.join(cfg.OUTPUT_DIR, conn_filename)
            print(f"  Saving runoutSIM Source Connectivity map to: {conn_filename}")
            conn_arr = np.full(dtm.shape, nodata_f, dtype=np.float32)
            for (r, c), prob in Config.SOURCE_CONNECTIVITY.items():
                conn_arr[r, c] = prob
            save_raster(conn_arr, prof_float, conn_raster_path, nodata_f, cfg.COMPRESS_OUTPUTS)

    # -------------------------------------------------------------------------
    # STEP: Summary statistics
    # -------------------------------------------------------------------------
    current_step += 1
    print_step(current_step, total_steps, "Summary statistics")

    print(f"\n  📊 FINAL RESULTS:")
    print(f"    Total source points processed: {num_sources}")
    if cfg.ENABLE_PARALLEL_PROCESSING:
        print(f"    Processing mode: PARALLEL ({cfg.NUM_WORKERS} workers)")
    else:
        print(f"    Processing mode: SEQUENTIAL")
    
    if run_msf and combined_msf is not None:
        valid_pq = ((combined_msf['pq_lim'] != nodata_f) & (combined_msf['pq_lim'] > 0)).sum()
        print(f"    MSF cells reached: {valid_pq:,} ({100 * valid_pq / (~dtm_mask).sum():.1f}% coverage)")
        
    if run_runoutsim and combined_runoutsim is not None:
        valid_pq = ((combined_runoutsim['pq_lim'] != nodata_f) & (combined_runoutsim['pq_lim'] > 0)).sum()
        print(f"    runoutSIM cells reached: {valid_pq:,} ({100 * valid_pq / (~dtm_mask).sum():.1f}% coverage)")

    print(f"\n✅ WORKFLOW COMPLETED - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":

    try:

        main()

    except Exception as e:

        print(f"\n❌ ERROR: {e}")

        import traceback



        traceback.print_exc()