#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MSF – Tabbed One-Window GUI v5 (PyQt5)
- Tech theme with transparent background image support
- Toggle buttons instead of checkboxes
- Improved path field display
- Better console output capture for parallel processing
- Removed redundant tab titles
"""

import sys, os, json, threading, time, re
from pathlib import Path
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QPalette, QColor, QFont, QTextCursor, QIcon, QPixmap, QImage, QPainter
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QPushButton,
    QFileDialog, QTextEdit, QMessageBox, QLabel, QTabWidget, QStyleFactory,
    QProgressBar, QScrollArea
)

try:
    from PyQt5.QtSvg import QSvgRenderer

    _HAS_SVG = True
except Exception:
    _HAS_SVG = False

try:
    from . import msf_engine as core
except ImportError:
    import msf_engine as core
except Exception as e:
    raise SystemExit(f"Could not import msf_engine.py: {e}")


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
            margin-top: 40px; padding: 16px; background-color: rgba(32,36,43,180);
        }
        QGroupBox::title {
            subcontrol-origin: margin; left: 12px; top: 14px;
            padding: 0 14px; color: #74d3ff; background-color: rgba(32,36,43,210); 
            font-weight: 700; font-size: 13px;
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
        QScrollArea {
            background-color: transparent;
            border: none;
        }
        QScrollArea > QWidget > QWidget {
            background-color: transparent;
        }
        QScrollBar:vertical {
            border: none;
            background: rgba(24,27,32,150);
            width: 10px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: rgba(0, 179, 255, 120);
            min-height: 20px;
            border-radius: 5px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QTabBar::tab {
            background: rgba(38,43,53,200); border: 1px solid rgba(58,64,77,160); 
            padding: 12px 30px; border-top-left-radius: 8px; border-top-right-radius: 8px; 
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MSF – Regional Workflow (PyQt5 GUI) v5")
        self.setWindowIcon(build_debris_icon())
        self.setMinimumSize(1000, 800)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self._thread = None
        self._old_out = None
        self._old_err = None
        self._log_lines = []
        self._log_buffer = []
        self._saw_completed = False
        self._forced_restore = None
        self._bg_pixmap = None
        self._load_background()
        self._build_ui()
        self._load_defaults()
        self._wire_enable_logic()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(150)
        self._poll_timer.timeout.connect(self._poll_flush)
        self._poll_timer.start()

    def _load_background(self):
        # Path logic for assets in development vs bundled mode
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(__file__)))
        path = os.path.join(base, "assets", "image.jpg")
        if os.path.exists(path):
            try:
                self._bg_pixmap = QPixmap(path)
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
        
        # Logo loading
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(__file__)))
        logo_path = os.path.join(base, "assets", "logo2.png")
        if os.path.exists(logo_path):
            logo_lbl = QLabel()
            logo_lbl.setPixmap(QPixmap(logo_path).scaled(160, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            hdr.addWidget(logo_lbl)
            hdr.addSpacing(15)

        icon_lbl = QLabel();
        icon_lbl.setPixmap(build_debris_icon().pixmap(34, 34))
        title = QLabel("MSF – Regional Workflow");
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

    def _make_scrollable_tab(self):
        tab = QWidget()
        scroll = QScrollArea(tab)
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(12)
        scroll.setWidget(scroll_content)
        main_tab_layout = QVBoxLayout(tab)
        main_tab_layout.setContentsMargins(0, 0, 0, 0)
        main_tab_layout.addWidget(scroll)
        return tab, layout

    def _tab_inputs(self):
        tab, layout = self._make_scrollable_tab()
        
        # --- Group 1: Required Static Inputs ---
        grp_static = QGroupBox("1. Required Static Inputs");
        form_static = QFormLayout();
        form_static.setSpacing(18);
        form_static.setLabelAlignment(Qt.AlignRight)
        
        self.e_dtm_orig = QLineEdit();
        btn_dtm_orig = QPushButton("…");
        btn_dtm_orig.setMaximumWidth(40)
        btn_dtm_orig.clicked.connect(
            lambda: self._browse_file(self.e_dtm_orig, "Select DTM Original", "GeoTIFF (*.tif)"))
        h1 = QHBoxLayout();
        h1.addWidget(self.e_dtm_orig);
        h1.addWidget(btn_dtm_orig)
        form_static.addRow("Base DTM:", h1)

        # Unified Initiation Points Row
        self.e_source_path = QLineEdit();
        btn_source_browse = QPushButton("…");
        btn_source_browse.setMaximumWidth(40)
        self.cmb_source_type = QComboBox();
        self.cmb_source_type.addItems(["SHAPEFILE", "RASTER"])
        self.cmb_source_type.setFixedWidth(120)

        def browse_source():
            is_shp = self.cmb_source_type.currentText() == "SHAPEFILE"
            cap = "Select Shapefile" if is_shp else "Select Source Raster"
            filt = "Shapefile (*.shp)" if is_shp else "GeoTIFF (*.tif)"
            self._browse_file(self.e_source_path, cap, filt)

        btn_source_browse.clicked.connect(browse_source)

        h_source = QHBoxLayout();
        h_source.addWidget(self.e_source_path);
        h_source.addWidget(btn_source_browse);
        h_source.addWidget(self.cmb_source_type)
        form_static.addRow("Initiation Points:", h_source)

        self.e_shape_elev = QLineEdit()
        form_static.addRow("Shapefile Elev Field:", self.e_shape_elev)
        
        grp_static.setLayout(form_static)
        layout.addWidget(grp_static)

        # --- Group 2: Optional Pre-computed Inputs (Overrides Engine) ---
        grp_opt = QGroupBox("2. Optional Pre-computed Inputs (Overrides Engine)");
        form_opt = QFormLayout();
        form_opt.setSpacing(18);
        form_opt.setLabelAlignment(Qt.AlignRight)

        self.btn_dtm_filled = self._toggle_button("Use External Filled DTM")
        self.e_dtm_filled = QLineEdit();
        btn_dtm_filled = QPushButton("…");
        btn_dtm_filled.setMaximumWidth(40)
        btn_dtm_filled.clicked.connect(
            lambda: self._browse_file(self.e_dtm_filled, "Select DTM Filled", "GeoTIFF (*.tif)"))
        h2 = QHBoxLayout();
        h2.addWidget(self.btn_dtm_filled);
        h2.addWidget(self.e_dtm_filled);
        h2.addWidget(btn_dtm_filled)
        form_opt.addRow("Filled DTM:", h2)

        self.btn_fdir = self._toggle_button("Use External FDIR")
        self.e_fdir = QLineEdit();
        btn_fdir = QPushButton("…");
        btn_fdir.setMaximumWidth(40)
        btn_fdir.clicked.connect(lambda: self._browse_file(self.e_fdir, "Select Flow Direction", "GeoTIFF (*.tif)"))
        h3 = QHBoxLayout();
        h3.addWidget(self.btn_fdir);
        h3.addWidget(self.e_fdir);
        h3.addWidget(btn_fdir)
        form_opt.addRow("FDIR Path:", h3)
        
        grp_opt.setLayout(form_opt)
        layout.addWidget(grp_opt)

        # --- Group 3: Output naming ---
        grp_out = QGroupBox("3. Output Settings");
        form_out = QFormLayout();
        form_out.setSpacing(18)
        self.e_outdir = QLineEdit();
        btn_outdir = QPushButton("…");
        btn_outdir.setMaximumWidth(40)
        btn_outdir.clicked.connect(lambda: self._browse_dir(self.e_outdir, "Select Output Directory"))
        h_out = QHBoxLayout();
        h_out.addWidget(self.e_outdir);
        h_out.addWidget(btn_outdir)
        form_out.addRow("Output Directory:", h_out)
        
        self.e_pqlim_filename = QLineEdit()
        form_out.addRow("PQ_LIM Filename:", self.e_pqlim_filename)
        
        grp_out.setLayout(form_out)
        layout.addWidget(grp_out)

        layout.addStretch(1)
        self.tabs.addTab(tab, "Inputs")

    def _tab_resampling(self):
        tab, layout = self._make_scrollable_tab()
        grp = QGroupBox("DTM Resampling");
        form = QFormLayout();
        form.setSpacing(18);
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
        layout.addStretch(1)
        self.tabs.addTab(tab, "Resampling")

    def _tab_parallel(self):
        tab, layout = self._make_scrollable_tab()
        grp = QGroupBox("Parallel Processing");
        form = QFormLayout();
        form.setSpacing(18);
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
        self.tabs.addTab(tab, "Parallel")

    def _tab_processing(self):
        tab, layout = self._make_scrollable_tab()
        grp = QGroupBox("Automated Engine Steps (If no External overrides are used)");
        form = QFormLayout();
        form.setSpacing(18);
        form.setLabelAlignment(Qt.AlignRight)
        self.btn_pit = self._toggle_button("Compute Pit Filling", True)
        form.addRow("Pit Filling:", self.btn_pit)
        self.btn_wbt_fill = self._toggle_button("   ↳ via WhiteboxTools", True)
        form.addRow("", self.btn_wbt_fill)
        
        self.btn_calc_fdir = self._toggle_button("Compute Flow Direction", True)
        form.addRow("Flow Direction:", self.btn_calc_fdir)
        self.btn_wbt_fdir = self._toggle_button("   ↳ via WhiteboxTools")
        form.addRow("", self.btn_wbt_fdir)
        
        grp.setLayout(form);
        layout.addWidget(grp);
        layout.addStretch(1)
        self.tabs.addTab(tab, "Processing")

    def _tab_msf(self):
        tab, layout = self._make_scrollable_tab()
        grp = QGroupBox("MSF Model Parameters");
        form = QFormLayout();
        form.setSpacing(18);
        form.setLabelAlignment(Qt.AlignRight)
        self.spn_maxslope = QDoubleSpinBox();
        self.spn_maxslope.setRange(0, 90);
        self.spn_maxslope.setValue(30);
        self.spn_maxslope.setDecimals(1)
        form.addRow("Max Slope (deg):", self.spn_maxslope)
        self.dsp_hl = QDoubleSpinBox();
        self.dsp_hl.setRange(0, 10);
        self.dsp_hl.setValue(0.19);
        self.dsp_hl.setDecimals(4);
        self.dsp_hl.setSingleStep(0.01)
        form.addRow("H/L Threshold:", self.dsp_hl)
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
        self.spn_cut.setValue(90)
        form.addRow("Cut Angle:", self.spn_cut)
        self.dsp_slope = QDoubleSpinBox();
        self.dsp_slope.setRange(0, 1);
        self.dsp_slope.setValue(0.011111);
        self.dsp_slope.setDecimals(6)
        form.addRow("Slope:", self.dsp_slope)
        grp.setLayout(form);
        layout.addWidget(grp);
        layout.addStretch(1)
        self.tabs.addTab(tab, "MSF Model")

    def _tab_advanced(self):
        tab, layout = self._make_scrollable_tab()
        grp = QGroupBox("Advanced Options");
        form = QFormLayout();
        form.setSpacing(18);
        form.setLabelAlignment(Qt.AlignRight)
        self.spn_wbt_breach = QSpinBox();
        self.spn_wbt_breach.setRange(0, 100);
        self.spn_wbt_breach.setValue(5)
        form.addRow("WBT Breach Dist:", self.spn_wbt_breach)
        self.btn_wbt_deps = self._toggle_button("WBT Fill Depressions", True)
        form.addRow("WBT Fill Deps:", self.btn_wbt_deps)
        self.btn_save_inter = self._toggle_button("Save Intermediate")
        form.addRow("Save Intermediate:", self.btn_save_inter)
        self.btn_compress = self._toggle_button("Compress Outputs", True)
        form.addRow("Compress:", self.btn_compress)
        grp.setLayout(form);
        layout.addWidget(grp);
        layout.addStretch(1)
        self.tabs.addTab(tab, "Advanced")

    def _tab_outputs(self):
        tab, layout = self._make_scrollable_tab()
        grp = QGroupBox("Output Options");
        form = QFormLayout();
        form.setSpacing(18);
        form.setLabelAlignment(Qt.AlignRight)
        self.btn_save_li = self._toggle_button("Save LI Raster")
        form.addRow("LI Raster:", self.btn_save_li)
        self.btn_save_li_bl = self._toggle_button("Save LI Backlink")
        form.addRow("LI Backlink:", self.btn_save_li_bl)
        self.btn_save_fri = self._toggle_button("Save FRI Raster")
        form.addRow("FRI Raster:", self.btn_save_fri)
        self.btn_save_fri_bl = self._toggle_button("Save FRI Backlink")
        form.addRow("FRI Backlink:", self.btn_save_fri_bl)
        grp.setLayout(form);
        layout.addWidget(grp);
        layout.addStretch(1)
        self.tabs.addTab(tab, "Outputs")

    def _tab_logs(self):
        tab = QWidget();
        layout = QVBoxLayout(tab);
        layout.setSpacing(8)
        self.console = QTextEdit();
        self.console.setReadOnly(True)
        self.console.setStyleSheet("QTextEdit{font-family:'Consolas','Courier New',monospace;font-size:10pt;}")
        h = QHBoxLayout()
        self.btn_clear_log = self._toggle_button("Clear on Run", True)
        btn_export = QPushButton("Export Log…");
        btn_export.clicked.connect(self._export_log)
        h.addWidget(self.btn_clear_log);
        h.addWidget(btn_export);
        h.addStretch(1)
        layout.addLayout(h);
        layout.addWidget(self.console, 1)
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
        # When "Use External Filled DTM" is checked, we don't NEED the engine to fill pits
        self.btn_dtm_filled.toggled.connect(lambda c: (
            self.e_dtm_filled.setEnabled(c),
            self.btn_pit.setChecked(not c) if c else None
        ))
        # When "Use External FDIR" is checked, we don't NEED the engine to calc fdir
        self.btn_fdir.toggled.connect(lambda c: (
            self.e_fdir.setEnabled(c),
            self.btn_calc_fdir.setChecked(not c) if c else None
        ))
        
        self.btn_resample.toggled.connect(lambda c: (self.spn_target_res.setEnabled(c), self.cmb_agg.setEnabled(c)))
        self.btn_parallel.toggled.connect(lambda c: (self.spn_workers.setEnabled(c), self.spn_ppw.setEnabled(c)))
        self.btn_pit.toggled.connect(lambda c: self.btn_wbt_fill.setEnabled(c))
        self.btn_calc_fdir.toggled.connect(lambda c: self.btn_wbt_fdir.setEnabled(c))

    def _load_defaults(self):
        d = get_config_defaults()
        stype = d.get("SOURCE_INPUT_TYPE", "SHAPEFILE")
        self.cmb_source_type.setCurrentText(stype)
        if stype == "SHAPEFILE":
            self.e_source_path.setText(d.get("SOURCE_SHAPEFILE_PATH", ""))
        else:
            self.e_source_path.setText(d.get("SOURCE_RASTER_PATH", ""))

        self.e_dtm_orig.setText(d.get("DTM_ORIGINAL_PATH", ""))
        dtm_filled = d.get("DTM_FILLED_PATH", "")
        self.btn_dtm_filled.setChecked(bool(dtm_filled))
        self.e_dtm_filled.setText(dtm_filled)
        fdir_path = d.get("FDIR_PATH", "")
        self.btn_fdir.setChecked(bool(fdir_path))
        self.e_fdir.setText(fdir_path)
        self.e_shape_elev.setText(d.get("SHAPEFILE_ELEV_FIELD", ""))
        self.e_pqlim_filename.setText(d.get("PQLIM_OUTPUT_FILENAME", "pq_lim.tif"))
        self.e_outdir.setText(d.get("OUTPUT_DIR", ""))
        self.btn_resample.setChecked(d.get("RESAMPLE_DTM", False))
        self.spn_target_res.setValue(d.get("TARGET_RESOLUTION", 25))
        self.cmb_agg.setCurrentText(d.get("AGGREGATION_METHOD", "median"))
        self.btn_parallel.setChecked(d.get("ENABLE_PARALLEL_PROCESSING", False))
        self.spn_workers.setValue(d.get("NUM_WORKERS", 12))
        self.spn_ppw.setValue(d.get("POINTS_PER_WORKER", 1))
        self.btn_pit.setChecked(d.get("DO_PIT_FILLING", True))
        self.btn_wbt_fill.setChecked(d.get("USE_WHITEBOX_FILLING", True))
        self.btn_calc_fdir.setChecked(d.get("CALCULATE_FLOW_DIRECTION", True))
        self.btn_wbt_fdir.setChecked(d.get("USE_WHITEBOX_FDIR", False))
        self.spn_maxslope.setValue(d.get("MAX_SLOPE_DEGREES", 30))
        self.dsp_hl.setValue(d.get("H_L_THRESHOLD", 0.19))
        self.btn_dir_uphill.setChecked(d.get("USE_DIRECTION_AWARE_UPHILL", False))
        self.btn_direct_hl.setChecked(d.get("USE_DIRECT_DISTANCE_FOR_HL", False))
        self.spn_hrma_from.setValue(d.get("HRMA_FROM_THRESH_LI", 90))
        self.spn_hrma_to.setValue(d.get("HRMA_TO_THRESH_LI", 90))
        self.dsp_zero.setValue(d.get("ZERO_FACTOR", 0.5))
        self.spn_cut.setValue(d.get("CUT_ANGLE", 90))
        self.dsp_slope.setValue(d.get("SLOPE", 0.011111))
        self.spn_wbt_breach.setValue(d.get("WBT_BREACH_DIST", 5))
        self.btn_wbt_deps.setChecked(d.get("WBT_FILL_DEPS", True))
        self.btn_save_inter.setChecked(d.get("SAVE_INTERMEDIATE_OUTPUTS", False))
        self.btn_compress.setChecked(d.get("COMPRESS_OUTPUTS", True))
        self.btn_save_li.setChecked(d.get("SAVE_LI_RASTER", False))
        self.btn_save_li_bl.setChecked(d.get("SAVE_LI_BACKLINK", False))
        self.btn_save_fri.setChecked(d.get("SAVE_FRI_RASTER", False))
        self.btn_save_fri_bl.setChecked(d.get("SAVE_FRI_BACKLINK", False))
        self._wire_enable_logic()

    def _widgets_to_conf(self) -> dict:
        stype = self.cmb_source_type.currentText()
        spath = self.e_source_path.text().strip()
        conf = {
            "SOURCE_INPUT_TYPE": stype,
            "DTM_ORIGINAL_PATH": self.e_dtm_orig.text().strip(),
            "DTM_FILLED_PATH": self.e_dtm_filled.text().strip() if self.btn_dtm_filled.isChecked() else "",
            "FDIR_PATH": self.e_fdir.text().strip() if self.btn_fdir.isChecked() else "",
            "SOURCE_SHAPEFILE_PATH": spath if stype == "SHAPEFILE" else "",
            "SOURCE_RASTER_PATH": spath if stype == "RASTER" else "",
            "SHAPEFILE_ELEV_FIELD": self.e_shape_elev.text().strip(),
            "PQLIM_OUTPUT_FILENAME": self.e_pqlim_filename.text().strip(),
            "OUTPUT_DIR": self.e_outdir.text().strip(),
            "RESAMPLE_DTM": self.btn_resample.isChecked(),
            "TARGET_RESOLUTION": self.spn_target_res.value(),
            "AGGREGATION_METHOD": self.cmb_agg.currentText(),
            "ENABLE_PARALLEL_PROCESSING": self.btn_parallel.isChecked(),
            "NUM_WORKERS": self.spn_workers.value(),
            "POINTS_PER_WORKER": self.spn_ppw.value(),
            "DO_PIT_FILLING": self.btn_pit.isChecked(),
            "USE_WHITEBOX_FILLING": self.btn_wbt_fill.isChecked(),
            "CALCULATE_FLOW_DIRECTION": self.btn_calc_fdir.isChecked(),
            "USE_WHITEBOX_FDIR": self.btn_wbt_fdir.isChecked(),
            "MAX_SLOPE_DEGREES": self.spn_maxslope.value(),
            "H_L_THRESHOLD": float(self.dsp_hl.value()),
            "USE_DIRECTION_AWARE_UPHILL": self.btn_dir_uphill.isChecked(),
            "USE_DIRECT_DISTANCE_FOR_HL": self.btn_direct_hl.isChecked(),
            "HRMA_FROM_THRESH_LI": self.spn_hrma_from.value(),
            "HRMA_TO_THRESH_LI": self.spn_hrma_to.value(),
            "ZERO_FACTOR": float(self.dsp_zero.value()),
            "CUT_ANGLE": self.spn_cut.value(),
            "SLOPE": float(self.dsp_slope.value()),
            "WBT_BREACH_DIST": self.spn_wbt_breach.value(),
            "WBT_FILL_DEPS": self.btn_wbt_deps.isChecked(),
            "SAVE_INTERMEDIATE_OUTPUTS": self.btn_save_inter.isChecked(),
            "COMPRESS_OUTPUTS": self.btn_compress.isChecked(),
            "SAVE_LI_RASTER": self.btn_save_li.isChecked(),
            "SAVE_LI_BACKLINK": self.btn_save_li_bl.isChecked(),
            "SAVE_FRI_RASTER": self.btn_save_fri.isChecked(),
            "SAVE_FRI_BACKLINK": self.btn_save_fri_bl.isChecked(),
        }
        return conf

    def _apply_conf_and_validate(self, conf: dict) -> bool:
        # 1. Check Output Directory
        if not conf.get("OUTPUT_DIR"):
            QMessageBox.warning(self, "Validation Error", "Please set the Output Directory.")
            return False
        
        # 2. Check Base DTM (Always required)
        dtm_path = conf.get("DTM_ORIGINAL_PATH")
        if not dtm_path or not os.path.exists(dtm_path):
            QMessageBox.warning(self, "Validation Error", f"Base DTM file not found:\n{dtm_path}")
            return False

        # 3. Check Initiation Points
        stype = conf.get("SOURCE_INPUT_TYPE")
        if stype == "SHAPEFILE":
            spath = conf.get("SOURCE_SHAPEFILE_PATH")
            if not spath or not os.path.exists(spath):
                QMessageBox.warning(self, "Validation Error", f"Source Shapefile not found:\n{spath}")
                return False
        else:
            rpath = conf.get("SOURCE_RASTER_PATH")
            if not rpath or not os.path.exists(rpath):
                QMessageBox.warning(self, "Validation Error", f"Source Raster not found:\n{rpath}")
                return False

        # 4. Check External Overrides if toggled
        if self.btn_dtm_filled.isChecked():
            fpath = conf.get("DTM_FILLED_PATH")
            if not fpath or not os.path.exists(fpath):
                QMessageBox.warning(self, "Validation Error", f"External Filled DTM not found:\n{fpath}")
                return False

        if self.btn_fdir.isChecked():
            dpath = conf.get("FDIR_PATH")
            if not dpath or not os.path.exists(dpath):
                QMessageBox.warning(self, "Validation Error", f"External FDIR file not found:\n{dpath}")
                return False

        # Create output dir if it doesn't exist
        try:
            os.makedirs(conf["OUTPUT_DIR"], exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create output directory:\n{e}")
            return False

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
        if self.btn_clear_log.isChecked():
            self.console.clear();
            self._log_lines.clear()
        conf = self._widgets_to_conf()
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
        try:
            core.main()
        except Exception as e:
            # Print to sys.stdout/err which is currently captured by EmittingStream
            print(f"\n❌ FATAL ENGINE ERROR: {e}\n")
            import traceback
            traceback.print_exc()
        finally:
            # Use QTimer to ensure UI updates happen on the main thread
            def finish():
                sys.stdout = self._old_out or sys.__stdout__;
                sys.stderr = self._old_err or sys.__stderr__
                self._old_out = self._old_err = None
                if self._forced_restore is not None:
                    for k, v in self._forced_restore.items():
                        setattr(core.Config, k, v)
                    self._forced_restore = None
                
                # Check if we actually finished or crashed
                if self._saw_completed:
                    self._set_status("Completed")
                    self.progress.setValue(100)
                else:
                    self._set_status("Error - Stopped")
                
                self.btn_run.setEnabled(True)
                self._log(f"[{time.strftime('%H:%M:%S')}] Run thread finished\n")

            QTimer.singleShot(50, finish)

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

        # 2. Flush Python system buffers
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


def main():
    # Fix for Windows taskbar icon
    if sys.platform == 'win32':
        try:
            import ctypes
            myappid = 'anthropic.msf.regional.v5'  # Arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except:
            pass

    app = QApplication(sys.argv)
    app.setWindowIcon(build_debris_icon())  # Set icon for taskbar
    set_tech_glass_theme(app)
    w = MSFWindow();
    w.show();
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()