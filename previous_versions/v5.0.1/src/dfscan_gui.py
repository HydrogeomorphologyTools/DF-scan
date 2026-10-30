#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import multiprocessing
multiprocessing.freeze_support()

import sys
class DummyWriter:
    def write(self, x): pass
    def flush(self): pass

if sys.stdout is None:
    sys.stdout = DummyWriter()
if sys.stderr is None:
    sys.stderr = DummyWriter()

"""MSF – Tabbed One-Window GUI v5 (PyQt5)
- Tech theme with transparent background image support
- Toggle buttons instead of checkboxes
- Improved path field display
- Better console output capture for parallel processing
- Removed redundant tab titles
"""

import sys, os, json, threading, time, re, rasterio

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
import numpy as np
from pathlib import Path
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QPalette, QColor, QFont, QTextCursor, QIcon, QPixmap, QImage, QPainter
from PyQt5.QtWidgets import (
QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QPushButton,
QFileDialog, QTextEdit, QMessageBox, QLabel, QTabWidget, QStyleFactory,
QProgressBar, QDialog, QFrame, QGraphicsView, QGraphicsScene
)

try:
    from PyQt5.QtSvg import QSvgRenderer

    _HAS_SVG = True
except Exception:
    _HAS_SVG = False

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import dfscan_core as core
except Exception as e:
    raise SystemExit(f"Could not import dfscan_core.py: {e}")


def set_tech_glass_theme(app: QApplication):
    app.setStyle(QStyleFactory.create("Fusion"))
    palette = QPalette()
    bg0 = QColor(24, 27, 32, 200)
    bg1 = QColor(32, 36, 43, 200)
    bg2 = QColor(18, 20, 24, 220)
    fg = QColor(235, 238, 243)
    cyan = QColor(0, 179, 255)
    palette.setColor(QPalette.Window, bg0)
    palette.setColor(QPalette.WindowText, fg)
    palette.setColor(QPalette.Base, bg2)
    palette.setColor(QPalette.AlternateBase, bg1)
    palette.setColor(QPalette.ToolTipBase, bg1)
    palette.setColor(QPalette.ToolTipText, fg)
    palette.setColor(QPalette.Text, fg)
    palette.setColor(QPalette.Button, bg1)
    palette.setColor(QPalette.ButtonText, fg)
    palette.setColor(QPalette.BrightText, QColor(255, 80, 80))
    palette.setColor(QPalette.Highlight, cyan.lighter(115))
    palette.setColor(QPalette.HighlightedText, QColor(15, 18, 22))
    app.setPalette(palette)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet("""
    QWidget { color: #EBEEF3; }
        QMainWindow, QWidget#centralWidget {
        background-color: rgba(24,27,32,200);
        }
        QGroupBox {
        border: 1px solid rgba(58,64,77,160); border-radius: 12px;
        margin-top: 10px; padding: 16px; background-color: rgba(32,36,43,180);
        }
        QGroupBox::title {
        subcontrol-origin: margin; left: 12px; top: -8px;
        padding: 0 8px; color: #74d3ff; background-color: rgba(32,36,43,200); 
            font-weight: 700; font-size: 12px;
        }
        QLabel { padding: 4px 0; }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
        background-color: rgba(21,23,28,220); border: 1px solid rgba(43,49,64,200); 
        border-radius: 8px; padding: 10px 12px; min-height: 28px;
        }
        QPushButton {
        border-radius: 18px; padding: 10px 18px; font-weight: 700;
        background-color: rgba(44,51,66,220); border: 1px solid rgba(59,66,84,200);
        }
        QPushButton:hover { background-color: rgba(52,61,79,240); }
        QPushButton:checked { 
        background-color: rgba(0,179,255,180); 
        border: 1px solid rgba(0,179,255,255);
        color: #FFFFFF;
            }
        QTextEdit { 
        border: 1px solid rgba(43,49,64,200); 
        background: rgba(20,22,27,220); 
        padding: 8px;
        }
        QTabWidget::pane { 
        border: 1px solid rgba(58,64,77,160); 
        border-radius: 10px; 
        background-color: rgba(24,27,32,180);
        }
        QTabBar::tab {
        background: rgba(38,43,53,200); border: 1px solid rgba(58,64,77,160); 
        padding: 12px 18px; border-top-left-radius: 8px; border-top-right-radius: 8px; 
        margin-right: 8px; color: #EBEEF3;
            }
        QTabBar::tab:selected { 
        background: rgba(44,51,66,220); 
        color: #00b3ff; 
            font-weight: 700;
        }
        QTabBar::tab:hover { background: rgba(51,60,77,220); }
    """)


def get_config_defaults():
    return {k: getattr(core.Config, k) for k in dir(core.Config)
    if k.isupper() and not k.startswith("__")}


def apply_config_to_core(conf: dict):
    for k, v in conf.items():
        if hasattr(core.Config, k):
            setattr(core.Config, k, v)


class EmittingStream(QObject):
    text_written = pyqtSignal(str)

    def write(self, text):
        try:
            s = str(text)
        except Exception:
            s = repr(text)
        if s:
            if not s.endswith("\n"):
                s += "\n"
            self.text_written.emit(s)

    def flush(self):
        pass


def build_debris_icon():
    # Try loading local icon.ico first if present (in script dir or assets dir)
    paths_to_try = [
        "icon.ico",
        "assets/icon.ico",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "icon.ico")
    ]
    for p in paths_to_try:
        if os.path.exists(p):
            return QIcon(p)

    svg = """<svg width="96" height="96" viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#00b3ff"/><stop offset="100%" stop-color="#ff8c00"/></linearGradient></defs><rect x="0" y="0" width="96" height="96" rx="18" ry="18" fill="#20242b"/><path d="M8,72 C26,62 34,56 44,44 C54,32 64,18 88,14 L88,30 C65,36 60,48 50,58 C40,68 28,78 8,84 Z" fill="url(#g)" opacity="0.95"/><circle cx="30" cy="70" r="4" fill="#c0d4ff" opacity="0.9"/><circle cx="46" cy="58" r="3" fill="#b8e7ff" opacity="0.9"/><circle cx="60" cy="46" r="3" fill="#ffe0b3" opacity="0.9"/></svg>"""
    try:
        if _HAS_SVG:
            from PyQt5.QtSvg import QSvgRenderer
            renderer = QSvgRenderer(bytearray(svg.encode('utf-8')))
            img = QImage(96, 96, QImage.Format_ARGB32);
            img.fill(Qt.transparent)
            from PyQt5.QtGui import QPainter
            painter = QPainter(img);
            renderer.render(painter);
            painter.end()
            pm = QPixmap.fromImage(img);
            return QIcon(pm)
    except Exception:
        pass
    pm = QPixmap(96, 96);
    pm.fill(QColor(32, 36, 43));
    return QIcon(pm)


class MSFWindow(QWidget):
    run_finished = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DF-scan – Regional Workflow (PyQt5 GUI) v5")
        self.setWindowIcon(build_debris_icon())
        self.setMinimumSize(1280, 920)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self._thread = None
        self._old_out = None
        self._old_err = None
        self._log_lines = []
        self._log_buffer = []
        self._worker_log_positions = {}
        self._saw_completed = False
        self._forced_restore = None
        self._bg_pixmap = None
        self._load_background()
        self._build_ui()
        # Set aseptic default paths in core.Config before loading defaults
        core.Config.DTM_ORIGINAL_PATH = r"C:\test\msf\dtm.tif"
        core.Config.DTM_FILLED_PATH = r""
        core.Config.FDIR_PATH = r""
        core.Config.SOURCE_SHAPEFILE_PATH = r"C:\test\msf\trigger.shp"
        core.Config.SOURCE_RASTER_PATH = r""
        core.Config.PQLIM_REF_PATH = r""
        core.Config.OUTPUT_DIR = r"C:\test\msf\outputs"
        self._load_defaults()
        self._wire_enable_logic()
        self._update_source_type_visibility()
        self.run_finished.connect(self._on_run_finished)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(150)
        self._poll_timer.timeout.connect(self._poll_flush)
        self._poll_timer.start()

    def _load_background(self):
        img_path = "image.jpg"
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            img_path = os.path.join(sys._MEIPASS, "image.jpg")

        if os.path.exists(img_path):
            try:
                self._bg_pixmap = QPixmap(img_path)
            except:
                self._bg_pixmap = None
        else:
            self._bg_pixmap = None

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._bg_pixmap and not self._bg_pixmap.isNull():
            painter = QPainter(self)
            painter.setOpacity(0.15)
            scaled = self._bg_pixmap.scaled(
            self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.end()

    def _build_ui(self):
        root = QVBoxLayout(self);
        root.setContentsMargins(18, 18, 18, 18);
        root.setSpacing(14)
        hdr = QHBoxLayout();
        icon_lbl = QLabel();
        icon_lbl.setPixmap(build_debris_icon().pixmap(34, 34))
        title = QLabel("DF-scan – Regional Workflow");
        title.setStyleSheet("font-size:20px;font-weight:800;")
        subtitle = QLabel("Tabbed configuration • JSON save/load • Run • Live log");
        subtitle.setStyleSheet("color:#C0CAD6;")
        col = QVBoxLayout();
        col.addWidget(title);
        col.addWidget(subtitle)
        hdr.addWidget(icon_lbl);
        hdr.addSpacing(8);
        hdr.addLayout(col);
        hdr.addStretch(1)
        root.addLayout(hdr)
        bar = QHBoxLayout();
        self.btn_load = self._pill_button("Load Config…");
        self.btn_save = self._pill_button("Save Config…")
        self.btn_run = self._pill_button("Run", primary=True);
        self.btn_close = self._pill_button("Close")
        bar.addWidget(self.btn_load);
        bar.addWidget(self.btn_save);
        bar.addStretch(1);
        bar.addWidget(self.btn_run);
        bar.addWidget(self.btn_close)
        root.addLayout(bar)
        self.tabs = QTabWidget();
        self.tabs.setTabPosition(QTabWidget.North)
        root.addWidget(self.tabs, 1)
        self._tab_inputs();
        self._tab_resampling();
        self._tab_parallel();
        self._tab_processing();
        self._tab_msf();
        self._tab_runoutsim();
        self._tab_advanced();
        self._tab_outputs();
        self._tab_logs()
        status_layout = QHBoxLayout()
        self.status_bar = QLabel("Ready");
        self._set_status("Ready")
        self.progress = QProgressBar();
        self.progress.setValue(0);
        self.progress.setMaximum(100)
        self.progress.setStyleSheet(
        "QProgressBar{border-radius:8px;background:rgba(30,33,40,220);text-align:center;}QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #00b3ff,stop:1 #ff8c00);border-radius:8px;}")
        status_layout.addWidget(self.status_bar);
        status_layout.addWidget(self.progress, 1)
        root.addLayout(status_layout)
        self.btn_load.clicked.connect(self.on_load);
        self.btn_save.clicked.connect(self.on_save)
        self.btn_run.clicked.connect(self.on_run);
        self.btn_close.clicked.connect(self.close)

    def _pill_button(self, text, primary=False):
        btn = QPushButton(text)
        if primary: btn.setStyleSheet(
        "QPushButton{background-color:rgba(0,179,255,200);color:#FFF;font-weight:800;}QPushButton:hover{background-color:rgba(0,200,255,255);}")
        return btn

    def _toggle_button(self, text, checked=False):
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setMinimumHeight(36)
        return btn

    def _make_scrollable(self, widget):
        from PyQt5.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        return scroll

    def _tab_inputs(self):
        tab = QWidget();
        layout = QVBoxLayout(tab);
        layout.setSpacing(12)
        grp = QGroupBox("Input Files");
        form = QFormLayout();
        form.setSpacing(10);
        form.setLabelAlignment(Qt.AlignRight)
        self.cmb_source_type = QComboBox();
        self.cmb_source_type.addItems(["SHAPEFILE", "RASTER"])
        form.addRow("Source Type:", self.cmb_source_type)
        self.e_dtm_orig = QLineEdit();
        btn_dtm_orig = QPushButton("…");
        btn_dtm_orig.setMaximumWidth(40)
        btn_dtm_orig.clicked.connect(
        lambda: self._browse_file(self.e_dtm_orig, "Select DTM Original", "GeoTIFF (*.tif)"))
        h1 = QHBoxLayout();
        h1.addWidget(self.e_dtm_orig);
        h1.addWidget(btn_dtm_orig)
        form.addRow("DTM Original:", h1)
        self.btn_dtm_filled = self._toggle_button("Use Filled DTM")
        self.e_dtm_filled = QLineEdit();
        btn_dtm_filled = QPushButton("…");
        btn_dtm_filled.setMaximumWidth(40)
        btn_dtm_filled.clicked.connect(
        lambda: self._browse_file(self.e_dtm_filled, "Select DTM Filled", "GeoTIFF (*.tif)"))
        h2 = QHBoxLayout();
        h2.addWidget(self.btn_dtm_filled);
        h2.addWidget(self.e_dtm_filled);
        h2.addWidget(btn_dtm_filled)
        form.addRow("DTM Filled:", h2)
        self.btn_fdir = self._toggle_button("Use FDIR")
        self.e_fdir = QLineEdit();
        btn_fdir = QPushButton("…");
        btn_fdir.setMaximumWidth(40)
        btn_fdir.clicked.connect(lambda: self._browse_file(self.e_fdir, "Select Flow Direction", "GeoTIFF (*.tif)"))
        h3 = QHBoxLayout();
        h3.addWidget(self.btn_fdir);
        h3.addWidget(self.e_fdir);
        h3.addWidget(btn_fdir)
        form.addRow("FDIR Path:", h3)
        self.e_source_shp = QLineEdit();
        btn_source_shp = QPushButton("…");
        btn_source_shp.setMaximumWidth(40)
        btn_source_shp.clicked.connect(
        lambda: self._browse_file(self.e_source_shp, "Select Shapefile", "Shapefile (*.shp)"))
        h4 = QHBoxLayout();
        h4.addWidget(self.e_source_shp);
        h4.addWidget(btn_source_shp)
        form.addRow("Source Shapefile:", h4)
        self.btn_source_raster = self._toggle_button("Use Source Raster")
        self.e_source_raster = QLineEdit();
        btn_source_raster = QPushButton("…");
        btn_source_raster.setMaximumWidth(40)
        btn_source_raster.clicked.connect(
        lambda: self._browse_file(self.e_source_raster, "Select Source Raster", "GeoTIFF (*.tif)"))
        h5 = QHBoxLayout();
        h5.addWidget(self.btn_source_raster);
        h5.addWidget(self.e_source_raster);
        h5.addWidget(btn_source_raster)
        form.addRow("Source Raster:", h5)
        self.e_shape_elev = QLineEdit()
        form.addRow("Shapefile Elev Field:", self.e_shape_elev)
        self.btn_pqlim = self._toggle_button("Use PQ_LIM Reference")
        self.e_pqlim = QLineEdit();
        btn_pqlim = QPushButton("…");
        btn_pqlim.setMaximumWidth(40)
        btn_pqlim.clicked.connect(lambda: self._browse_file(self.e_pqlim, "Select PQ_LIM Reference", "GeoTIFF (*.tif)"))
        h6 = QHBoxLayout();
        h6.addWidget(self.btn_pqlim);
        h6.addWidget(self.e_pqlim);
        h6.addWidget(btn_pqlim)
        form.addRow("PQ_LIM Ref:", h6)
        self.e_outdir = QLineEdit();
        btn_outdir = QPushButton("…");
        btn_outdir.setMaximumWidth(40)
        btn_outdir.clicked.connect(lambda: self._browse_dir(self.e_outdir, "Select Output Directory"))
        h7 = QHBoxLayout();
        h7.addWidget(self.e_outdir);
        h7.addWidget(btn_outdir)
        form.addRow("Output Directory:", h7)

        # PQ_LIM Filename (moved here from outputs tab)
        self.e_pqlim_filename = QLineEdit()
        self.e_pqlim_filename.setPlaceholderText("Default: pq_lim.tif (or with resolution suffix)")
        form.addRow("PQ_LIM Filename:", self.e_pqlim_filename)

        grp.setLayout(form);
        layout.addWidget(grp);

        # Trigger Points Snapping Group Box (New in v2)
        grp_snap = QGroupBox("Trigger Points Snapping")
        form_snap = QFormLayout()
        form_snap.setSpacing(10)
        form_snap.setLabelAlignment(Qt.AlignRight)

        self.btn_snap = self._toggle_button("Snap Triggers to local thalweg channels", True)
        form_snap.addRow("Snap Triggers:", self.btn_snap)

        self.spn_snap_radius = QSpinBox()
        self.spn_snap_radius.setRange(1, 20)
        self.spn_snap_radius.setValue(2)
        form_snap.addRow("Search Radius (pixels):", self.spn_snap_radius)

        self.dsp_snap_height = QDoubleSpinBox()
        self.dsp_snap_height.setRange(0.0, 10.0)
        self.dsp_snap_height.setValue(1.0)
        self.dsp_snap_height.setSingleStep(0.5)
        self.dsp_snap_height.setDecimals(1)
        self.dsp_snap_height.setSuffix(" m")
        form_snap.addRow("Elevation Offset (m):", self.dsp_snap_height)

        grp_snap.setLayout(form_snap)
        layout.addWidget(grp_snap)

        layout.addStretch(1)
        self.tabs.addTab(self._make_scrollable(tab), "Inputs")

    def _tab_resampling(self):
        tab = QWidget();
        layout = QVBoxLayout(tab);
        layout.setSpacing(12)
        grp = QGroupBox("DTM Resampling");
        form = QFormLayout();
        form.setSpacing(10);
        form.setLabelAlignment(Qt.AlignRight)
        self.btn_resample = self._toggle_button("Enable Resampling")
        form.addRow("Resample DTM:", self.btn_resample)
        self.spn_target_res = QSpinBox();
        self.spn_target_res.setRange(1, 1000);
        self.spn_target_res.setValue(25)
        form.addRow("Target Resolution (m):", self.spn_target_res)
        self.cmb_agg = QComboBox();
        self.cmb_agg.addItems(["median", "mean", "bilinear"])
        form.addRow("Aggregation Method:", self.cmb_agg)
        grp.setLayout(form);
        layout.addWidget(grp);

        # Trigger Points Snapping Group Box (Moved here in v2)
        grp_snap = QGroupBox("Trigger Points Snapping")
        form_snap = QFormLayout()
        form_snap.setSpacing(10)
        form_snap.setLabelAlignment(Qt.AlignRight)

        self.btn_snap = self._toggle_button("Snap Triggers to local thalweg channels", True)
        form_snap.addRow("Snap Triggers:", self.btn_snap)

        self.spn_snap_radius = QSpinBox()
        self.spn_snap_radius.setRange(1, 20)
        self.spn_snap_radius.setValue(2)
        form_snap.addRow("Search Radius (pixels):", self.spn_snap_radius)

        self.dsp_snap_height = QDoubleSpinBox()
        self.dsp_snap_height.setRange(0.0, 10.0)
        self.dsp_snap_height.setValue(1.0)
        self.dsp_snap_height.setSingleStep(0.5)
        self.dsp_snap_height.setDecimals(1)
        self.dsp_snap_height.setSuffix(" m")
        form_snap.addRow("Elevation Offset (m):", self.dsp_snap_height)

        grp_snap.setLayout(form_snap)
        layout.addWidget(grp_snap)

        layout.addStretch(1)
        self.tabs.addTab(self._make_scrollable(tab), "Resampling")

    def _tab_parallel(self):
        tab = QWidget();
        layout = QVBoxLayout(tab);
        layout.setSpacing(12)
        grp = QGroupBox("Parallel Processing");
        form = QFormLayout();
        form.setSpacing(10);
        form.setLabelAlignment(Qt.AlignRight)
        self.btn_parallel = self._toggle_button("Enable Parallel Processing")
        form.addRow("Parallel:", self.btn_parallel)
        self.spn_workers = QSpinBox();
        self.spn_workers.setRange(1, 64);
        self.spn_workers.setValue(12)
        form.addRow("Num Workers:", self.spn_workers)
        self.spn_ppw = QSpinBox();
        self.spn_ppw.setRange(1, 10000);
        self.spn_ppw.setValue(200)
        form.addRow("Points per Worker:", self.spn_ppw)
        grp.setLayout(form);
        layout.addWidget(grp);
        layout.addStretch(1)
        self.tabs.addTab(self._make_scrollable(tab), "Parallel")

    def _tab_processing(self):
        tab = QWidget();
        layout = QVBoxLayout(tab);
        layout.setSpacing(12)
        grp = QGroupBox("Processing Options");
        form = QFormLayout();
        form.setSpacing(10);
        form.setLabelAlignment(Qt.AlignRight)
        self.btn_pit = self._toggle_button("Enable Pit Filling", True)
        form.addRow("Pit Filling:", self.btn_pit)

        self.btn_calc_fdir = self._toggle_button("Calculate Flow Direction", True)
        form.addRow("Calc Flow Dir:", self.btn_calc_fdir)

        grp.setLayout(form);
        layout.addWidget(grp);
        layout.addStretch(1)
        self.tabs.addTab(self._make_scrollable(tab), "Processing")

    def _tab_msf(self):
        tab = QWidget();
        layout = QVBoxLayout(tab);
        layout.setSpacing(12)
        grp = QGroupBox("MSF Model Parameters");
        form = QFormLayout();
        form.setSpacing(10);
        form.setLabelAlignment(Qt.AlignRight)

        # ENABLE MODEL TOGGLE
        self.btn_run_msf = self._toggle_button("Enable MSF", True)
        form.addRow("Enable MSF:", self.btn_run_msf)

        self.spn_maxslope = QDoubleSpinBox();
        self.spn_maxslope.setRange(0, 90);
        self.spn_maxslope.setValue(30);
        self.spn_maxslope.setDecimals(1)
        form.addRow("Max Slope (deg):", self.spn_maxslope)
        self.dsp_hl = QDoubleSpinBox();
        self.dsp_hl.setRange(0, 10);
        self.dsp_hl.setValue(0.25);
        self.dsp_hl.setDecimals(4);
        self.dsp_hl.setSingleStep(0.01)
        form.addRow("H/L Threshold:", self.dsp_hl)
        self.btn_fill_hl_holes = self._toggle_button("H/L Hole Filling")
        self.btn_fill_hl_holes.setChecked(True)
        form.addRow("Continuità percorso:", self.btn_fill_hl_holes)
        self.btn_dir_uphill = self._toggle_button("Direction Aware Uphill")
        form.addRow("Dir Uphill:", self.btn_dir_uphill)
        self.btn_direct_hl = self._toggle_button("Direct Distance H/L")
        form.addRow("Euclidean H/L:", self.btn_direct_hl)
        self.spn_hrma_from = QSpinBox();
        self.spn_hrma_from.setRange(0, 1000);
        self.spn_hrma_from.setValue(90)
        form.addRow("HRMA From:", self.spn_hrma_from)
        self.spn_hrma_to = QSpinBox();
        self.spn_hrma_to.setRange(0, 1000);
        self.spn_hrma_to.setValue(90)
        form.addRow("HRMA To:", self.spn_hrma_to)
        self.dsp_zero = QDoubleSpinBox();
        self.dsp_zero.setRange(0, 10);
        self.dsp_zero.setValue(0.5);
        self.dsp_zero.setDecimals(2)
        form.addRow("Zero Factor:", self.dsp_zero)
        self.spn_cut = QSpinBox();
        self.spn_cut.setRange(0, 180);
        self.spn_cut.setValue(45)
        form.addRow("Cut Angle:", self.spn_cut)
        self.dsp_slope = QDoubleSpinBox();
        self.dsp_slope.setRange(0, 1);
        self.dsp_slope.setValue(0.011111);
        self.dsp_slope.setDecimals(6)
        form.addRow("Slope:", self.dsp_slope)

        # PATH PRUNING
        self.btn_msf_pruning = self._toggle_button("Enable Path Pruning", False)
        form.addRow("Path Pruning:", self.btn_msf_pruning)
        self.dsp_msf_pruning_threshold = QDoubleSpinBox()
        self.dsp_msf_pruning_threshold.setRange(1.0, 3.0)
        self.dsp_msf_pruning_threshold.setValue(1.5)
        self.dsp_msf_pruning_threshold.setDecimals(2)
        self.dsp_msf_pruning_threshold.setSingleStep(0.05)
        form.addRow("Pruning Threshold:", self.dsp_msf_pruning_threshold)



        grp.setLayout(form);
        layout.addWidget(grp);
        layout.addStretch(1)
        self.tabs.addTab(self._make_scrollable(tab), "MSF Model")

    def _tab_runoutsim(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)
        grp = QGroupBox("runoutSIM Model Parameters")
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        # Run toggle
        self.btn_run_runoutsim = self._toggle_button("Enable runoutSIM", False)
        form.addRow("Enable runoutSIM:", self.btn_run_runoutsim)

        # Exponent of divergence
        self.spn_ro_ediv = QDoubleSpinBox()
        self.spn_ro_ediv.setRange(0.1, 10.0)
        self.spn_ro_ediv.setValue(1.5)
        self.spn_ro_ediv.setDecimals(2)
        form.addRow("Exponent of Divergence:", self.spn_ro_ediv)

        # Flow persistence factor
        self.spn_ro_persist = QDoubleSpinBox()
        self.spn_ro_persist.setRange(0.1, 10.0)
        self.spn_ro_persist.setValue(1.3)
        self.spn_ro_persist.setDecimals(2)
        form.addRow("Flow Persistence Factor:", self.spn_ro_persist)

        # Slope threshold (deg)
        self.spn_ro_slopethresh = QDoubleSpinBox()
        self.spn_ro_slopethresh.setRange(0.0, 90.0)
        self.spn_ro_slopethresh.setValue(40.0)
        self.spn_ro_slopethresh.setDecimals(1)
        form.addRow("Slope Threshold (deg):", self.spn_ro_slopethresh)

        # Monte Carlo Walks
        self.spn_ro_walks = QSpinBox()
        self.spn_ro_walks.setRange(1, 100000)
        self.spn_ro_walks.setValue(1000)
        self.spn_ro_walks.setSingleStep(100)
        form.addRow("Monte Carlo Walks:", self.spn_ro_walks)

        # Friction coefficient
        self.dsp_ro_friction = QDoubleSpinBox()
        self.dsp_ro_friction.setRange(0.001, 2.0)
        self.dsp_ro_friction.setValue(0.06)
        self.dsp_ro_friction.setDecimals(3)
        self.dsp_ro_friction.setSingleStep(0.01)
        form.addRow("Friction Coefficient (Mu):", self.dsp_ro_friction)

        # Spatially varying friction (raster)
        self.e_ro_fric_raster = QLineEdit()
        btn_ro_fric = QPushButton("…")
        btn_ro_fric.setMaximumWidth(40)
        btn_ro_fric.clicked.connect(lambda: self._browse_file(self.e_ro_fric_raster, "Select Friction Raster", "GeoTIFF (*.tif)"))
        h1 = QHBoxLayout()
        h1.addWidget(self.e_ro_fric_raster)
        h1.addWidget(btn_ro_fric)
        form.addRow("Friction Raster (Optional):", h1)

        # Mass-to-drag ratio
        self.dsp_ro_massdrag = QDoubleSpinBox()
        self.dsp_ro_massdrag.setRange(1.0, 1000.0)
        self.dsp_ro_massdrag.setValue(45.0)
        self.dsp_ro_massdrag.setDecimals(1)
        form.addRow("Mass-to-Drag Ratio (M/D):", self.dsp_ro_massdrag)

        # Initial velocity
        self.dsp_ro_intvel = QDoubleSpinBox()
        self.dsp_ro_intvel.setRange(0.0, 50.0)
        self.dsp_ro_intvel.setValue(1.0)
        self.dsp_ro_intvel.setDecimals(1)
        form.addRow("Initial Velocity (v0):", self.dsp_ro_intvel)

        # Source cell probability raster (optional)
        self.e_ro_src_prob = QLineEdit()
        btn_ro_src = QPushButton("…")
        btn_ro_src.setMaximumWidth(40)
        btn_ro_src.clicked.connect(lambda: self._browse_file(self.e_ro_src_prob, "Select Source Probability Raster", "GeoTIFF (*.tif)"))
        h2 = QHBoxLayout()
        h2.addWidget(self.e_ro_src_prob)
        h2.addWidget(btn_ro_src)
        form.addRow("Source Prob. Raster (Optional):", h2)

        # Connectivity target feature (optional)
        self.e_ro_conn_feature = QLineEdit()
        btn_ro_conn = QPushButton("…")
        btn_ro_conn.setMaximumWidth(40)
        btn_ro_conn.clicked.connect(lambda: self._browse_file(self.e_ro_conn_feature, "Select Connectivity Target File", "Shapefile/GeoTIFF (*.shp *.tif)"))
        h3 = QHBoxLayout()
        h3.addWidget(self.e_ro_conn_feature)
        h3.addWidget(btn_ro_conn)
        form.addRow("Connectivity Target (Optional):", h3)

        grp.setLayout(form)
        layout.addWidget(grp)
        layout.addStretch(1)
        self.tabs.addTab(self._make_scrollable(tab), "runoutSIM")

    def _tab_advanced(self):
        tab = QWidget();
        layout = QVBoxLayout(tab);
        layout.setSpacing(12)
        grp = QGroupBox("Advanced Options");
        form = QFormLayout();
        form.setSpacing(10);
        form.setLabelAlignment(Qt.AlignRight)
        self.btn_save_inter = self._toggle_button("Save Intermediate")
        form.addRow("Save Intermediate:", self.btn_save_inter)
        self.btn_compress = self._toggle_button("Compress Outputs", True)
        form.addRow("Compress:", self.btn_compress)
        grp.setLayout(form);
        layout.addWidget(grp);
        layout.addStretch(1)
        self.tabs.addTab(self._make_scrollable(tab), "Advanced")

    def _tab_outputs(self):
        tab = QWidget();
        layout = QVBoxLayout(tab);
        layout.setSpacing(12)
        grp = QGroupBox("Output Options");
        form = QFormLayout();
        form.setSpacing(10);
        form.setLabelAlignment(Qt.AlignRight)
        # Output Directory (moved here from inputs tab)
        self.e_outdir = QLineEdit();
        btn_outdir = QPushButton("…");
        btn_outdir.setMaximumWidth(40)
        btn_outdir.clicked.connect(lambda: self._browse_dir(self.e_outdir, "Select Output Directory"))
        h7 = QHBoxLayout();
        h7.addWidget(self.e_outdir);
        h7.addWidget(btn_outdir)
        form.addRow("Output Directory:", h7)

        # PQ_LIM Filename (moved here from inputs/outputs changes)
        self.e_pqlim_filename = QLineEdit()
        self.e_pqlim_filename.setPlaceholderText("Default: pq_lim.tif (or with resolution suffix)")
        form.addRow("PQ_LIM Filename:", self.e_pqlim_filename)


        # PQ_LIM filename (always saved)
        self.e_pqlim_filename = QLineEdit()
        self.e_pqlim_filename.setPlaceholderText("Default: pq_lim.tif (or with resolution suffix)")
        form.addRow("PQ_LIM Filename:", self.e_pqlim_filename)

        # HL options
        self.btn_save_hl = self._toggle_button("Save H/L Raster")
        self.e_hl_filename = QLineEdit()
        self.e_hl_filename.setPlaceholderText("Default: hl_ratio.tif")
        h_hl = QHBoxLayout()
        h_hl.addWidget(self.btn_save_hl, 1)
        h_hl.addWidget(self.e_hl_filename, 2)
        form.addRow("H/L Raster:", h_hl)

        # LI options
        self.btn_save_li = self._toggle_button("Save LI Raster")
        self.e_li_filename = QLineEdit()
        self.e_li_filename.setPlaceholderText("Default: li_distance.tif")
        h_li = QHBoxLayout()
        h_li.addWidget(self.btn_save_li, 1)
        h_li.addWidget(self.e_li_filename, 2)
        form.addRow("LI Raster:", h_li)

        # LI Backlink options
        self.btn_save_li_bl = self._toggle_button("Save LI Backlink")
        self.e_li_bl_filename = QLineEdit()
        self.e_li_bl_filename.setPlaceholderText("Default: backlink_li.tif")
        h_li_bl = QHBoxLayout()
        h_li_bl.addWidget(self.btn_save_li_bl, 1)
        h_li_bl.addWidget(self.e_li_bl_filename, 2)
        form.addRow("LI Backlink:", h_li_bl)

        # FRI options
        self.btn_save_fri = self._toggle_button("Save FRI Raster")
        self.e_fri_filename = QLineEdit()
        self.e_fri_filename.setPlaceholderText("Default: fri_distance.tif")
        h_fri = QHBoxLayout()
        h_fri.addWidget(self.btn_save_fri, 1)
        h_fri.addWidget(self.e_fri_filename, 2)
        form.addRow("FRI Raster:", h_fri)

        # FRI Backlink options
        self.btn_save_fri_bl = self._toggle_button("Save FRI Backlink")
        self.e_fri_bl_filename = QLineEdit()
        self.e_fri_bl_filename.setPlaceholderText("Default: backlink_fri.tif")
        h_fri_bl = QHBoxLayout()
        h_fri_bl.addWidget(self.btn_save_fri_bl, 1)
        h_fri_bl.addWidget(self.e_fri_bl_filename, 2)
        form.addRow("FRI Backlink:", h_fri_bl)

        # Map Preview option
        self.btn_show_preview = self._toggle_button("Show Map Preview at Completion", False)
        form.addRow("Map Preview:", self.btn_show_preview)

        grp.setLayout(form);
        layout.addWidget(grp);
        layout.addStretch(1)
        self.tabs.addTab(self._make_scrollable(tab), "Outputs")

    def _tab_logs(self):
        tab = QWidget();
        layout = QVBoxLayout(tab);
        layout.setSpacing(8)

        self.console = QTextEdit();
        self.console.setReadOnly(True)
        self.console.setStyleSheet("QTextEdit{font-family:'Consolas','Courier New',monospace;font-size:10pt;}")

        self.worker_console = QTextEdit();
        self.worker_console.setReadOnly(True)
        self.worker_console.setStyleSheet("QTextEdit{font-family:'Consolas','Courier New',monospace;font-size:10pt;}")

        from PyQt5.QtWidgets import QSplitter, QLabel
        splitter = QSplitter(Qt.Horizontal)

        # Left widget: Main Log
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        lbl_left = QLabel("<b>Main Workflow Log:</b>")
        lbl_left.setStyleSheet("color:#A0AEC0;")
        left_layout.addWidget(lbl_left)
        left_layout.addWidget(self.console)

        # Right widget: Worker Log
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        lbl_right = QLabel("<b>Parallel Workers Output (Live):</b>")
        lbl_right.setStyleSheet("color:#A0AEC0;")
        right_layout.addWidget(lbl_right)
        right_layout.addWidget(self.worker_console)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([450, 450])

        h = QHBoxLayout()
        self.btn_clear_log = self._toggle_button("Clear on Run", True)
        btn_export = QPushButton("Export Log…");
        btn_export.clicked.connect(self._export_log)
        h.addWidget(self.btn_clear_log);
        h.addWidget(btn_export);
        h.addStretch(1)
        layout.addLayout(h);
        layout.addWidget(splitter, 1)
        self.tabs.addTab(tab, "Console")

    def _browse_file(self, line_edit, caption, filter_str):
        path, _ = QFileDialog.getOpenFileName(self, caption, "", filter_str)
        if path: line_edit.setText(path)

    def _browse_dir(self, line_edit, caption):
        path = QFileDialog.getExistingDirectory(self, caption)
        if path: line_edit.setText(path)

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Log", "msf_log.txt", "Text Files (*.txt)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.console.toPlainText())
                QMessageBox.information(self, "Exported", f"Log exported to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export log:\n{e}")

    def _wire_enable_logic(self):
        self.btn_dtm_filled.toggled.connect(lambda c: self.e_dtm_filled.setEnabled(c))
        self.btn_fdir.toggled.connect(lambda c: self.e_fdir.setEnabled(c))
        self.btn_source_raster.toggled.connect(lambda c: self.e_source_raster.setEnabled(c))
        self.btn_pqlim.toggled.connect(lambda c: self.e_pqlim.setEnabled(c))
        self.btn_resample.toggled.connect(lambda c: (
        self.spn_target_res.setEnabled(c), 
        self.cmb_agg.setEnabled(c),
        self.btn_pit.setChecked(True) if c else None
        ))
        self.btn_snap.toggled.connect(lambda c: (
        self.spn_snap_radius.setEnabled(c),
        self.dsp_snap_height.setEnabled(c)
        ))
        self.btn_msf_pruning.toggled.connect(lambda c: self.dsp_msf_pruning_threshold.setEnabled(c))
        self.btn_parallel.toggled.connect(lambda c: (self.spn_workers.setEnabled(c), self.spn_ppw.setEnabled(c)))
        self.btn_save_hl.toggled.connect(lambda c: self.e_hl_filename.setEnabled(c))
        self.btn_save_li.toggled.connect(lambda c: self.e_li_filename.setEnabled(c))
        self.btn_save_li_bl.toggled.connect(lambda c: self.e_li_bl_filename.setEnabled(c))
        self.btn_save_fri.toggled.connect(lambda c: self.e_fri_filename.setEnabled(c))
        self.btn_save_fri_bl.toggled.connect(lambda c: self.e_fri_bl_filename.setEnabled(c))
        self.cmb_source_type.currentTextChanged.connect(self._update_source_type_visibility)

    def _update_source_type_visibility(self):
        is_shp = (self.cmb_source_type.currentText() == "SHAPEFILE")
        self.e_source_shp.setEnabled(is_shp)
        self.e_shape_elev.setEnabled(is_shp)

        self.btn_source_raster.setEnabled(not is_shp)
        if is_shp:
            self.btn_source_raster.setChecked(False)
            self.e_source_raster.setEnabled(False)
        else:
            self.btn_source_raster.setChecked(True)
            self.e_source_raster.setEnabled(True)

    def _load_defaults(self):
        d = get_config_defaults()
        self.cmb_source_type.setCurrentText(d.get("SOURCE_INPUT_TYPE", "SHAPEFILE"))
        self.e_dtm_orig.setText(d.get("DTM_ORIGINAL_PATH", ""))
        dtm_filled = d.get("DTM_FILLED_PATH", "")
        self.btn_dtm_filled.setChecked(bool(dtm_filled))
        self.e_dtm_filled.setText(dtm_filled)
        fdir_path = d.get("FDIR_PATH", "")
        self.btn_fdir.setChecked(bool(fdir_path))
        self.e_fdir.setText(fdir_path)
        self.e_source_shp.setText(d.get("SOURCE_SHAPEFILE_PATH", ""))
        src_raster = d.get("SOURCE_RASTER_PATH", "")
        self.btn_source_raster.setChecked(bool(src_raster))
        self.e_source_raster.setText(src_raster)
        self.e_shape_elev.setText(d.get("SHAPEFILE_ELEV_FIELD", ""))
        pqlim = d.get("PQLIM_REF_PATH", "")
        self.btn_pqlim.setChecked(bool(pqlim))
        self.e_pqlim.setText(pqlim)
        self.e_outdir.setText(d.get("OUTPUT_DIR", ""))
        self.btn_resample.setChecked(d.get("RESAMPLE_DTM", False))
        self.spn_target_res.setValue(d.get("TARGET_RESOLUTION", 25))
        self.cmb_agg.setCurrentText(d.get("AGGREGATION_METHOD", "bilinear"))
        self.btn_snap.setChecked(d.get("SNAP_TRIGGERS", True))
        self.spn_snap_radius.setValue(d.get("SNAP_RADIUS", 2))
        self.dsp_snap_height.setValue(d.get("ADD_ELEVATION_METERS", 1.0))

        # Sync enabled state for snapping controls
        snap_ok = self.btn_snap.isChecked()
        self.btn_snap.setEnabled(True)
        self.spn_snap_radius.setEnabled(snap_ok)
        self.dsp_snap_height.setEnabled(snap_ok)
        self.btn_msf_pruning.setChecked(d.get("ENABLE_MSF_PRUNING", False))
        self.dsp_msf_pruning_threshold.setValue(d.get("MSF_PRUNING_THRESHOLD", 1.5))
        self.dsp_msf_pruning_threshold.setEnabled(self.btn_msf_pruning.isChecked())
        self.btn_parallel.setChecked(d.get("ENABLE_PARALLEL_PROCESSING", False))
        self.spn_workers.setValue(d.get("NUM_WORKERS", 12))
        self.spn_ppw.setValue(d.get("POINTS_PER_WORKER", 1))
        self.btn_pit.setChecked(d.get("DO_PIT_FILLING", True))
        self.btn_calc_fdir.setChecked(d.get("CALCULATE_FLOW_DIRECTION", True))
        self.spn_maxslope.setValue(d.get("MAX_SLOPE_DEGREES", 30))
        self.dsp_hl.setValue(d.get("H_L_THRESHOLD", 0.25))
        self.btn_fill_hl_holes.setChecked(d.get("FILL_HL_HOLES", True))
        self.btn_dir_uphill.setChecked(d.get("USE_DIRECTION_AWARE_UPHILL", False))
        self.btn_direct_hl.setChecked(d.get("USE_DIRECT_DISTANCE_FOR_HL", False))
        self.spn_hrma_from.setValue(d.get("HRMA_FROM_THRESH_LI", 90))
        self.spn_hrma_to.setValue(d.get("HRMA_TO_THRESH_LI", 90))
        self.dsp_zero.setValue(d.get("ZERO_FACTOR", 0.5))
        self.spn_cut.setValue(d.get("CUT_ANGLE", 45))
        self.dsp_slope.setValue(d.get("SLOPE", 0.011111))
        self.btn_save_inter.setChecked(d.get("SAVE_INTERMEDIATE_OUTPUTS", False))
        self.btn_compress.setChecked(d.get("COMPRESS_OUTPUTS", True))
        self.btn_save_hl.setChecked(d.get("SAVE_HL_RASTER", False))
        self.e_hl_filename.setText(d.get("HL_FILENAME", ""))
        self.e_hl_filename.setEnabled(self.btn_save_hl.isChecked())

        self.btn_save_li.setChecked(d.get("SAVE_LI_RASTER", False))
        self.e_li_filename.setText(d.get("LI_FILENAME", ""))
        self.e_li_filename.setEnabled(self.btn_save_li.isChecked())

        self.btn_save_li_bl.setChecked(d.get("SAVE_LI_BACKLINK", False))
        self.e_li_bl_filename.setText(d.get("LI_BACKLINK_FILENAME", ""))
        self.e_li_bl_filename.setEnabled(self.btn_save_li_bl.isChecked())

        self.btn_save_fri.setChecked(d.get("SAVE_FRI_RASTER", False))
        self.e_fri_filename.setText(d.get("FRI_FILENAME", ""))
        self.e_fri_filename.setEnabled(self.btn_save_fri.isChecked())

        self.btn_save_fri_bl.setChecked(d.get("SAVE_FRI_BACKLINK", False))
        self.e_fri_bl_filename.setText(d.get("FRI_BACKLINK_FILENAME", ""))
        self.e_fri_bl_filename.setEnabled(self.btn_save_fri_bl.isChecked())

        self.e_pqlim_filename.setText(d.get("PQLIM_FILENAME", ""))
        self.btn_show_preview.setChecked(d.get("SHOW_MAP_PREVIEW", False))
        self.btn_run_msf.setChecked(d.get("RUN_MSF", True))
        self.btn_run_runoutsim.setChecked(d.get("RUN_RUNOUTSIM", False))
        self.spn_ro_ediv.setValue(d.get("RUNOUTSIM_E_DIV", 2.1))
        self.spn_ro_persist.setValue(d.get("RUNOUTSIM_PERSISTENCE", 1.6))
        self.spn_ro_slopethresh.setValue(d.get("RUNOUTSIM_SLOPE_THRESH", 40.0))
        self.spn_ro_walks.setValue(d.get("RUNOUTSIM_WALKS", 1000))
        self.dsp_ro_friction.setValue(d.get("RUNOUTSIM_FRICTION", 0.06))
        self.dsp_ro_massdrag.setValue(d.get("RUNOUTSIM_MASS_DRAG", 45.0))
        self.dsp_ro_intvel.setValue(d.get("RUNOUTSIM_INT_VEL", 1.0))
        self.e_ro_fric_raster.setText(d.get("RUNOUTSIM_FRICTION_RASTER", ""))
        self.e_ro_src_prob.setText(d.get("RUNOUTSIM_P_SOURCE_PATH", ""))
        self.e_ro_conn_feature.setText(d.get("RUNOUTSIM_CONN_FEATURE_PATH", ""))

        self._wire_enable_logic()

    def _widgets_to_conf(self) -> dict:
        conf = {
        "SOURCE_INPUT_TYPE": self.cmb_source_type.currentText(),
        "DTM_ORIGINAL_PATH": self.e_dtm_orig.text().strip(),
        "DTM_FILLED_PATH": self.e_dtm_filled.text().strip() if self.btn_dtm_filled.isChecked() else "",
        "FDIR_PATH": self.e_fdir.text().strip() if self.btn_fdir.isChecked() else "",
        "SOURCE_SHAPEFILE_PATH": self.e_source_shp.text().strip(),
        "SOURCE_RASTER_PATH": self.e_source_raster.text().strip() if self.btn_source_raster.isChecked() else "",
        "SHAPEFILE_ELEV_FIELD": self.e_shape_elev.text().strip(),
        "PQLIM_REF_PATH": self.e_pqlim.text().strip() if self.btn_pqlim.isChecked() else "",
        "OUTPUT_DIR": self.e_outdir.text().strip(),
        "RESAMPLE_DTM": self.btn_resample.isChecked(),
        "TARGET_RESOLUTION": self.spn_target_res.value(),
        "AGGREGATION_METHOD": self.cmb_agg.currentText(),
        "SNAP_TRIGGERS": self.btn_snap.isChecked(),
        "SNAP_RADIUS": self.spn_snap_radius.value(),
        "ADD_ELEVATION_METERS": float(self.dsp_snap_height.value()),
        "ENABLE_PARALLEL_PROCESSING": self.btn_parallel.isChecked(),
        "NUM_WORKERS": self.spn_workers.value(),
        "POINTS_PER_WORKER": self.spn_ppw.value(),
        "DO_PIT_FILLING": self.btn_pit.isChecked(),
        "USE_WHITEBOX_FILLING": False,
        "CALCULATE_FLOW_DIRECTION": self.btn_calc_fdir.isChecked(),
        "USE_WHITEBOX_FDIR": False,
        "MAX_SLOPE_DEGREES": self.spn_maxslope.value(),
        "H_L_THRESHOLD": float(self.dsp_hl.value()),
        "FILL_HL_HOLES": self.btn_fill_hl_holes.isChecked(),
        "USE_DIRECTION_AWARE_UPHILL": self.btn_dir_uphill.isChecked(),
        "USE_DIRECT_DISTANCE_FOR_HL": self.btn_direct_hl.isChecked(),
        "HRMA_FROM_THRESH_LI": self.spn_hrma_from.value(),
        "HRMA_TO_THRESH_LI": self.spn_hrma_to.value(),
        "ZERO_FACTOR": float(self.dsp_zero.value()),
        "CUT_ANGLE": self.spn_cut.value(),
        "SLOPE": float(self.dsp_slope.value()),
        "ENABLE_MSF_PRUNING": self.btn_msf_pruning.isChecked(),
        "MSF_PRUNING_THRESHOLD": float(self.dsp_msf_pruning_threshold.value()),
        "SAVE_INTERMEDIATE_OUTPUTS": self.btn_save_inter.isChecked(),
        "COMPRESS_OUTPUTS": self.btn_compress.isChecked(),
        "SAVE_HL_RASTER": self.btn_save_hl.isChecked(),
        "SAVE_LI_RASTER": self.btn_save_li.isChecked(),
        "SAVE_LI_BACKLINK": self.btn_save_li_bl.isChecked(),
        "SAVE_FRI_RASTER": self.btn_save_fri.isChecked(),
        "SAVE_FRI_BACKLINK": self.btn_save_fri_bl.isChecked(),
        "PQLIM_FILENAME": self.e_pqlim_filename.text().strip(),
        "HL_FILENAME": self.e_hl_filename.text().strip(),
        "LI_FILENAME": self.e_li_filename.text().strip(),
        "LI_BACKLINK_FILENAME": self.e_li_bl_filename.text().strip(),
        "FRI_FILENAME": self.e_fri_filename.text().strip(),
        "FRI_BACKLINK_FILENAME": self.e_fri_bl_filename.text().strip(),
        "SHOW_MAP_PREVIEW": self.btn_show_preview.isChecked(),
        "RUN_MSF": self.btn_run_msf.isChecked(),
        "RUN_RUNOUTSIM": self.btn_run_runoutsim.isChecked(),
        "RUNOUTSIM_E_DIV": float(self.spn_ro_ediv.value()),
        "RUNOUTSIM_PERSISTENCE": float(self.spn_ro_persist.value()),
        "RUNOUTSIM_SLOPE_THRESH": float(self.spn_ro_slopethresh.value()),
        "RUNOUTSIM_WALKS": int(self.spn_ro_walks.value()),
        "RUNOUTSIM_FRICTION": float(self.dsp_ro_friction.value()),
        "RUNOUTSIM_MASS_DRAG": float(self.dsp_ro_massdrag.value()),
        "RUNOUTSIM_INT_VEL": float(self.dsp_ro_intvel.value()),
        "RUNOUTSIM_FRICTION_RASTER": self.e_ro_fric_raster.text().strip(),
        "RUNOUTSIM_P_SOURCE_PATH": self.e_ro_src_prob.text().strip(),
        "RUNOUTSIM_CONN_FEATURE_PATH": self.e_ro_conn_feature.text().strip(),
        }
        return conf

    def _apply_conf_and_validate(self, conf: dict) -> bool:
        if not conf.get("OUTPUT_DIR"):
            QMessageBox.warning(self, "Missing", "Please set OUTPUT_DIR.")
            return False
        os.makedirs(conf["OUTPUT_DIR"], exist_ok=True)
        apply_config_to_core(conf)
        return True

    def on_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load JSON config", "", "JSON (*.json)")
        if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            apply_config_to_core(data);
            self._load_defaults();
            self._log(f"Loaded configuration: {path}\n");
            self.tabs.setCurrentIndex(self.tabs.count() - 1)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load config:\n{e}")

    def on_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save JSON config", "msf_config.json", "JSON (*.json)")
        if not path: return
        try:
            data = self._widgets_to_conf()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._log(f"Saved configuration: {path}\n");
            self.tabs.setCurrentIndex(self.tabs.count() - 1)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save config:\n{e}")

    def on_run(self):
        if self._thread is not None and self._thread.is_alive():
            QMessageBox.information(self, "Running", "A run is already in progress.");
            return

        # Auto-save current config to msf_config.json on run
        try:
            current_conf = self._widgets_to_conf()
            with open("msf_config.json", "w", encoding="utf-8") as f:
                json.dump(current_conf, f, indent=2)
        except Exception as e:
            print(f"[Debug] Failed to auto-save msf_config.json: {e}")

        if self.btn_clear_log.isChecked():
            self.console.clear();
            self._log_lines.clear()

            # Clear worker log UI and log files on disk
        self.worker_console.clear()
        self._worker_log_positions = {}
        conf = self._widgets_to_conf()
        output_dir = conf.get("OUTPUT_DIR", "")
        if output_dir and os.path.exists(output_dir):
            import glob
            for f in glob.glob(os.path.join(output_dir, "worker_*.log")):
                try:
                    os.remove(f)
                except:
                    pass
        if not conf.get("RUN_MSF", True) and not conf.get("RUN_RUNOUTSIM", False):
            QMessageBox.warning(self, "Validation Error", "Please enable at least one model (MSF or runoutSIM) to run.")
            return
        self._saw_completed = False
        self._forced_restore = None
        if not conf.get("ENABLE_PARALLEL_PROCESSING", True):
            self._forced_restore = {"ENABLE_PARALLEL_PROCESSING": False, "NUM_WORKERS": conf.get("NUM_WORKERS", 1)}
            conf["ENABLE_PARALLEL_PROCESSING"] = True
            conf["NUM_WORKERS"] = 1
            self._log(
            "[Compatibility] Using parallel path with NUM_WORKERS=1 (sequential-safe) because non-parallel path is unreliable in this environment.\n")
        if not self._apply_conf_and_validate(conf): return
        self._log(f"[{time.strftime('%H:%M:%S')}] Run started\n");
        self._set_status("Running...");
        self.progress.setValue(0)
        apply_config_to_core(conf)
        self._old_out, self._old_err = sys.stdout, sys.stderr
        self._stream = EmittingStream();
        self._stream.text_written.connect(self._on_stream_text)
        sys.stdout = sys.stderr = self._stream
        self.btn_run.setEnabled(False);
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        self._thread = threading.Thread(target=self._run_core, daemon=True)
        self._thread.start()

    def _run_core(self):
        self._run_success = False
        try:
            core.main()
            self._run_success = True
        except Exception as e:
            print(f"\n❌ ERROR: {e}\n")
        finally:
            self.run_finished.emit(self._run_success)

    def _on_run_finished(self, success: bool):
        sys.stdout = self._old_out or sys.__stdout__
        sys.stderr = self._old_err or sys.__stderr__
        self._old_out = self._old_err = None
        if self._forced_restore is not None:
            for k, v in self._forced_restore.items():
                setattr(core.Config, k, v)
            self._forced_restore = None
        self._set_status("Completed")
        self.progress.setValue(100)
        self.btn_run.setEnabled(True)
        self._log(f"[{time.strftime('%H:%M:%S')}] Run finished\n")
        self._log(f"  [Debug] success={success}, show_preview_checked={self.btn_show_preview.isChecked()}\n")
        print(f"[Debug Terminal] success={success}, show_preview_checked={self.btn_show_preview.isChecked()}")

        # Final flush and cleanup of worker logs
        self._poll_flush()
        output_dir = getattr(core.Config, 'OUTPUT_DIR', '')
        if output_dir and os.path.exists(output_dir):
            import glob
            for f in glob.glob(os.path.join(output_dir, "worker_*.log")):
                try:
                    os.remove(f)
                except:
                    pass

        if success and self.btn_show_preview.isChecked():
            self._show_map_preview()

    def _on_stream_text(self, text: str):
        self._log_buffer.append(text)
        if "WORKFLOW COMPLETED" in text.upper():
            self._saw_completed = True
            if self._thread is not None and not self._thread.is_alive():
                self._set_status("Completed");
                self.progress.setValue(100);
                self.btn_run.setEnabled(True)
        self._parse_and_update_progress(text)

    def _log(self, text: str):
        if not text: return
        self.console.moveCursor(QTextCursor.End);
        self.console.insertPlainText(text);
        self.console.moveCursor(QTextCursor.End)

    def _append_log_cache(self, text: str):
        lines = text.splitlines()
        for L in lines:
            self._log_lines.append(L)
        if len(self._log_lines) > 3000:
            self._log_lines = self._log_lines[-3000:]

    def _parse_and_update_progress(self, text: str):
        m = re.search(r"(\d{1,3})\s*%", text)
        if m:
            val = max(0, min(100, int(m.group(1))))
            self.progress.setValue(val);
            return
        m2 = re.search(r"(\d{1,6})\s*/\s*(\d{1,6})", text)
        if m2:
            a = int(m2.group(1));
            b = int(m2.group(2))
            if b > 0: self.progress.setValue(max(0, min(100, int(round(a * 100.0 / b))))); return
        if re.search(r"processed|processing|cells|points", text, re.I):
            cur = self.progress.value();
            self.progress.setValue(min(99, cur + 1));
            return

    def _poll_flush(self):
    # 1. Flush the textual log buffer to the GUI
        if self._log_buffer:
        # Join all buffered lines into one big string
            combined_text = "".join(self._log_buffer)
            self._log_lines.append(combined_text)  # Update cache

            # Write to GUI Console in one go
            self.console.moveCursor(QTextCursor.End)
            self.console.insertPlainText(combined_text)
            self.console.moveCursor(QTextCursor.End)

            # Update Progress Bar based on the combined text
            self._parse_and_update_progress(combined_text)

            # Clear the buffer
            self._log_buffer.clear()

            # 2. Read from worker logs in real-time
        output_dir = getattr(core.Config, 'OUTPUT_DIR', '')
        if output_dir and os.path.exists(output_dir):
            import glob
            log_files = glob.glob(os.path.join(output_dir, "worker_*.log"))
            new_worker_text = ""
            for lf in log_files:
                filename = os.path.basename(lf)
                try:
                    size = os.path.getsize(lf)
                    last_pos = self._worker_log_positions.get(filename, 0)
                    if size > last_pos:
                        with open(lf, 'r', encoding='utf-8', errors='replace') as f:
                            f.seek(last_pos)
                            text = f.read()
                        self._worker_log_positions[filename] = size

                        worker_pid = filename.replace("worker_", "").replace(".log", "")
                        for line in text.splitlines():
                            if line.strip():
                                new_worker_text += f"[Worker {worker_pid}] {line}\n"
                except:
                    pass
            if new_worker_text:
                self.worker_console.moveCursor(QTextCursor.End)
                self.worker_console.insertPlainText(new_worker_text)
                self.worker_console.moveCursor(QTextCursor.End)

                # 3. Flush Python system buffers
        try:
            if hasattr(sys.stdout, 'flush'): sys.stdout.flush()
            if hasattr(sys.stderr, 'flush'): sys.stderr.flush()
        except Exception:
            pass

            # 3. Check for thread completion
        if self._saw_completed and (self._thread is None or not self._thread.is_alive()):
            self._set_status("Completed")
            self.progress.setValue(100)
            self.btn_run.setEnabled(True)

    def _set_status(self, text: str):
        color = "#8FAADC"
        if text.startswith("Ready"): color = "#9AA5B1"
        if text.startswith("Running"): color = "#00B3FF"
        if text.startswith("Completed"): color = "#6CDB7A"
        if text.startswith("Error"): color = "#FF6B6B"
        self.status_bar.setText(text);
        self.status_bar.setStyleSheet(f"font-weight:800;color:{color};")

    def _create_map_sheet(self, dtm_arr, dtm_nodata, cellsize_x, cellsize_y, pq_path, title_str, scale_factor, dtm_filled, hillshade, dtm_valid_mask, norm_dtm, shading, stops, colors_stop, model_type="msf"):
        """Helper to create a single map sheet image overlaying hillshade, DTM colors, and PQ_LIM colors."""
        from PyQt5.QtGui import QColor, QImage, QPainter, QBrush, QPen, QPolygonF
        from PyQt5.QtCore import Qt, QPointF, QRectF, QRect

        with rasterio.open(pq_path) as src:
            pq_arr = src.read(1).astype(np.float32)
            pq_nodata = src.nodata

        height, width = pq_arr.shape

        # Get breaks and active thresholds based on model type
        if model_type == "msf":
            min_val = 1.1
            max_val = 2.0
            colors = [
            [255, 237, 160],  # Class 1: Very Low (Light Yellow)
            [254, 178, 76],   # Class 2: Low (Yellow-Orange)
            [253, 141, 60],   # Class 3: Moderate (Orange)
            [240, 59, 32],    # Class 4: High (Orange-Red)
            [189, 0, 38]      # Class 5: Very High (Dark Red)
            ]
        else:
            min_val = 0.01  # filter out 1-walk noise (e.g. less than 1% probability)
            max_val = 1.0
            colors = [
            [255, 237, 160],  # Class 1: Very Low (Light Yellow)
            [254, 178, 76],   # Class 2: Low (Yellow-Orange)
            [253, 141, 60],   # Class 3: Moderate (Orange)
            [240, 59, 32],    # Class 4: High (Orange-Red)
            [189, 0, 38]      # Class 5: Very High (Dark Red)
            ]

        pq_valid_data = pq_arr[(pq_arr != pq_nodata) & (pq_arr >= min_val)]
        if model_type == "msf":
            if len(pq_valid_data) > 0:
                breaks = np.percentile(pq_valid_data, [35, 60, 80, 92])
            else:
                breaks = [1.30, 1.50, 1.65, 1.78]
        else:
            breaks = self._get_natural_breaks(pq_valid_data, 5, min_val=min_val, max_val=max_val)
        b1, b2, b3, b4 = breaks

        valid_pq = (pq_arr != pq_nodata) & (pq_arr >= min_val)
        masks = [
        valid_pq & (pq_arr <= b1),
        valid_pq & (pq_arr > b1) & (pq_arr <= b2),
        valid_pq & (pq_arr > b2) & (pq_arr <= b3),
        valid_pq & (pq_arr > b3) & (pq_arr <= b4),
        valid_pq & (pq_arr > b4)
        ]

        dtm_rgb = np.zeros((height, width, 3), dtype=np.float32)
        for i in range(len(stops) - 1):
            s0, s1 = stops[i], stops[i+1]
            c0, c1 = colors_stop[i], colors_stop[i+1]
            mask = (norm_dtm >= s0) & (norm_dtm <= s1)
            if np.any(mask):
                t = (norm_dtm[mask] - s0) / (s1 - s0)
                t_expanded = t[:, np.newaxis]
                dtm_rgb[mask] = c0 + t_expanded * (c1 - c0)

        dtm_rgb = dtm_rgb * 0.5 + 200.0 * 0.5
        img_rgb = np.zeros((height, width, 3), dtype=np.uint8)
        for channel in range(3):
            img_rgb[:, :, channel] = np.clip(dtm_rgb[:, :, channel] * shading, 0, 255).astype(np.uint8)

        pq_shading = 0.5 + 0.5 * (hillshade.astype(np.float32) / 255.0)
        alpha = 0.80  # 80% opaque, 20% transparent as requested
        for idx, mask in enumerate(masks):
            if np.any(mask):
                c = colors[idx]
                for channel in range(3):
                    sim_color = c[channel] * pq_shading
                    bg_color = img_rgb[:, :, channel].astype(np.float32)
                    blended = alpha * sim_color + (1.0 - alpha) * bg_color
                    img_rgb[:, :, channel] = np.where(
                    mask,
                    np.clip(blended, 0, 255).astype(np.uint8),
                    img_rgb[:, :, channel]
                    )

        dtm_nodata_mask = (dtm_arr == dtm_nodata) | np.isnan(dtm_arr)
        bg_color = [24, 27, 32]
        for channel in range(3):
            img_rgb[:, :, channel] = np.where(
            dtm_nodata_mask,
            bg_color[channel],
            img_rgb[:, :, channel]
            )

        bytes_per_line = 3 * width
        map_img = QImage(img_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888).copy()

        new_map_w = int(width * scale_factor)
        new_map_h = int(height * scale_factor)
        map_img_scaled = map_img.scaled(new_map_w, new_map_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Calculate graphical UI scale factor for drawing overlays (north arrow, scale bar, titles)
        ui_scale = (max(new_map_w, new_map_h) / 1600.0) * 1.4

        # Add bottom padding for simulation parameters
        param_padding = int(80 * ui_scale)
        total_h = new_map_h + param_padding

        sheet_img = QImage(new_map_w, total_h, QImage.Format_RGB888)
        sheet_img.fill(QColor(24, 27, 32))

        painter = QPainter(sheet_img)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawImage(0, 0, map_img_scaled)

        # Source point markers
        src_pixels = getattr(core.Config, "SOURCE_PIXELS", [])
        if len(src_pixels) > 0:
            brush = QBrush(QColor(255, 0, 255))
            pen = QPen(QColor(0, 0, 0), max(1.5, 2.0 * ui_scale))
            painter.setBrush(brush)
            painter.setPen(pen)
            r = int(max(6 * ui_scale, max(new_map_w, new_map_h) / 200))
            for row, col in src_pixels:
                draw_col = int(col * scale_factor)
                draw_row = int(row * scale_factor)
                painter.drawEllipse(draw_col - r, draw_row - r, 2 * r, 2 * r)

        # North Arrow
        arrow_w = int(max(36 * ui_scale, new_map_w * 0.045))
        arrow_h = int(arrow_w * 1.5)
        margin_x = int(40 * ui_scale)
        margin_y = int(80 * ui_scale)
        center_x = new_map_w - margin_x - arrow_w // 2
        center_y = margin_y + arrow_h // 2

        painter.setBrush(QBrush(QColor(0, 0, 0, 140)))
        painter.setPen(QPen(QColor(255, 255, 255, 180), max(1.5, 2.0 * ui_scale)))
        circle_r = int(arrow_h * 0.7)
        painter.drawEllipse(center_x - circle_r, center_y - circle_r + 5, 2 * circle_r, 2 * circle_r)

        left_poly = QPolygonF([
        QPointF(center_x, center_y - arrow_h // 2),
        QPointF(center_x - arrow_w // 2, center_y + arrow_h // 2),
        QPointF(center_x, center_y + arrow_h // 4),
        ])
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.drawPolygon(left_poly)

        right_poly = QPolygonF([
        QPointF(center_x, center_y - arrow_h // 2),
        QPointF(center_x + arrow_w // 2, center_y + arrow_h // 2),
        QPointF(center_x, center_y + arrow_h // 4),
        ])
        painter.setBrush(QBrush(QColor(80, 80, 80)))
        painter.drawPolygon(right_poly)

        # Draw North Letter "N" (doubled size, positioned completely outside the circle to avoid interception)
        font = painter.font()
        font.setBold(True)
        font.setPointSize(int(24 * ui_scale))
        painter.setFont(font)
        painter.setPen(QPen(QColor(255, 255, 255)))
        font_metrics = painter.fontMetrics()
        n_w = font_metrics.horizontalAdvance("N")
        painter.drawText(int(center_x - n_w // 2), int(center_y - circle_r - int(10 * ui_scale)), "N")

        # Scale Bar
        candidates = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0]
        total_width_m = width * cellsize_x
        target_m = total_width_m / 4.0
        target_km = target_m / 1000.0
        best_cand = min(candidates, key=lambda x: abs(x - target_km))
        scale_km = best_cand
        scale_m = scale_km * 1000.0
        scale_pixels = (scale_m / cellsize_x) * scale_factor

        bar_h = int(max(8 * ui_scale, new_map_h * 0.015))
        start_x = margin_x
        start_y = new_map_h - margin_y - bar_h

        # Expanded background rect for larger scale fonts (raddoppiato)
        bg_w = int(scale_pixels + 120 * ui_scale)
        bg_h = int(bar_h + 90 * ui_scale)
        painter.setBrush(QBrush(QColor(20, 22, 26, 240)))
        painter.setPen(QPen(QColor(130, 135, 145), max(1.5, 2.5 * ui_scale)))
        painter.drawRoundedRect(start_x - int(40 * ui_scale), start_y - int(65 * ui_scale), bg_w, bg_h, int(6 * ui_scale), int(6 * ui_scale))

        mid_x = start_x + scale_pixels / 2
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(QColor(0, 0, 0), max(1.0, 1.5 * ui_scale)))
        painter.drawRect(QRectF(start_x, start_y, scale_pixels / 2, bar_h))

        painter.setBrush(QBrush(QColor(0, 0, 0)))
        painter.drawRect(QRectF(mid_x, start_y, scale_pixels / 2, bar_h))

        font = painter.font()
        font.setBold(True)
        font.setPointSize(int(18 * ui_scale))
        painter.setFont(font)
        painter.setPen(QPen(QColor(235, 238, 243)))

        label_y = start_y - int(10 * ui_scale)
        painter.drawText(QRectF(start_x - int(40 * ui_scale), label_y - int(35 * ui_scale), int(80 * ui_scale), int(35 * ui_scale)), Qt.AlignCenter, "0")
        mid_val = scale_km / 2.0
        mid_str = f"{mid_val:.2f}".rstrip('0').rstrip('.')
        painter.drawText(QRectF(mid_x - int(40 * ui_scale), label_y - int(35 * ui_scale), int(80 * ui_scale), int(35 * ui_scale)), Qt.AlignCenter, mid_str)
        scale_str = f"{scale_km:.2f}".rstrip('0').rstrip('.') + " km"
        painter.drawText(QRectF(start_x + scale_pixels - int(70 * ui_scale), label_y - int(35 * ui_scale), int(140 * ui_scale), int(35 * ui_scale)), Qt.AlignCenter, scale_str)

        # Title Banner (raddoppiato)
        painter.setBrush(QBrush(QColor(24, 27, 32, 220)))
        painter.setPen(QPen(QColor(0, 179, 255), max(1.5, 2.0 * ui_scale)))
        painter.drawRoundedRect(int(15 * ui_scale), int(15 * ui_scale), int(500 * ui_scale), int(60 * ui_scale), int(10 * ui_scale), int(10 * ui_scale))

        font = painter.font()
        font.setBold(True)
        font.setPointSize(int(20 * ui_scale))
        painter.setFont(font)
        painter.setPen(QPen(QColor(235, 238, 243)))
        painter.drawText(QRect(int(25 * ui_scale), int(15 * ui_scale), int(480 * ui_scale), int(60 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, title_str)

        # Draw Simulation Parameters at the bottom black strip
        font = painter.font()
        font.setBold(False)
        font.setPointSize(int(12 * ui_scale))
        painter.setFont(font)
        painter.setPen(QPen(QColor(235, 238, 243)))

        # Determine the text to write based on model and title
        lines = []
        is_pruned = "pruned" in title_str.lower() or "pruned" in model_type.lower()
        if model_type == "msf":
            cut_val = getattr(core.Config, "CUT_ANGLE", 45)
            slope_val = getattr(core.Config, "SLOPE", 0.011111)
            hl_val = getattr(core.Config, "H_L_THRESHOLD", 0.25)
            if is_pruned:
                prun_val = getattr(core.Config, "MSF_PRUNING_THRESHOLD", 1.5)
                lines.append(f"MSF Pruned: Cut = {cut_val}°, Slope = {slope_val:.5f}")
                lines.append(f"H/L = {hl_val:.2f}, Prun = {prun_val:.1f}")
            else:
                lines.append(f"MSF Standard: Cut = {cut_val}°, Slope = {slope_val:.5f}")
                lines.append(f"H/L = {hl_val:.2f}")
        else:
            walks = getattr(core.Config, "RUNOUTSIM_WALKS", 1000)
            div = getattr(core.Config, "RUNOUTSIM_E_DIV", 2.1)
            fric = getattr(core.Config, "RUNOUTSIM_FRICTION", 0.06)
            drag = getattr(core.Config, "RUNOUTSIM_MASS_DRAG", 45.0)
            pers = getattr(core.Config, "RUNOUTSIM_PERSISTENCE", 1.6)
            lines.append(f"runoutSIM: Walks = {walks}, Div = {div:.1f}, Fric = {fric:.3f}")
            lines.append(f"Mass Drag = {drag:.1f}, Pers = {pers:.1f}")

        # Draw the lines of text centered in the padding area
        text_y = new_map_h + int(15 * ui_scale)
        for line_str in lines:
            painter.drawText(QRect(int(15 * ui_scale), text_y, new_map_w - int(30 * ui_scale), int(25 * ui_scale)), Qt.AlignCenter | Qt.AlignVCenter, line_str)
            text_y += int(25 * ui_scale)

        painter.end()
        return sheet_img, breaks, colors

    def _show_map_preview(self):
        try:
            cfg = core.Config
            output_dir = cfg.OUTPUT_DIR
            run_msf = getattr(cfg, "RUN_MSF", True)
            run_runoutsim = getattr(cfg, "RUN_RUNOUTSIM", False)

            # Determine paths to PQ_LIM rasters
            msf_pq_lim_path = None
            if run_msf:
                if getattr(cfg, "PQLIM_FILENAME", ""):
                    msf_filename = cfg.PQLIM_FILENAME
                else:
                    extra = getattr(cfg, "PQLIM_CUSTOM_SUFFIX", "")
                    suffix = f"_msf{extra}" if run_runoutsim else extra
                    if cfg.RESAMPLE_DTM:
                        msf_filename = f"pq_lim_{cfg.TARGET_RESOLUTION}m{suffix}.tif"
                    else:
                        msf_filename = f"pq_lim{suffix}.tif"
                msf_pq_lim_path = os.path.join(output_dir, msf_filename)

            ro_pq_lim_path = None
            if run_runoutsim:
                if getattr(cfg, "RUNOUTSIM_PQLIM_FILENAME", ""):
                    ro_filename = cfg.RUNOUTSIM_PQLIM_FILENAME
                else:
                    extra = getattr(cfg, "PQLIM_CUSTOM_SUFFIX", "")
                    suffix = f"_runoutsim{extra}" if run_msf else f"_runoutsim{extra}" if extra else "_runoutsim"
                    if cfg.RESAMPLE_DTM:
                        ro_filename = f"pq_lim_{cfg.TARGET_RESOLUTION}m{suffix}.tif"
                    else:
                        ro_filename = f"pq_lim{suffix}.tif"
                ro_pq_lim_path = os.path.join(output_dir, ro_filename)

                # Determine DTM path
            if cfg.RESAMPLE_DTM:
                dtm_path = os.path.join(output_dir, f"dtm_resampled_{cfg.TARGET_RESOLUTION}m.tif")
            else:
                dtm_path = cfg.DTM_FILLED_PATH if (cfg.DTM_FILLED_PATH and os.path.exists(cfg.DTM_FILLED_PATH)) else cfg.DTM_ORIGINAL_PATH

            if not os.path.exists(dtm_path):
                self._log(f"⚠ Warning: DTM file not found at {dtm_path}\n")
                return

            self._log("  Reading DTM for map preview...\n")
            with rasterio.open(dtm_path) as src:
                dtm_arr = src.read(1).astype(np.float32)
                dtm_nodata = src.nodata
                cellsize_x, cellsize_y = src.res

            height, width = dtm_arr.shape

            # Calculate Multidirectional Hillshade once (Swiss-style shading)
            dtm_valid_mask = (dtm_arr != dtm_nodata) & (~np.isnan(dtm_arr))
            dtm_filled = dtm_arr.copy()
            if not np.all(dtm_valid_mask):
                mean_elev = np.mean(dtm_arr[dtm_valid_mask]) if np.any(dtm_valid_mask) else 0.0
                dtm_filled[~dtm_valid_mask] = mean_elev

            dy, dx = np.gradient(dtm_filled, cellsize_y, cellsize_x)
            slope = np.arctan(np.sqrt(dx**2 + dy**2))
            aspect = np.arctan2(dx, -dy)

            directions = [225.0, 270.0, 315.0, 360.0]
            weights = [0.25, 0.25, 0.375, 0.125]
            zenith_rad = np.radians(90.0 - 45.0)
            cos_zenith = np.cos(zenith_rad)
            sin_zenith = np.sin(zenith_rad)

            hillshade_accum = np.zeros_like(dtm_filled, dtype=np.float32)
            for az, w in zip(directions, weights):
                azimuth_rad = np.radians(360.0 - az + 90.0)
                hs = (cos_zenith * np.cos(slope) + 
                sin_zenith * np.sin(slope) * np.cos(azimuth_rad - aspect))
                hs = 255.0 * (hs + 1.0) / 2.0
                hillshade_accum += w * hs

            hillshade = np.clip(hillshade_accum, 0, 255).astype(np.uint8)

            # Map DTM Elevations (ArcGIS elevation color ramp stops)
            min_elev = np.min(dtm_filled[dtm_valid_mask]) if np.any(dtm_valid_mask) else 0.0
            max_elev = np.max(dtm_filled[dtm_valid_mask]) if np.any(dtm_valid_mask) else 1.0
            elev_range = max_elev - min_elev if max_elev > min_elev else 1.0

            norm_dtm = (dtm_filled - min_elev) / elev_range
            norm_dtm = np.clip(norm_dtm, 0.0, 1.0)

            stops = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
            colors_stop = np.array([
            [50, 130, 50],
            [140, 190, 90],
            [245, 225, 140],
            [205, 140, 70],
            [135, 75, 35],
            [245, 245, 245]
            ], dtype=np.float32)

            shading = 0.35 + 0.65 * (hillshade.astype(np.float32) / 255.0)

            # Scale factor for consistent preview sizes across resolutions
            target_max_dim = 2400.0
            scale_factor = target_max_dim / max(width, height)
            new_map_w = int(width * scale_factor)
            new_map_h = int(height * scale_factor)
            ui_scale = (target_max_dim / 1600.0) * 1.4

            # Color spectrum definition for classes
            msf_colors = [
            [0, 63, 255],    # Class 1: Blue
            [0, 220, 0],     # Class 2: Green
            [255, 220, 0],   # Class 3: Yellow
            [255, 127, 0],   # Class 4: Orange
            [255, 0, 0]      # Class 5: Red
            ]
            ro_colors = [
            [255, 237, 160],  # Class 1: Very Low (Light Yellow)
            [254, 178, 76],   # Class 2: Low (Yellow-Orange)
            [253, 141, 60],   # Class 3: Moderate (Orange)
            [240, 59, 32],    # Class 4: High (Orange-Red)
            [189, 0, 38]      # Class 5: Very High (Dark Red)
            ]

            # Generate sheet images
            msf_sheet = None
            msf_breaks = []
            if run_msf and msf_pq_lim_path and os.path.exists(msf_pq_lim_path):
                self._log("  Generating MSF map sheet...\n")
                msf_sheet, msf_breaks, _ = self._create_map_sheet(
                dtm_arr, dtm_nodata, cellsize_x, cellsize_y, msf_pq_lim_path, "MSF Standard Output",
                scale_factor, dtm_filled, hillshade, dtm_valid_mask, norm_dtm, shading, stops, colors_stop,
                model_type="msf"
                )

            pruned_sheet = None
            pruned_breaks = []
            msf_pruned_pq_lim_path = msf_pq_lim_path.replace(".tif", "_pruned.tif") if msf_pq_lim_path else None
            if run_msf and getattr(cfg, "ENABLE_MSF_PRUNING", False) and msf_pruned_pq_lim_path and os.path.exists(msf_pruned_pq_lim_path):
                self._log("  Generating Pruned MSF map sheet...\n")
                pruned_sheet, pruned_breaks, _ = self._create_map_sheet(
                dtm_arr, dtm_nodata, cellsize_x, cellsize_y, msf_pruned_pq_lim_path, "MSF Pruned Output",
                scale_factor, dtm_filled, hillshade, dtm_valid_mask, norm_dtm, shading, stops, colors_stop,
                model_type="msf"
                )

            ro_sheet = None
            ro_breaks = []
            if run_runoutsim and ro_pq_lim_path and os.path.exists(ro_pq_lim_path):
                self._log("  Generating runoutSIM map sheet...\n")
                ro_sheet, ro_breaks, _ = self._create_map_sheet(
                dtm_arr, dtm_nodata, cellsize_x, cellsize_y, ro_pq_lim_path, "runoutSIM Model Output",
                scale_factor, dtm_filled, hillshade, dtm_valid_mask, norm_dtm, shading, stops, colors_stop,
                model_type="runoutsim"
                )

            from PyQt5.QtCore import QPointF, QRectF, QRect
            from PyQt5.QtGui import QBrush, QPen, QPolygonF, QLinearGradient

            # Now build combined layout based on what was rendered
            if msf_sheet is not None and pruned_sheet is not None and ro_sheet is not None:
            # 3-Panel Layout
                new_height = max(msf_sheet.height(), int(850 * (target_max_dim / 1600.0)))
                legend_width = int(380 * ui_scale)
                q_img = QImage(new_map_w * 3 + legend_width + 10, new_height, QImage.Format_RGB888)
                q_img.fill(QColor(24, 27, 32))

                painter = QPainter(q_img)
                painter.setRenderHint(QPainter.Antialiasing)

                # Draw Standard MSF sheet
                painter.drawImage(0, 0, msf_sheet)

                # Divider 1
                painter.setPen(QPen(QColor(43, 49, 64), max(1.5, 2.0 * ui_scale)))
                painter.drawLine(new_map_w + 5, 0, new_map_w + 5, new_height)

                # Draw Pruned MSF sheet
                painter.drawImage(new_map_w + 10, 0, pruned_sheet)

                # Divider 2
                painter.drawLine(new_map_w * 2 + 15, 0, new_map_w * 2 + 15, new_height)

                # Draw runoutSIM sheet
                painter.drawImage(new_map_w * 2 + 20, 0, ro_sheet)

                # Divider 3 (legend)
                painter.drawLine(new_map_w * 3 + 20, 0, new_map_w * 3 + 20, new_height)

                legend_x = new_map_w * 3 + int(20 * ui_scale)

                # 1. MSF Standard Legend
                font = painter.font()
                font.setPointSize(int(15 * ui_scale))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QPen(QColor(0, 179, 255)))
                sec1_y = int(25 * ui_scale)
                painter.drawText(QRect(legend_x, sec1_y, legend_width - int(20 * ui_scale), int(30 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, "MSF Standard Prob.")

                font.setBold(False)
                font.setPointSize(int(12 * ui_scale))
                painter.setFont(font)
                msf_b1, msf_b2, msf_b3, msf_b4 = msf_breaks if len(msf_breaks) == 4 else [1.3, 1.5, 1.65, 1.78]
                msf_labels = [
                (ro_colors[4], f"> {msf_b4:.2f}"),
                (ro_colors[3], f"{msf_b3:.2f} - {msf_b4:.2f}"),
                (ro_colors[2], f"{msf_b2:.2f} - {msf_b3:.2f}"),
                (ro_colors[1], f"{msf_b1:.2f} - {msf_b2:.2f}"),
                (ro_colors[0], f"<= {msf_b1:.2f}")
                ]
                item_y = sec1_y + int(35 * ui_scale)
                rect_w, rect_h = int(28 * ui_scale), int(16 * ui_scale)
                for col_val, label_str in msf_labels:
                    painter.setBrush(QBrush(QColor(*col_val)))
                    painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
                    painter.drawRect(legend_x + 5, item_y, rect_w, rect_h)
                    painter.setPen(QPen(QColor(235, 238, 243)))
                    painter.drawText(QRect(legend_x + rect_w + int(15 * ui_scale), item_y - int(8 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(28 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, label_str)
                    item_y += int(26 * ui_scale)

                # 2. MSF Pruned Legend
                font.setBold(True)
                font.setPointSize(int(15 * ui_scale))
                painter.setFont(font)
                painter.setPen(QPen(QColor(0, 179, 255)))
                sec2_y = item_y + int(10 * ui_scale)
                painter.drawText(QRect(legend_x, sec2_y, legend_width - int(20 * ui_scale), int(30 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, "MSF Pruned Prob.")

                font.setBold(False)
                font.setPointSize(int(12 * ui_scale))
                painter.setFont(font)
                p_b1, p_b2, p_b3, p_b4 = pruned_breaks if len(pruned_breaks) == 4 else [1.3, 1.5, 1.65, 1.78]
                pruned_labels = [
                (ro_colors[4], f"> {p_b4:.2f}"),
                (ro_colors[3], f"{p_b3:.2f} - {p_b4:.2f}"),
                (ro_colors[2], f"{p_b2:.2f} - {p_b3:.2f}"),
                (ro_colors[1], f"{p_b1:.2f} - {p_b2:.2f}"),
                (ro_colors[0], f"<= {p_b1:.2f}")
                ]
                item_y = sec2_y + int(35 * ui_scale)
                for col_val, label_str in pruned_labels:
                    painter.setBrush(QBrush(QColor(*col_val)))
                    painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
                    painter.drawRect(legend_x + 5, item_y, rect_w, rect_h)
                    painter.setPen(QPen(QColor(235, 238, 243)))
                    painter.drawText(QRect(legend_x + rect_w + int(15 * ui_scale), item_y - int(8 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(28 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, label_str)
                    item_y += int(26 * ui_scale)

                # 3. runoutSIM Legend
                font.setBold(True)
                font.setPointSize(int(15 * ui_scale))
                painter.setFont(font)
                painter.setPen(QPen(QColor(0, 179, 255)))
                sec3_y = item_y + int(10 * ui_scale)
                painter.drawText(QRect(legend_x, sec3_y, legend_width - int(20 * ui_scale), int(30 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, "runoutSIM ECDF Prob.")

                font.setBold(False)
                font.setPointSize(int(12 * ui_scale))
                painter.setFont(font)
                ro_b1, ro_b2, ro_b3, ro_b4 = ro_breaks if len(ro_breaks) == 4 else [0.2, 0.4, 0.6, 0.8]
                ro_labels = [
                (ro_colors[4], f"> {ro_b4:.2f}"),
                (ro_colors[3], f"{ro_b3:.2f} - {ro_b4:.2f}"),
                (ro_colors[2], f"{ro_b2:.2f} - {ro_b3:.2f}"),
                (ro_colors[1], f"{ro_b1:.2f} - {ro_b2:.2f}"),
                (ro_colors[0], f"<= {ro_b1:.2f}")
                ]
                item_y = sec3_y + int(35 * ui_scale)
                for col_val, label_str in ro_labels:
                    painter.setBrush(QBrush(QColor(*col_val)))
                    painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
                    painter.drawRect(legend_x + 5, item_y, rect_w, rect_h)
                    painter.setPen(QPen(QColor(235, 238, 243)))
                    painter.drawText(QRect(legend_x + rect_w + int(15 * ui_scale), item_y - int(8 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(28 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, label_str)
                    item_y += int(26 * ui_scale)

                # 4. Triggering Points Circle
                item_y += int(10 * ui_scale)
                painter.setBrush(QBrush(QColor(255, 0, 255)))
                painter.setPen(QPen(QColor(0, 0, 0), max(1.0, 1.5 * ui_scale)))
                circle_r = int(8 * ui_scale)
                painter.drawEllipse(legend_x + 5 + rect_w // 2 - circle_r, item_y + rect_h // 2 - circle_r, 2 * circle_r, 2 * circle_r)
                painter.setPen(QPen(QColor(235, 238, 243)))
                painter.drawText(QRect(legend_x + rect_w + int(15 * ui_scale), item_y - int(8 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(28 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, "Triggering Points")

                # 5. DTM Elevation gradient
                item_y += int(40 * ui_scale)
                font.setBold(True)
                font.setPointSize(int(15 * ui_scale))
                painter.setFont(font)
                painter.setPen(QPen(QColor(0, 179, 255)))
                painter.drawText(QRect(legend_x, item_y, legend_width - int(20 * ui_scale), int(30 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, "Elevation [m]")

                grad_w, grad_h = int(28 * ui_scale), int(120 * ui_scale)
                grad_x = legend_x + 5
                grad_y = item_y + int(35 * ui_scale)
                gradient = QLinearGradient(grad_x, grad_y + grad_h, grad_x, grad_y)
                for s, c_val in zip(stops, colors_stop):
                    gradient.setColorAt(s, QColor(*c_val.astype(int)))
                painter.setBrush(QBrush(gradient))
                painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
                painter.drawRect(grad_x, grad_y, grad_w, grad_h)

                font.setBold(False)
                font.setPointSize(int(12 * ui_scale))
                painter.setFont(font)
                painter.setPen(QPen(QColor(235, 238, 243)))
                max_elev_int = int(round(max_elev))
                min_elev_int = int(round(min_elev))
                mid_elev_int = int(round(min_elev + elev_range / 2.0))
                painter.drawText(QRect(legend_x + rect_w + int(15 * ui_scale), grad_y - int(15 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(28 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, f"{max_elev_int}")
                painter.drawText(QRect(legend_x + rect_w + int(15 * ui_scale), grad_y + grad_h // 2 - int(15 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(20 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, f"{mid_elev_int}")
                painter.drawText(QRect(legend_x + rect_w + int(15 * ui_scale), grad_y + grad_h - int(15 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(20 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, f"{min_elev_int}")

                painter.end()
                pixmap = QPixmap.fromImage(q_img)
                breaks = msf_breaks
                colors = msf_colors

            elif len([s for s in [msf_sheet, pruned_sheet, ro_sheet] if s is not None]) == 2:
            # 2-Panel Layout
                sheet1, label1, breaks1, col1 = None, "", [], []
                sheet2, label2, breaks2, col2 = None, "", [], []

                if msf_sheet is not None:
                    sheet1, label1, breaks1, col1 = msf_sheet, "MSF Standard Prob.", msf_breaks, ro_colors
                if pruned_sheet is not None:
                    if sheet1 is None:
                        sheet1, label1, breaks1, col1 = pruned_sheet, "MSF Pruned Prob.", pruned_breaks, ro_colors
                    else:
                        sheet2, label2, breaks2, col2 = pruned_sheet, "MSF Pruned Prob.", pruned_breaks, ro_colors
                if ro_sheet is not None:
                    sheet2, label2, breaks2, col2 = ro_sheet, "runoutSIM ECDF Prob.", ro_breaks, ro_colors

                new_height = max(sheet1.height(), int(850 * (target_max_dim / 1600.0)))
                legend_width = int(370 * ui_scale)
                q_img = QImage(new_map_w * 2 + legend_width + 10, new_height, QImage.Format_RGB888)
                q_img.fill(QColor(24, 27, 32))

                painter = QPainter(q_img)
                painter.setRenderHint(QPainter.Antialiasing)

                # Draw Sheet 1
                painter.drawImage(0, 0, sheet1)

                # Divider between sheets
                painter.setPen(QPen(QColor(43, 49, 64), max(1.5, 2.0 * ui_scale)))
                painter.drawLine(new_map_w + 5, 0, new_map_w + 5, new_height)

                # Draw Sheet 2
                painter.drawImage(new_map_w + 10, 0, sheet2)

                # Divider between map and legend panel
                painter.drawLine(new_map_w * 2 + 10, 0, new_map_w * 2 + 10, new_height)

                legend_x = new_map_w * 2 + int(20 * ui_scale)

                # Draw Legend 1
                font = painter.font()
                font.setPointSize(int(17 * ui_scale))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QPen(QColor(0, 179, 255)))
                sec1_y = int(35 * ui_scale)
                painter.drawText(QRect(legend_x, sec1_y, legend_width - int(20 * ui_scale), int(35 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, label1)

                font.setBold(False)
                font.setPointSize(int(13 * ui_scale))
                painter.setFont(font)
                b1, b2, b3, b4 = breaks1 if len(breaks1) == 4 else [1.3, 1.5, 1.65, 1.78]
                labels1 = [
                (col1[4], f"> {b4:.3f}"),
                (col1[3], f"{b3:.3f} - {b4:.3f}"),
                (col1[2], f"{b2:.3f} - {b3:.3f}"),
                (col1[1], f"{b1:.3f} - {b2:.3f}"),
                (col1[0], f"<= {b1:.3f}")
                ]
                item_y = sec1_y + int(45 * ui_scale)
                rect_w, rect_h = int(32 * ui_scale), int(20 * ui_scale)
                for col_val, label_str in labels1:
                    painter.setBrush(QBrush(QColor(*col_val)))
                    painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
                    painter.drawRect(legend_x + 5, item_y, rect_w, rect_h)
                    painter.setPen(QPen(QColor(235, 238, 243)))
                    painter.drawText(QRect(legend_x + rect_w + int(18 * ui_scale), item_y - int(8 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(34 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, label_str)
                    item_y += int(35 * ui_scale)

                # Draw Legend 2
                item_y += int(15 * ui_scale)
                font.setBold(True)
                font.setPointSize(int(17 * ui_scale))
                painter.setFont(font)
                painter.setPen(QPen(QColor(0, 179, 255)))
                painter.drawText(QRect(legend_x, item_y, legend_width - int(20 * ui_scale), int(35 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, label2)

                font.setBold(False)
                font.setPointSize(int(13 * ui_scale))
                painter.setFont(font)
                b1_2, b2_2, b3_2, b4_2 = breaks2 if len(breaks2) == 4 else [0.2, 0.4, 0.6, 0.8]
                labels2 = [
                (col2[4], f"> {b4_2:.3f}"),
                (col2[3], f"{b3_2:.3f} - {b4_2:.3f}"),
                (col2[2], f"{b2_2:.3f} - {b3_2:.3f}"),
                (col2[1], f"{b1_2:.3f} - {b2_2:.3f}"),
                (col2[0], f"<= {b1_2:.3f}")
                ]
                item_y += int(45 * ui_scale)
                for col_val, label_str in labels2:
                    painter.setBrush(QBrush(QColor(*col_val)))
                    painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
                    painter.drawRect(legend_x + 5, item_y, rect_w, rect_h)
                    painter.setPen(QPen(QColor(235, 238, 243)))
                    painter.drawText(QRect(legend_x + rect_w + int(18 * ui_scale), item_y - int(8 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(34 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, label_str)
                    item_y += int(35 * ui_scale)

                # Triggering points circle
                item_y += int(15 * ui_scale)
                painter.setBrush(QBrush(QColor(255, 0, 255)))
                painter.setPen(QPen(QColor(0, 0, 0), max(1.5, 2.0 * ui_scale)))
                circle_r = int(8 * ui_scale)
                painter.drawEllipse(legend_x + 5 + rect_w // 2 - circle_r, item_y + rect_h // 2 - circle_r, 2 * circle_r, 2 * circle_r)
                painter.setPen(QPen(QColor(235, 238, 243)))
                painter.drawText(QRect(legend_x + rect_w + int(18 * ui_scale), item_y - int(8 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(34 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, "Triggering Points")

                # DTM Elevation gradient
                item_y += int(50 * ui_scale)
                font.setBold(True)
                font.setPointSize(int(17 * ui_scale))
                painter.setFont(font)
                painter.setPen(QPen(QColor(0, 179, 255)))
                painter.drawText(QRect(legend_x, item_y, legend_width - int(20 * ui_scale), int(35 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, "Elevation [m]")

                grad_w, grad_h = int(32 * ui_scale), int(160 * ui_scale)
                grad_x = legend_x + 5
                grad_y = item_y + int(45 * ui_scale)
                gradient = QLinearGradient(grad_x, grad_y + grad_h, grad_x, grad_y)
                for s, c_val in zip(stops, colors_stop):
                    gradient.setColorAt(s, QColor(*c_val.astype(int)))
                painter.setBrush(QBrush(gradient))
                painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
                painter.drawRect(grad_x, grad_y, grad_w, grad_h)

                font.setBold(False)
                font.setPointSize(int(13 * ui_scale))
                painter.setFont(font)
                painter.setPen(QPen(QColor(235, 238, 243)))
                max_elev_int = int(round(max_elev))
                min_elev_int = int(round(min_elev))
                mid_elev_int = int(round(min_elev + elev_range / 2.0))
                painter.drawText(QRect(legend_x + rect_w + int(18 * ui_scale), grad_y - int(15 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(30 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, f"{max_elev_int}")
                painter.drawText(QRect(legend_x + rect_w + int(18 * ui_scale), grad_y + grad_h // 2 - int(15 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(20 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, f"{mid_elev_int}")
                painter.drawText(QRect(legend_x + rect_w + int(18 * ui_scale), grad_y + grad_h - int(15 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(20 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, f"{min_elev_int}")

                painter.end()
                pixmap = QPixmap.fromImage(q_img)
                breaks = breaks1
                colors = col1

            else:
            # 1-Panel Layout
                active_sheet = msf_sheet if msf_sheet is not None else (pruned_sheet if pruned_sheet is not None else ro_sheet)
                active_breaks = msf_breaks if msf_sheet is not None else (pruned_breaks if pruned_sheet is not None else ro_breaks)
                title_lbl = "MSF Standard" if msf_sheet is not None else ("MSF Pruned" if pruned_sheet is not None else "runoutSIM ECDF")

                if active_sheet is None:
                    self._log("WARNING Warning: No rendered map sheets found. Cannot show preview.\n")
                    return

                new_height = max(active_sheet.height(), int(620 * (target_max_dim / 1600.0)))
                legend_width = int(360 * ui_scale)
                q_img = QImage(new_map_w + legend_width, new_height, QImage.Format_RGB888)
                q_img.fill(QColor(24, 27, 32))

                painter = QPainter(q_img)
                painter.setRenderHint(QPainter.Antialiasing)

                painter.drawImage(0, 0, active_sheet)

                painter.setPen(QPen(QColor(43, 49, 64), max(1.5, 2.0 * ui_scale)))
                painter.drawLine(new_map_w, 0, new_map_w, new_height)

                legend_x = new_map_w + int(20 * ui_scale)
                font = painter.font()
                font.setPointSize(int(18 * ui_scale))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QPen(QColor(0, 179, 255)))

                sec1_y = int(35 * ui_scale)
                painter.drawText(QRect(legend_x, sec1_y, legend_width - int(20 * ui_scale), int(35 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, title_lbl)

                font.setBold(False)
                font.setPointSize(int(15 * ui_scale))
                painter.setFont(font)

                b1, b2, b3, b4 = active_breaks if len(active_breaks) == 4 else [0.2, 0.4, 0.6, 0.8]
                class_labels = [
                (ro_colors[4], f"> {b4:.3f}"),
                (ro_colors[3], f"{b3:.3f} - {b4:.3f}"),
                (ro_colors[2], f"{b2:.3f} - {b3:.3f}"),
                (ro_colors[1], f"{b1:.3f} - {b2:.3f}"),
                (ro_colors[0], f"<= {b1:.3f}")
                ]

                item_y = sec1_y + int(45 * ui_scale)
                rect_w, rect_h = int(32 * ui_scale), int(22 * ui_scale)
                for col_val, label_str in class_labels:
                    painter.setBrush(QBrush(QColor(*col_val)))
                    painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
                    painter.drawRect(legend_x + 5, item_y, rect_w, rect_h)

                    painter.setPen(QPen(QColor(235, 238, 243)))
                    painter.drawText(QRect(legend_x + rect_w + int(18 * ui_scale), item_y - int(8 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(34 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, label_str)
                    item_y += int(40 * ui_scale)

                painter.setBrush(QBrush(QColor(255, 0, 255)))
                painter.setPen(QPen(QColor(0, 0, 0), max(1.5, 2.0 * ui_scale)))
                circle_r = int(9 * ui_scale)
                painter.drawEllipse(legend_x + 5 + rect_w // 2 - circle_r, item_y + rect_h // 2 - circle_r, 2 * circle_r, 2 * circle_r)

                painter.setPen(QPen(QColor(235, 238, 243)))
                painter.drawText(QRect(legend_x + rect_w + int(18 * ui_scale), item_y - int(8 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(34 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, "Triggering Points")
                item_y += int(70 * ui_scale)

                font.setPointSize(int(18 * ui_scale))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QPen(QColor(0, 179, 255)))
                painter.drawText(QRect(legend_x, item_y, legend_width - int(20 * ui_scale), int(35 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, "Elevation [m]")

                grad_w, grad_h = int(32 * ui_scale), int(160 * ui_scale)
                grad_x = legend_x + 5
                grad_y = item_y + int(45 * ui_scale)

                gradient = QLinearGradient(grad_x, grad_y + grad_h, grad_x, grad_y)
                for s, c_val in zip(stops, colors_stop):
                    gradient.setColorAt(s, QColor(*c_val.astype(int)))

                painter.setBrush(QBrush(gradient))
                painter.setPen(QPen(QColor(255, 255, 255, 100), 1))
                painter.drawRect(grad_x, grad_y, grad_w, grad_h)

                font.setBold(False)
                font.setPointSize(int(15 * ui_scale))
                painter.setFont(font)
                painter.setPen(QPen(QColor(235, 238, 243)))

                max_elev_int = int(round(max_elev))
                min_elev_int = int(round(min_elev))
                mid_elev_int = int(round(min_elev + elev_range / 2.0))

                painter.drawText(QRect(legend_x + rect_w + int(18 * ui_scale), grad_y - int(15 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(30 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, f"{max_elev_int}")
                painter.drawText(QRect(legend_x + rect_w + int(18 * ui_scale), grad_y + grad_h // 2 - int(15 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(20 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, f"{mid_elev_int}")
                painter.drawText(QRect(legend_x + rect_w + int(18 * ui_scale), grad_y + grad_h - int(15 * ui_scale), legend_width - rect_w - int(20 * ui_scale), int(20 * ui_scale)), Qt.AlignLeft | Qt.AlignVCenter, f"{min_elev_int}")

                painter.end()
                pixmap = QPixmap.fromImage(q_img)
                breaks = active_breaks
                colors = msf_colors if msf_sheet is not None else (msf_colors if pruned_sheet is not None else ro_colors)

            # 4.5 Save layout automatically to output directory
            try:
                auto_save_path = os.path.join(output_dir, "map_preview_layout.png")
                q_img.save(auto_save_path)
                self._log(f"  ✓ Saved automatic map layout preview to: {auto_save_path}\n")
            except Exception as e:
                self._log(f"  ⚠ Warning: Failed to save automatic map layout preview: {e}\n")

            # 5. Open dialog modally on top
            self._preview_dialog = MapPreviewDialog(pixmap, breaks, colors, self)
            self._preview_dialog.raise_()
            self._preview_dialog.activateWindow()
            self._preview_dialog.exec_()
            self._log("   Map preview closed\n")
        except Exception as e:
            self._log(f" Error generating preview: {e}\n")
            QMessageBox.warning(self, "Preview Error", f"Could not generate map preview:\n{e}")

    def _get_natural_breaks(self, values, num_classes=5, min_val=1.1, max_val=2.0):
        target_vals = values[(values >= min_val) & (values <= max_val)]
        fallback_breaks = [min_val + (max_val - min_val) * i / num_classes for i in range(1, num_classes)]

        if len(target_vals) < num_classes * 10:
            return fallback_breaks

        if len(target_vals) > 20000:
            target_vals = np.random.choice(target_vals.ravel(), 20000, replace=False)
        else:
            target_vals = target_vals.ravel()

        centroids = np.linspace(min_val, max_val, num_classes)
        for _ in range(20):
            dists = np.abs(target_vals[:, np.newaxis] - centroids)
            labels = np.argmin(dists, axis=1)

            new_centroids = []
            for i in range(num_classes):
                cluster_vals = target_vals[labels == i]
                if len(cluster_vals) > 0:
                    new_centroids.append(cluster_vals.mean())
                else:
                    new_centroids.append(centroids[i])

            new_centroids = np.sort(new_centroids)
            if np.allclose(centroids, new_centroids, atol=1e-4):
                break
            centroids = new_centroids

        breaks = []
        for i in range(num_classes - 1):
            breaks.append((centroids[i] + centroids[i+1]) / 2.0)

        breaks = np.clip(np.sort(breaks), min_val + 0.001, max_val - 0.001).tolist()
        return breaks

class InteractiveGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.is_zoomed = False

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            angle = event.angleDelta().y()
            factor = 1.15 if angle > 0 else 0.85
            current_scale = self.transform().m11()
            if (factor > 1.0 and current_scale < 10.0) or (factor < 1.0 and current_scale > 0.05):
                self.scale(factor, factor)
                self.is_zoomed = True
        else:
            super().wheelEvent(event)

class MapPreviewDialog(QDialog):
    def __init__(self, pixmap, breaks, colors, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DF-scan Simulation Result Preview")
        self.setMinimumSize(1100, 800)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint)
        self.pixmap = pixmap

        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Left side: Image display in GraphicsView
        self.scene = QGraphicsScene(self)
        self.view = InteractiveGraphicsView(self)
        self.view.setMinimumSize(600, 600)
        self.view.setStyleSheet("background-color: rgba(20, 22, 27, 220); border: 1px solid rgba(43,49,64,200); border-radius: 8px;")
        self.view.setScene(self.scene)
        
        # Load the pixmap into the scene
        self.pixmap_item = self.scene.addPixmap(self.pixmap)
        self.scene.setSceneRect(0, 0, self.pixmap.width(), self.pixmap.height())
        layout.addWidget(self.view, 1)

        # Right side: Legend and controls in a groupbox or frame
        sidebar = QFrame()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("QFrame { background-color: rgba(32,36,43,180); border: 1px solid rgba(58,64,77,160); border-radius: 12px; } QLabel { border: none; background: transparent; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_layout.setSpacing(15)

        title = QLabel("DF-scan MAP LAYOUT")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #74d3ff; padding-bottom: 5px;")
        sidebar_layout.addWidget(title)

        info_lbl = QLabel("This view shows the finalized cartographic layout ready for export.\n\n"
        "Included layers:\n"
        "• Swiss Multi-directional Hillshade\n"
        "• ArcGIS Elevation Color Ramp\n"
        "• Transparent PQ_LIM probability spectrum\n"
        "• Scaled North Arrow & Scale Bar\n"
        "• Vector Triggering Points\n\n"
        "Controls:\n"
        "• Ctrl + Scroll: Zoom in/out\n"
        "• Click & Drag: Pan around map\n\n"
        "Use the button below to save the layout as a high-quality image file.")
        info_lbl.setStyleSheet("font-size: 11px; color: #EBEEF3; line-height: 1.4;")
        info_lbl.setWordWrap(True)
        sidebar_layout.addWidget(info_lbl)

        sidebar_layout.addStretch(1)

        # Action buttons
        self.btn_save = QPushButton("Save Image…")
        self.btn_save.setMinimumHeight(36)
        self.btn_save.setStyleSheet("QPushButton { background-color: rgba(0,179,255,200); color: #FFF; font-weight: 800; border-radius: 18px; } QPushButton:hover { background-color: rgba(0,200,255,255); }")
        self.btn_save.clicked.connect(self.save_image)

        self.btn_reset_zoom = QPushButton("Reset Zoom")
        self.btn_reset_zoom.setMinimumHeight(36)
        self.btn_reset_zoom.setStyleSheet("QPushButton { background-color: rgba(44,51,66,220); color: #FFF; font-weight: 800; border-radius: 18px; } QPushButton:hover { background-color: rgba(52,61,79,240); }")
        self.btn_reset_zoom.clicked.connect(self.reset_zoom)

        self.btn_close = QPushButton("Close")
        self.btn_close.setMinimumHeight(36)
        self.btn_close.setStyleSheet("QPushButton { background-color: rgba(44,51,66,220); color: #FFF; font-weight: 800; border-radius: 18px; } QPushButton:hover { background-color: rgba(52,61,79,240); }")
        self.btn_close.clicked.connect(self.close)

        sidebar_layout.addWidget(self.btn_save)
        sidebar_layout.addWidget(self.btn_reset_zoom)
        sidebar_layout.addWidget(self.btn_close)

        layout.addWidget(sidebar, 0)

        # Initial pixmap display
        QTimer.singleShot(100, self.update_pixmap)

    def update_pixmap(self):
        if not self.pixmap.isNull():
            if not self.view.is_zoomed:
                self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def reset_zoom(self):
        self.view.is_zoomed = False
        self.view.resetTransform()
        self.update_pixmap()

    def save_image(self):
        path, _ = QFileDialog.getSaveFileName(
        self, "Save Preview Image", "msf_preview.png", "PNG Image (*.png);;JPEG Image (*.jpg)"
        )
        if path:
            try:
                self.pixmap.save(path)
                QMessageBox.information(self, "Saved", f"Map preview saved to:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save image:\n{e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(50, self.update_pixmap)

    def closeEvent(self, event):
        # Auto-save current config to msf_config.json on exit
        try:
            current_conf = self._widgets_to_conf()
            with open("msf_config.json", "w", encoding="utf-8") as f:
                json.dump(current_conf, f, indent=2)
        except Exception as e:
            print(f"[Debug] Failed to auto-save msf_config.json on exit: {e}")
        super().closeEvent(event)


def main():
# Fix for Windows taskbar icon
    if sys.platform == 'win32':
        try:
            import ctypes
            myappid = 'anthropic.msf.regional.v5'  # Arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except:
            pass

    # Check if CLI mode is requested (e.g. --config is passed)
    if "--config" in sys.argv:
        # HEADLESS CLI MODE
        # Attach to parent console if on Windows to show stdout in terminal
        if sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.kernel32.AttachConsole(-1)
                sys.stdout = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
                sys.stderr = open('CONOUT$', 'w', encoding='utf-8', errors='replace')
            except:
                pass
        
        print("\nMSF Standalone Execution - Headless CLI Mode")
        import argparse
        p = argparse.ArgumentParser(description="MSF - CLI Mode")
        p.add_argument("--config", required=True, help="Path to a JSON config file")
        p.add_argument("--set", action="append", default=[], help="Override KEY=VALUE (repeatable)")
        args, unknown = p.parse_known_args()
        
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            TRUE, FALSE = {"1","true","yes","on","y","t"}, {"0","false","no","off","n","f"}
            def coerce(v:str):
                s=v.strip().lower()
                if s in TRUE: return True
                if s in FALSE: return False
                try:
                    return float(v) if "." in v else int(v)
                except ValueError:
                    return v
            
            for pair in args.set:
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    data[k.strip()] = coerce(v)
            
            for k, v in data.items():
                if hasattr(core.Config, k):
                    setattr(core.Config, k, v)
                    print(f"  Config: {k} = {v}")
                else:
                    print(f"  Warning: Unknown config key '{k}' ignored.")
            
            print("\nStarting MSF Core Engine in CLI mode...")
            core.main()
            print("\nSUCCESS: Execution completed successfully!")
            sys.exit(0)
        except Exception as e:
            print(f"\nERROR in CLI execution: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    app = QApplication(sys.argv)
    app.setWindowIcon(build_debris_icon())  # Set icon for taskbar
    set_tech_glass_theme(app)
    w = MSFWindow();
    w.show();
    if os.environ.get("MSF_AUTO_RUN") == "1":
    # Load msf_config.json automatically
        config_path = os.path.join(os.path.dirname(sys.argv[0]), "msf_config.json")
        if not os.path.exists(config_path):
            config_path = "msf_config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                apply_config_to_core(data)
                w._load_defaults()
            except Exception as e:
                pass
        QTimer.singleShot(1000, w.on_run)
    sys.exit(app.exec_())


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
