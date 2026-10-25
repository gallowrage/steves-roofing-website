import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
try:
    from PIL import Image, ImageTk
except ImportError:
    # Pillow is optional; the application can still start without satellite imagery.
    Image = None
    ImageTk = None
import urllib.request
import urllib.parse
import json
import io
import math
import threading
import os
from datetime import datetime, timezone

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class UnifiedRoofingOS(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Steve's Roofing Operations OS - Unified QAC & Field Estimator")
        self.geometry("1360x860")
        self.minsize(1150, 750)

        # ---------------- State Variables ----------------
        self.quote_ready = False
        self.accepted = False
        self.contract_signed = False
        self.quote_drafted_at = None
        self.accepted_at = None
        self.contract_signed_at = None
        self.audit_log = []

        # Canvas measurement state
        self.points = []
        self.point_markers = []
        self.polygon_id = None
        self.closed = False
        self.bg_photo = None
        self.current_zoom = 19

        # Pitch multipliers: sqrt(1 + (pitch/12)^2)
        self.pitch_multipliers = {
            "Flat (0/12)": 1.000,
            "Low (3/12)": 1.031,
            "Standard (4/12)": 1.054,
            "Moderate (6/12)": 1.118,
            "Steep (8/12)": 1.202,
            "Severe (10/12)": 1.302,
            "Mansard/Extreme (12/12)": 1.414
        }

        # Best Buy Metals catalog pricing
        self.pricing_table = {
            "26ga Standing Seam (16in panel)": {"unit_cost_sqft": 3.45, "nominal_width_in": 16.0},
            "29ga Tuff-Rib / Agricultural (36in)": {"unit_cost_sqft": 2.15, "nominal_width_in": 36.0},
            "24ga Commercial Standing Seam (18in)": {"unit_cost_sqft": 4.60, "nominal_width_in": 18.0}
        }

        # Grid config
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_panel()

    # ---------------- 1. SIDEBAR & PIPELINE GATE ----------------
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)

        ctk.CTkLabel(
            self.sidebar, 
            text="STEVE'S ROOFING\nOPERATIONS OS", 
            font=("Arial", 18, "bold")
        ).grid(row=0, column=0, padx=20, pady=(25, 15))

        # API Keys Section
        ctk.CTkLabel(self.sidebar, text="CREDENTIAL VAULT", font=("Arial", 11, "bold"), text_color="gray").grid(row=1, column=0, padx=20, pady=(5, 2), sticky="w")
        
        self.gemini_key_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Gemini API Key...", show="*")
        self.gemini_key_entry.grid(row=2, column=0, padx=20, pady=4, sticky="ew")
        if os.environ.get("GEMINI_API_KEY"):
            self.gemini_key_entry.insert(0, os.environ.get("GEMINI_API_KEY"))

        self.maps_key_entry = ctk.CTkEntry(self.sidebar, placeholder_text="Google Maps API Key (Optional)...", show="*")
        self.maps_key_entry.grid(row=3, column=0, padx=20, pady=4, sticky="ew")

        # Pipeline progress indicators
        ctk.CTkLabel(self.sidebar, text="QAC PIPELINE GATE", font=("Arial", 11, "bold"), text_color="gray").grid(row=4, column=0, padx=20, pady=(15, 5), sticky="w")

        self.lbl_quote = ctk.CTkLabel(self.sidebar, text="[  ] 1. Quote Drafted", text_color="#A0A0A0", anchor="w")
        self.lbl_quote.grid(row=5, column=0, padx=20, pady=2, sticky="w")

        self.lbl_accept = ctk.CTkLabel(self.sidebar, text="[  ] 2. Customer Accepted", text_color="#A0A0A0", anchor="w")
        self.lbl_accept.grid(row=6, column=0, padx=20, pady=2, sticky="w")

        self.lbl_contract = ctk.CTkLabel(self.sidebar, text="[  ] 3. Contract Signed", text_color="#A0A0A0", anchor="w")
        self.lbl_contract.grid(row=7, column=0, padx=20, pady=2, sticky="w")

        # Operational Status Indicator Card
        self.status_card = ctk.CTkFrame(self.sidebar, fg_color="#2A2A2A")
        self.status_card.grid(row=8, column=0, padx=15, pady=20, sticky="s")

        self.status_text = ctk.CTkLabel(
            self.status_card, 
            text="GATE STATUS:\nLOCKED (RED)", 
            font=("Arial", 13, "bold"), 
            text_color="#FF4C4C"
        )
        self.status_text.pack(padx=15, pady=12)

        self.btn_reset = ctk.CTkButton(
            self.sidebar, 
            text="Reset Workflow", 
            fg_color="#3A3A3A", 
            hover_color="#505050", 
            command=self.reset_workflow
        )
        self.btn_reset.grid(row=9, column=0, padx=20, pady=(0, 20))

        self.btn_export = ctk.CTkButton(
            self.sidebar,
            text="Export Job Record",
            fg_color="#1565C0",
            hover_color="#0D47A1",
            command=self.export_job_record
        )
        self.btn_export.grid(row=10, column=0, padx=20, pady=(0, 20))

        self.btn_save = ctk.CTkButton(
            self.sidebar,
            text="Save Job",
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            command=self.save_job
        )
        self.btn_save.grid(row=11, column=0, padx=20, pady=(0, 10))

        self.btn_load = ctk.CTkButton(
            self.sidebar,
            text="Load Job",
            fg_color="#5D4037",
            hover_color="#3E2723",
            command=self.load_job
        )
        self.btn_load.grid(row=12, column=0, padx=20, pady=(0, 20))

    # ---------------- 2. MAIN WORKSPACE & TABS ----------------
    def _build_main_panel(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self.main_container)
        self.tabview.grid(row=0, column=0, sticky="nsew")

        self.tab_qac = self.tabview.add("Stage 1: Job Intake & QAC Quote")
        self.tab_measure = self.tabview.add("Stage 2: Satellite Measure & Best Buy BOM")
        self.tab_codes = self.tabview.add("Stage 3: NC Building Codes & Permits")
        self.tab_phases = self.tabview.add("Stage 4: Execution Checklist")

        self._build_tab_qac()
        self._build_tab_measure()
        self._build_tab_codes()
        self._build_tab_phases()

    # ---------------- TAB 1: QAC & AI PROPOSAL ----------------
    def _build_tab_qac(self):
        self.tab_qac.grid_columnconfigure(0, weight=1)
        self.tab_qac.grid_columnconfigure(1, weight=1)
        self.tab_qac.grid_rowconfigure(1, weight=1)

        # Left: Customer Notes & Triggers
        left_intake = ctk.CTkFrame(self.tab_qac)
        left_intake.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(5, 10), pady=5)
        left_intake.grid_rowconfigure(1, weight=1)
        left_intake.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left_intake, text="Customer Job Intake / Field Notes:", font=("Arial", 14, "bold")).grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        self.txt_notes = ctk.CTkTextbox(left_intake, font=("Arial", 12))
        self.txt_notes.grid(row=1, column=0, padx=15, pady=5, sticky="nsew")
        self.txt_notes.insert("0.0", (
            "Customer: David Galloway\n"
            "Address: 690 Dogwood Lane, Buncombe County, NC\n"
            "Footprint: Roughly 1,400 sq ft, 6/12 pitch roof.\n"
            "Scope: Strip existing shingles. Install 26ga Galvalume standing seam (Black finish).\n"
            "Needs high-temp synthetic underlayment, ice & water shield in valleys, and chimney flashing."
        ))

        # Action Buttons
        btn_bar = ctk.CTkFrame(left_intake, fg_color="transparent")
        btn_bar.grid(row=2, column=0, padx=15, pady=15, sticky="ew")

        self.btn_gen_quote = ctk.CTkButton(btn_bar, text="⚡ Draft AI Quote", fg_color="#1E88E5", command=self.action_draft_quote)
        self.btn_gen_quote.pack(side="left", padx=5, expand=True, fill="x")

        self.btn_accept = ctk.CTkButton(btn_bar, text="2. Mark Accepted", state="disabled", command=self.action_mark_accepted)
        self.btn_accept.pack(side="left", padx=5, expand=True, fill="x")

        self.btn_sign = ctk.CTkButton(btn_bar, text="3. Sign Contract (QAC Lock)", state="disabled", fg_color="#2E7D32", command=self.action_sign_contract)
        self.btn_sign.pack(side="left", padx=5, expand=True, fill="x")

        signature_bar = ctk.CTkFrame(left_intake, fg_color="#2A2A2A")
        signature_bar.grid(row=3, column=0, padx=15, pady=(0, 15), sticky="ew")
        signature_bar.grid_columnconfigure(1, weight=1)
        signature_bar.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(signature_bar, text="Customer signature:").grid(row=0, column=0, padx=(10, 5), pady=8, sticky="w")
        self.customer_signature_entry = ctk.CTkEntry(signature_bar, placeholder_text="Typed name")
        self.customer_signature_entry.grid(row=0, column=1, padx=5, pady=8, sticky="ew")
        ctk.CTkLabel(signature_bar, text="Contractor signature:").grid(row=0, column=2, padx=(10, 5), pady=8, sticky="w")
        self.contractor_signature_entry = ctk.CTkEntry(signature_bar, placeholder_text="Typed name")
        self.contractor_signature_entry.grid(row=0, column=3, padx=(5, 10), pady=8, sticky="ew")

        # Right: Formatted Quote Preview
        right_quote = ctk.CTkFrame(self.tab_qac)
        right_quote.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(5, 5), pady=5)
        right_quote.grid_rowconfigure(1, weight=1)
        right_quote.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right_quote, text="Proposal & Contract Preview:", font=("Arial", 14, "bold")).grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        self.txt_quote_preview = ctk.CTkTextbox(right_quote, font=("Consolas", 12))
        self.txt_quote_preview.grid(row=1, column=0, padx=15, pady=(5, 15), sticky="nsew")
        self.txt_quote_preview.insert("0.0", "Click 'Draft AI Quote' to synthesize customer notes...")

    # ---------------- TAB 2: SATELLITE MEASUREMENT & BOM ----------------
    def _build_tab_measure(self):
        self.tab_measure.grid_columnconfigure(0, weight=3) # Canvas
        self.tab_measure.grid_columnconfigure(1, weight=2) # BOM
        self.tab_measure.grid_rowconfigure(0, weight=1)

        # Left: Map controls & drawing canvas
        map_container = ctk.CTkFrame(self.tab_measure)
        map_container.grid(row=0, column=0, sticky="nsew", padx=(5, 10), pady=5)
        map_container.grid_rowconfigure(1, weight=1)
        map_container.grid_columnconfigure(0, weight=1)

        # Overhead fetch bar
        search_bar = ctk.CTkFrame(map_container, fg_color="transparent")
        search_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        self.entry_address = ctk.CTkEntry(search_bar, placeholder_text="Enter Job Address (e.g. 690 Dogwood Ln, Buncombe County, NC)...", width=380)
        self.entry_address.pack(side="left", padx=(0, 5), fill="x", expand=True)
        self.entry_address.insert(0, "690 Dogwood Lane, Buncombe County, NC")

        self.btn_fetch_map = ctk.CTkButton(search_bar, text="🛰️ Fetch Overhead", width=140, command=self.start_satellite_fetch)
        self.btn_fetch_map.pack(side="left", padx=5)

        self.btn_zoom_in = ctk.CTkButton(search_bar, text="+", width=35, command=lambda: self.adjust_zoom(1))
        self.btn_zoom_in.pack(side="left", padx=2)
        self.btn_zoom_out = ctk.CTkButton(search_bar, text="-", width=35, command=lambda: self.adjust_zoom(-1))
        self.btn_zoom_out.pack(side="left", padx=2)

        # Interactive Canvas
        self.canvas = tk.Canvas(map_container, bg="#1A1A1A", highlightthickness=1, highlightbackground="#333333")
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        # Canvas tools & calibration
        tool_bar = ctk.CTkFrame(map_container, fg_color="transparent")
        tool_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))

        self.btn_close_poly = ctk.CTkButton(tool_bar, text="📐 Close & Calculate", fg_color="#2E7D32", hover_color="#1B5E20", command=self.close_polygon)
        self.btn_close_poly.pack(side="left", padx=5)

        self.btn_clear_canvas = ctk.CTkButton(tool_bar, text="Clear Pins", fg_color="#C62828", hover_color="#8E0000", width=90, command=self.clear_canvas)
        self.btn_clear_canvas.pack(side="left", padx=5)

        ctk.CTkLabel(tool_bar, text="Scale (Px/Ft):").pack(side="left", padx=(10, 2))
        self.scale_var = ctk.StringVar(value="5.0")
        self.entry_scale = ctk.CTkEntry(tool_bar, textvariable=self.scale_var, width=50)
        self.entry_scale.pack(side="left", padx=2)
        self.entry_scale.bind("<KeyRelease>", lambda e: self.recalculate_bom())

        ctk.CTkLabel(tool_bar, text="Pitch:").pack(side="left", padx=(10, 2))
        self.pitch_combo = ctk.CTkComboBox(tool_bar, values=list(self.pitch_multipliers.keys()), width=140, command=lambda _: self.recalculate_bom())
        self.pitch_combo.set("Moderate (6/12)")
        self.pitch_combo.pack(side="left", padx=2)

        # Right: Best Buy Metals Live BOM
        bom_container = ctk.CTkFrame(self.tab_measure)
        bom_container.grid(row=0, column=1, sticky="nsew", padx=(5, 5), pady=5)
        bom_container.grid_rowconfigure(2, weight=1)
        bom_container.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(bom_container, text="BEST BUY METALS - REAL-TIME BOM", font=("Arial", 16, "bold")).grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        config_bar = ctk.CTkFrame(bom_container, fg_color="#2A2A2A")
        config_bar.grid(row=1, column=0, sticky="ew", padx=15, pady=5)
        config_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(config_bar, text="Metal Profile:").grid(row=0, column=0, padx=8, pady=4, sticky="w")
        self.profile_combo = ctk.CTkComboBox(config_bar, values=list(self.pricing_table.keys()), width=240, command=lambda _: self.recalculate_bom())
        self.profile_combo.set("26ga Standing Seam (16in panel)")
        self.profile_combo.grid(row=0, column=1, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(config_bar, text="Panel Overlap (in):").grid(row=1, column=0, padx=8, pady=4, sticky="w")
        self.overlap_var = ctk.StringVar(value="4.0")
        self.entry_overlap = ctk.CTkEntry(config_bar, textvariable=self.overlap_var, width=90)
        self.entry_overlap.grid(row=1, column=1, padx=8, pady=4, sticky="w")
        self.entry_overlap.bind("<KeyRelease>", lambda e: self.recalculate_bom())

        ctk.CTkLabel(config_bar, text="Cut Scrap Allowance:").grid(row=2, column=0, padx=8, pady=4, sticky="w")
        self.waste_combo = ctk.CTkComboBox(config_bar, values=["10%", "12%", "15%", "20%"], width=90, command=lambda _: self.recalculate_bom())
        self.waste_combo.set("10%")
        self.waste_combo.grid(row=2, column=1, padx=8, pady=4, sticky="w")

        self.txt_bom = ctk.CTkTextbox(bom_container, font=("Consolas", 12))
        self.txt_bom.grid(row=2, column=0, sticky="nsew", padx=15, pady=10)

        self.total_card = ctk.CTkFrame(bom_container, fg_color="#1E3A1E")
        self.total_card.grid(row=3, column=0, sticky="ew", padx=15, pady=(0, 15))
        self.lbl_grand_total = ctk.CTkLabel(self.total_card, text="ESTIMATED TOTAL: $0.00", font=("Arial", 16, "bold"), text_color="#66BB6A")
        self.lbl_grand_total.pack(padx=15, pady=12)

        self.recalculate_bom()

    # ---------------- TAB 3 & 4: NC CODES & PHASES (GATED) ----------------
    def _build_tab_codes(self):
        self.tab_codes.grid_columnconfigure(0, weight=1)
        self.tab_codes.grid_rowconfigure(0, weight=1)
        self.txt_codes = ctk.CTkTextbox(self.tab_codes, font=("Consolas", 12))
        self.txt_codes.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.txt_codes.insert("0.0", "=== LOCKED ===\nComplete Quote -> Acceptance -> Contract (QAC) in Stage 1 to unlock NC Building Code and Permitting requirements.")
        self.txt_codes.configure(state="disabled")

    def _build_tab_phases(self):
        self.tab_phases.grid_columnconfigure(0, weight=1)
        self.tab_phases.grid_rowconfigure(0, weight=1)
        self.txt_phases = ctk.CTkTextbox(self.tab_phases, font=("Consolas", 12))
        self.txt_phases.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.txt_phases.insert("0.0", "=== LOCKED ===\nComplete Quote -> Acceptance -> Contract (QAC) in Stage 1 to unlock Phase Execution and Staging checklists.")
        self.txt_phases.configure(state="disabled")

    # ---------------- SATELLITE FETCHING LOGIC ----------------
    def adjust_zoom(self, delta):
        self.current_zoom = max(16, min(21, self.current_zoom + delta))
        self.start_satellite_fetch()

    def start_satellite_fetch(self):
        address = self.entry_address.get().strip()
        if not address:
            messagebox.showwarning("Missing Address", "Enter a valid job address.")
            return

        self.btn_fetch_map.configure(state="disabled", text="Fetching...")
        threading.Thread(target=self._fetch_map_worker, args=(address,), daemon=True).start()

    def _fetch_map_worker(self, address):
        """Fetches Google Maps Static Satellite image with automated ArcGIS/OSM fallback."""
        maps_key = self.maps_key_entry.get().strip()
        img = None

        # 1. Primary: Google Maps Static Satellite API
        if maps_key:
            try:
                encoded = urllib.parse.quote(address)
                url = f"https://maps.googleapis.com/maps/api/staticmap?center={encoded}&zoom={self.current_zoom}&size=700x520&maptype=satellite&key={maps_key}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    img_data = response.read()
                    img = Image.open(io.BytesIO(img_data))
            except Exception as e:
                print(f"Google Maps Fetch Failed: {e}. Falling back to Open Satellite.")

        # 2. Free Fallback: Nominatim Geocoding + ArcGIS High-Res Satellite
        if img is None:
            try:
                geo_url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(address)}&format=json&limit=1"
                req = urllib.request.Request(geo_url, headers={'User-Agent': 'StevesRoofingEstimatorApp/1.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    geo_data = json.loads(response.read().decode('utf-8'))

                if geo_data:
                    lat = float(geo_data[0]['lat'])
                    lon = float(geo_data[0]['lon'])

                    # Calculate bounding box from zoom level
                    span = 0.0035 / (2 ** (self.current_zoom - 18))
                    bbox = f"{lon-span},{lat-span*0.75},{lon+span},{lat+span*0.75}"
                    arcgis_url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export?bbox={bbox}&bboxSR=4326&imageSR=4326&size=700,520&f=image"
                    
                    req_map = urllib.request.Request(arcgis_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req_map, timeout=10) as map_resp:
                        img = Image.open(io.BytesIO(map_resp.read()))
            except Exception as e:
                print(f"Fallback Satellite failed: {e}")

        self.after(0, self._render_map_on_canvas, img)

    def _render_map_on_canvas(self, img):
        self.btn_fetch_map.configure(state="normal", text="🛰️ Fetch Overhead")
        if img is None:
            messagebox.showerror("Map Error", "Could not retrieve satellite imagery for this address.\nVerify your connection or provide a Google Maps API Key.")
            return

        self.clear_canvas()
        canvas_w = self.canvas.winfo_width() or 700
        canvas_h = self.canvas.winfo_height() or 520
        img = img.resize((canvas_w, canvas_h), Image.Resampling.LANCZOS)
        self.bg_photo = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor="nw", image=self.bg_photo)

    # ---------------- INTERACTIVE CANVAS DRAWING ----------------
    def on_canvas_click(self, event):
        if self.closed:
            return

        x, y = event.x, event.y
        self.points.append((x, y))

        marker = self.canvas.create_oval(x-4, y-4, x+4, y+4, fill="#00E5FF", outline="white")
        self.point_markers.append(marker)

        if len(self.points) > 1:
            prev = self.points[-2]
            self.canvas.create_line(prev[0], prev[1], x, y, fill="#00E5FF", width=2, tags="perimeter_line")

    def close_polygon(self):
        if len(self.points) < 3:
            messagebox.showwarning("Incomplete Shape", "Click at least 3 corner points around the roof.")
            return

        self.closed = True
        first, last = self.points[0], self.points[-1]
        self.canvas.create_line(last[0], last[1], first[0], first[1], fill="#00E5FF", width=2, tags="perimeter_line")

        poly_coords = [coord for pt in self.points for coord in pt]
        self.polygon_id = self.canvas.create_polygon(poly_coords, fill="#00E5FF", stipple="gray25", outline="#00E5FF", width=2)

        self.recalculate_bom()

    def clear_canvas(self):
        self.canvas.delete("all")
        if self.bg_photo:
            self.canvas.create_image(0, 0, anchor="nw", image=self.bg_photo)
        self.points.clear()
        self.point_markers.clear()
        self.polygon_id = None
        self.closed = False
        self.recalculate_bom()

    # ---------------- DYNAMIC BOM ENGINE ----------------
    def recalculate_bom(self):
        if len(self.points) < 3:
            self.txt_bom.configure(state="normal")
            self.txt_bom.delete("0.0", "end")
            self.txt_bom.insert("0.0", "Trace roof perimeter on the canvas and click 'Close & Calculate' to generate Best Buy Metals Bill of Materials.")
            self.txt_bom.configure(state="disabled")
            self.lbl_grand_total.configure(text="ESTIMATED TOTAL: $0.00")
            return

        try:
            px_per_ft = float(self.scale_var.get().strip())
            overlap_in = float(self.overlap_var.get().strip())
            if px_per_ft <= 0:
                return
        except ValueError:
            return

        # Shoelace Area Formula
        n = len(self.points)
        area_px = 0.5 * abs(sum(
            self.points[i][0] * self.points[(i + 1) % n][1] - 
            self.points[(i + 1) % n][0] * self.points[i][1] 
            for i in range(n)
        ))

        sqft_flat = area_px / (px_per_ft ** 2)
        pitch_mult = self.pitch_multipliers.get(self.pitch_combo.get(), 1.0)
        sqft_pitched = sqft_flat * pitch_mult
        waste_pct = float(self.waste_combo.get().replace("%", "")) / 100.0

        # Perimeter for trim packages
        perimeter_px = sum(math.dist(self.points[i], self.points[(i + 1) % n]) for i in range(n))
        perimeter_ft = perimeter_px / px_per_ft

        # Best Buy Metals Catalog Pricing
        selected_profile = self.profile_combo.get()
        spec = self.pricing_table[selected_profile]
        nominal_width_in = spec["nominal_width_in"]
        if overlap_in < 0 or overlap_in >= nominal_width_in:
            return
        effective_width_in = nominal_width_in - overlap_in
        overlap_factor = nominal_width_in / effective_width_in
        sqft_order_before_overlap = sqft_pitched * (1.0 + waste_pct)
        sqft_order = sqft_order_before_overlap * overlap_factor
        overlap_sqft = sqft_order - sqft_order_before_overlap
        squares = sqft_order / 100.0
        cost_metal = sqft_order * spec["unit_cost_sqft"]

        rolls_underlayment = math.ceil(sqft_order / 1000.0)
        cost_underlayment = rolls_underlayment * 95.0

        rolls_ice = max(1, math.ceil((perimeter_ft * 3.0) / 200.0))
        cost_ice = rolls_ice * 110.0

        sticks_trim = math.ceil(perimeter_ft / 10.0)
        cost_trim = sticks_trim * 28.0

        boxes_clips = max(1, math.ceil(squares / 5.0))
        cost_clips = boxes_clips * 75.0

        grand_total = cost_metal + cost_underlayment + cost_ice + cost_trim + cost_clips

        bom_text = (
            f"MEASUREMENT SPECIFICATIONS:\n"
            f"--------------------------------------------------\n"
            f"• Satellite Flat Footprint:    {sqft_flat:,.1f} sq ft\n"
            f"• Pitch Multiplier:            x{pitch_mult:.3f} ({self.pitch_combo.get().split()[0]})\n"
            f"• Actual Pitch Surface:        {sqft_pitched:,.1f} sq ft\n"
            f"• Order Before Overlap:        {sqft_order_before_overlap:,.1f} sq ft\n"
            f"• Panel Coverage:               {nominal_width_in:.1f} in nominal - {overlap_in:.1f} in overlap = {effective_width_in:.1f} in effective\n"
            f"• Overlap Material Allowance:   +{overlap_sqft:,.1f} sq ft ({(overlap_factor - 1.0) * 100:.1f}%)\n"
            f"• Total Order (+{int(waste_pct*100)}% scrap + overlap): {sqft_order:,.1f} sq ft ({squares:.2f} Sq)\n"
            f"• Net Perimeter (Trim Run):    {perimeter_ft:,.1f} lin ft\n\n"
            f"BEST BUY METALS ITEMIZED ORDER:\n"
            f"--------------------------------------------------\n"
            f"[1] Panels ({selected_profile.split('(')[0].strip()}):\n"
            f"    {sqft_order:,.1f} sq ft @ ${spec['unit_cost_sqft']:.2f}/sq ft        = ${cost_metal:,.2f}\n\n"
            f"[2] Synthetic Underlayment:\n"
            f"    {rolls_underlayment} roll(s) (1,000 sq ft ea)          = ${cost_underlayment:,.2f}\n\n"
            f"[3] Ice & Water Shield (Eaves/Valleys):\n"
            f"    {rolls_ice} roll(s) (200 sq ft ea)            = ${cost_ice:,.2f}\n\n"
            f"[4] Perimeter Trim (10-ft sticks):\n"
            f"    {sticks_trim} sticks @ $28.00/stick            = ${cost_trim:,.2f}\n\n"
            f"[5] Fasteners & Concealed Clips:\n"
            f"    {boxes_clips} box(es) @ $75.00/box             = ${cost_clips:,.2f}\n"
            f"--------------------------------------------------\n"
            f"TOTAL MATERIAL PROCUREMENT:            ${grand_total:,.2f}\n"
        )

        self.txt_bom.configure(state="normal")
        self.txt_bom.delete("0.0", "end")
        self.txt_bom.insert("0.0", bom_text)
        self.txt_bom.configure(state="disabled")

        self.lbl_grand_total.configure(text=f"ESTIMATED TOTAL: ${grand_total:,.2f}")

    # ---------------- STAGE 1: QAC WORKFLOW & AI INTEGRATION ----------------
    def action_draft_quote(self):
        notes = self.txt_notes.get("0.0", "end").strip()
        api_key = self.gemini_key_entry.get().strip()

        if not notes:
            messagebox.showwarning("Missing Notes", "Please provide customer field notes.")
            return
        if not api_key:
            messagebox.showwarning(
                "Missing Gemini API Key",
                "Enter a Gemini API key in the Credential Vault before drafting a quote."
            )
            return

        self.btn_gen_quote.configure(state="disabled", text="Generating...")
        self.txt_quote_preview.delete("0.0", "end")
        self.txt_quote_preview.insert("0.0", "Contacting Gemini API...\nDrafting professional proposal...")

        threading.Thread(target=self._ai_quote_worker, args=(api_key, notes), daemon=True).start()

    def _ai_quote_worker(self, api_key, notes):
        prompt = (
            "You are an expert roofing estimator for 'Steve's Roofing' in North Carolina. "
            "Transform the following raw field notes into a clean, professional, itemized proposal.\n"
            "Include:\n"
            "1. Summary of Client, Address, and Calculated Roof Squares (Factor in pitch multipliers & 10% scrap waste).\n"
            "2. Detailed Scope of Work (Tear-off, Prep, Materials, Flashing, Cleanup).\n"
            "3. Itemized Cost Estimate (Materials, Labor, Disposal, NC Permit fees).\n"
            "4. Payment Terms & Signable Acceptance Agreement (QAC contract lock).\n\n"
            f"FIELD NOTES:\n{notes}"
        )

        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )
            output_text = response.text
            success = bool(output_text and output_text.strip())
        except Exception as e:
            output_text = f"[QUOTE FAILED]\n{str(e)}\n\nCheck the Gemini API key and connection, then try again."
            success = False

        self.after(0, self._render_quote_result, output_text, success)

    def _render_quote_result(self, text, success):
        self.txt_quote_preview.delete("0.0", "end")
        self.txt_quote_preview.insert("0.0", text)
        self.btn_gen_quote.configure(state="normal", text="⚡ Draft AI Quote")

        if success:
            self.quote_ready = True
            self.accepted = False
            self.contract_signed = False
            self.accepted_at = None
            self.contract_signed_at = None
            self.customer_signature_entry.delete(0, "end")
            self.contractor_signature_entry.delete(0, "end")
            self.quote_drafted_at = self._utc_now()
            self._record_audit("Quote drafted")
            self.lbl_quote.configure(text="[OK] 1. Quote Drafted", text_color="#4CAF50")
            self.lbl_accept.configure(text="[  ] 2. Customer Accepted", text_color="#A0A0A0")
            self.lbl_contract.configure(text="[  ] 3. Contract Signed", text_color="#A0A0A0")
            self.btn_accept.configure(state="normal")
            self.btn_sign.configure(state="disabled")
            self.status_card.configure(fg_color="#2A2A2A")
            self.status_text.configure(text="GATE STATUS:\nLOCKED (RED)", text_color="#FF4C4C")
        else:
            self.quote_ready = False
            self.lbl_quote.configure(text="[  ] 1. Quote Drafted", text_color="#A0A0A0")
            self.btn_accept.configure(state="disabled")

    def action_mark_accepted(self):
        customer_signature = self.customer_signature_entry.get().strip()
        if not self.quote_ready:
            messagebox.showwarning("Quote Required", "Draft a successful quote before accepting it.")
            return
        if not customer_signature:
            messagebox.showwarning("Customer Signature Required", "Enter the customer's typed signature before marking the quote accepted.")
            return

        self.accepted = True
        self.accepted_at = self._utc_now()
        self._record_audit(f"Quote accepted by {customer_signature}")
        self.lbl_accept.configure(text="[OK] 2. Customer Accepted", text_color="#4CAF50")
        self.btn_sign.configure(state="normal")
        self.btn_accept.configure(state="disabled")

    def action_sign_contract(self):
        contractor_signature = self.contractor_signature_entry.get().strip()
        if not self.accepted:
            messagebox.showwarning("Acceptance Required", "Record customer acceptance before signing the contract.")
            return
        if not contractor_signature:
            messagebox.showwarning("Contractor Signature Required", "Enter the contractor's typed signature before signing the contract.")
            return

        self.contract_signed = True
        self.contract_signed_at = self._utc_now()
        self._record_audit(f"Contract signed by {contractor_signature}")
        self.lbl_contract.configure(text="[OK] 3. Contract Signed", text_color="#4CAF50")
        self.btn_sign.configure(state="disabled")

        # Unlock Green Light & Content
        self.status_card.configure(fg_color="#143D1A")
        self.status_text.configure(text="GATE STATUS:\nGREEN LIGHT (CLEAR)", text_color="#4EFA75")

        # Unlock NC Codes Tab
        self.txt_codes.configure(state="normal")
        self.txt_codes.delete("0.0", "end")
        self.txt_codes.insert("0.0", (
            "======================================================================\n"
            "NORTH CAROLINA RESIDENTIAL CODE (NCRC) - ROOF ASSEMBLY COMPLIANCE\n"
            "======================================================================\n\n"
            "[+] AHJ JURISDICTION: Buncombe County Permitting & Inspections\n"
            "    - Building Permit: REQUIRED for structural re-roofing / material transition.\n"
            "    - Decking Inspection: Mandatory prior to underlayment application.\n\n"
            "[+] TECHNICAL CODE REQUIREMENTS:\n"
            "    - Wind Resistance (NCRC R905.10): Fasteners must withstand local design wind\n"
            "      speeds (115 mph baseline in western NC).\n"
            "    - Underlayment (NCRC R905.1.1): Self-adhering polymer-modified bitumen sheet\n"
            "      required at eaves and valleys (ice & water shield) where pitch <= 6/12.\n"
            "    - Metal Panel Standard: Must comply with ASTM A792 (55% Al-Zn Galvalume).\n"
        ))
        self.txt_codes.configure(state="disabled")

        # Unlock Phase Execution Tab
        self.txt_phases.configure(state="normal")
        self.txt_phases.delete("0.0", "end")
        self.txt_phases.insert("0.0", (
            "======================================================================\n"
            "PHASED EXECUTION: MATERIALS, TOOLS & STAGING MANIFEST\n"
            "======================================================================\n\n"
            "PHASE 1: TEAR-OFF & DEMOLITION\n"
            "  [ ] Tools: Pitch hoes, roofing shovels, magnetic sweepers, tarps\n"
            "  [ ] Disposal: 20-yard roll-off dumpster staged driveway-side\n"
            "  [ ] Safety: OSHA harness kits, rope grabs, ridge anchor brackets\n\n"
            "PHASE 2: DECK PREPARATION & UNDERLAYMENT\n"
            "  [ ] Materials: 7/16\" OSB sheathing buffer, 8d ring-shank nails\n"
            "  [ ] Barriers: High-temp synthetic underlayment + ice & water shield\n\n"
            "PHASE 3: STANDING SEAM INSTALLATION\n"
            "  [ ] Metal Panels: Custom cut Galvalume 26ga standing seam\n"
            "  [ ] Fasteners: #10 pancake-head concealed clip screws\n"
            "  [ ] Trim: Custom bent drip edge, rake, ridge cap, butyl tape, poly sealant\n"
        ))
        self.txt_phases.configure(state="disabled")

        messagebox.showinfo("Green Light Cleared", "QAC is 100% complete!\nPermits, Building Codes, and Phase Execution tabs are now fully unlocked.")

    def reset_workflow(self):
        self.quote_ready = False
        self.accepted = False
        self.contract_signed = False
        self.quote_drafted_at = None
        self.accepted_at = None
        self.contract_signed_at = None
        self.audit_log = []
        self.customer_signature_entry.delete(0, "end")
        self.contractor_signature_entry.delete(0, "end")

        self.lbl_quote.configure(text="[  ] 1. Quote Drafted", text_color="#A0A0A0")
        self.lbl_accept.configure(text="[  ] 2. Customer Accepted", text_color="#A0A0A0")
        self.lbl_contract.configure(text="[  ] 3. Contract Signed", text_color="#A0A0A0")

        self.btn_gen_quote.configure(state="normal")
        self.btn_accept.configure(state="disabled")
        self.btn_sign.configure(state="disabled")

        self.status_card.configure(fg_color="#2A2A2A")
        self.status_text.configure(text="GATE STATUS:\nLOCKED (RED)", text_color="#FF4C4C")

        self.txt_codes.configure(state="normal")
        self.txt_codes.delete("0.0", "end")
        self.txt_codes.insert("0.0", "=== LOCKED ===\nComplete Quote -> Acceptance -> Contract (QAC) in Stage 1 to unlock NC Building Code and Permitting requirements.")
        self.txt_codes.configure(state="disabled")

        self.txt_phases.configure(state="normal")
        self.txt_phases.delete("0.0", "end")
        self.txt_phases.insert("0.0", "=== LOCKED ===\nComplete Quote -> Acceptance -> Contract (QAC) in Stage 1 to unlock Phase Execution and Staging checklists.")
        self.txt_phases.configure(state="disabled")

    def export_job_record(self):
        address = self.entry_address.get().strip() or "Unspecified address"
        safe_name = "_".join(address.split())[:60]
        file_path = filedialog.asksaveasfilename(
            title="Export Job Record",
            defaultextension=".txt",
            initialfile=f"roofing_job_{safe_name}.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not file_path:
            return

        record = (
            "STEVE'S ROOFING - JOB RECORD\n"
            "============================================================\n"
            f"Address: {address}\n"
            f"Workflow status: {'Contract signed' if self.contract_signed else 'Quote drafted' if self.quote_ready else 'Not started'}\n\n"
            "CUSTOMER FIELD NOTES\n"
            "------------------------------------------------------------\n"
            f"{self.txt_notes.get('0.0', 'end').strip()}\n\n"
            "PROPOSAL / CONTRACT\n"
            "------------------------------------------------------------\n"
            f"{self.txt_quote_preview.get('0.0', 'end').strip()}\n\n"
            "MATERIALS / BOM\n"
            "------------------------------------------------------------\n"
            f"{self.txt_bom.get('0.0', 'end').strip()}\n\n"
            "BUILDING CODES\n"
            "------------------------------------------------------------\n"
            f"{self.txt_codes.get('0.0', 'end').strip()}\n\n"
            "EXECUTION PHASES\n"
            "------------------------------------------------------------\n"
            f"{self.txt_phases.get('0.0', 'end').strip()}\n"
            "\nAUDIT TRAIL\n"
            "------------------------------------------------------------\n"
            f"{json.dumps(self.audit_log, indent=2)}\n"
        )

        try:
            with open(file_path, "w", encoding="utf-8") as output_file:
                output_file.write(record)
        except OSError as error:
            messagebox.showerror("Export Failed", f"Could not save the job record.\n\n{error}")
            return

        messagebox.showinfo("Job Record Exported", f"Saved job record to:\n{file_path}")

    def _job_data(self):
        return {
            "address": self.entry_address.get().strip(),
            "notes": self.txt_notes.get("0.0", "end").strip(),
            "quote_preview": self.txt_quote_preview.get("0.0", "end").strip(),
            "points": self.points,
            "closed": self.closed,
            "scale": self.scale_var.get(),
            "pitch": self.pitch_combo.get(),
            "profile": self.profile_combo.get(),
            "overlap": self.overlap_var.get(),
            "waste": self.waste_combo.get(),
            "current_zoom": self.current_zoom,
            "quote_ready": self.quote_ready,
            "accepted": self.accepted,
            "contract_signed": self.contract_signed,
            "customer_signature": self.customer_signature_entry.get().strip(),
            "contractor_signature": self.contractor_signature_entry.get().strip(),
            "quote_drafted_at": self.quote_drafted_at,
            "accepted_at": self.accepted_at,
            "contract_signed_at": self.contract_signed_at,
            "audit_log": self.audit_log,
            "codes": self.txt_codes.get("0.0", "end").strip(),
            "phases": self.txt_phases.get("0.0", "end").strip()
        }

    def save_job(self):
        address = self.entry_address.get().strip() or "unspecified_address"
        safe_name = "_".join(address.split())[:60]
        file_path = filedialog.asksaveasfilename(
            title="Save Roofing Job",
            defaultextension=".json",
            initialfile=f"roofing_job_{safe_name}.json",
            filetypes=[("Roofing job files", "*.json"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as output_file:
                json.dump(self._job_data(), output_file, indent=2)
        except OSError as error:
            messagebox.showerror("Save Failed", f"Could not save the job.\n\n{error}")
            return

        messagebox.showinfo("Job Saved", f"Saved job to:\n{file_path}")

    def _read_job_file(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as input_file:
                job = json.load(input_file)
            if not isinstance(job, dict):
                raise ValueError("The selected file does not contain a job record.")
            return job
        except (OSError, json.JSONDecodeError, ValueError) as error:
            messagebox.showerror("Load Failed", f"Could not load the job.\n\n{error}")
            return None

    def _populate_job_inputs(self, job):
        self.entry_address.delete(0, "end")
        self.entry_address.insert(0, job.get("address", ""))
        self.txt_notes.delete("0.0", "end")
        self.txt_notes.insert("0.0", job.get("notes", ""))
        self.txt_quote_preview.delete("0.0", "end")
        self.txt_quote_preview.insert("0.0", job.get("quote_preview", ""))
        self.customer_signature_entry.delete(0, "end")
        self.customer_signature_entry.insert(0, job.get("customer_signature", ""))
        self.contractor_signature_entry.delete(0, "end")
        self.contractor_signature_entry.insert(0, job.get("contractor_signature", ""))

        self.scale_var.set(str(job.get("scale", "5.0")))
        self.pitch_combo.set(job.get("pitch", "Moderate (6/12)"))
        self.profile_combo.set(job.get("profile", "26ga Standing Seam (16in panel)"))
        self.overlap_var.set(str(job.get("overlap", "4.0")))
        self.waste_combo.set(job.get("waste", "10%"))
        self.current_zoom = int(job.get("current_zoom", 19))

    def _restore_canvas_points(self, job):
        self.clear_canvas()
        loaded_points = job.get("points", [])
        self.points = []
        if isinstance(loaded_points, list):
            for point in loaded_points:
                if isinstance(point, (list, tuple)) and len(point) == 2:
                    self.points.append(tuple(point))
        self.closed = bool(job.get("closed", False))
        for index, point in enumerate(self.points):
            x, y = point
            marker = self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#00E5FF", outline="white")
            self.point_markers.append(marker)
            if index > 0:
                previous = self.points[index - 1]
                self.canvas.create_line(previous[0], previous[1], x, y, fill="#00E5FF", width=2, tags="perimeter_line")
        self._restore_polygon_overlay()

    def _restore_polygon_overlay(self):
        if not self.closed or len(self.points) < 3:
            return
        first, last = self.points[0], self.points[-1]
        self.canvas.create_line(last[0], last[1], first[0], first[1], fill="#00E5FF", width=2, tags="perimeter_line")
        poly_coords = [coord for point in self.points for coord in point]
        self.polygon_id = self.canvas.create_polygon(poly_coords, fill="#00E5FF", stipple="gray25", outline="#00E5FF", width=2)

    def _populate_job_status(self, job):
        self.quote_ready = bool(job.get("quote_ready", False))
        self.accepted = bool(job.get("accepted", False))
        self.contract_signed = bool(job.get("contract_signed", False))
        self.quote_drafted_at = job.get("quote_drafted_at")
        self.accepted_at = job.get("accepted_at")
        self.contract_signed_at = job.get("contract_signed_at")
        raw_audit = job.get("audit_log", [])
        self.audit_log = raw_audit if isinstance(raw_audit, list) else []

        self.txt_codes.configure(state="normal")
        self.txt_codes.delete("0.0", "end")
        self.txt_codes.insert("0.0", job.get("codes", ""))
        self.txt_codes.configure(state="disabled")
        self.txt_phases.configure(state="normal")
        self.txt_phases.delete("0.0", "end")
        self.txt_phases.insert("0.0", job.get("phases", ""))
        self.txt_phases.configure(state="disabled")

    def load_job(self):
        file_path = filedialog.askopenfilename(
            title="Load Roofing Job",
            filetypes=[("Roofing job files", "*.json"), ("All files", "*.*")]
        )
        if not file_path:
            return

        job = self._read_job_file(file_path)
        if not job:
            return

        self._populate_job_inputs(job)
        self._restore_canvas_points(job)
        self._populate_job_status(job)
        self._restore_workflow_controls()
        self.recalculate_bom()
        messagebox.showinfo("Job Loaded", f"Loaded job from:\n{file_path}")

    @staticmethod
    def _utc_now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _record_audit(self, event):
        self.audit_log.append({"timestamp": self._utc_now(), "event": event})

    def _configure_step_label(self, widget, step_number, step_name, is_done):
        prefix = "[OK]" if is_done else "[  ]"
        color = "#4CAF50" if is_done else "#A0A0A0"
        widget.configure(text=f"{prefix} {step_number}. {step_name}", text_color=color)

    @staticmethod
    def _resolve_button_state(is_complete, prerequisite_done):
        if is_complete or not prerequisite_done:
            return "disabled"
        return "normal"

    def _update_gate_status_card(self, is_contract_signed):
        if is_contract_signed:
            self.status_card.configure(fg_color="#143D1A")
            self.status_text.configure(text="GATE STATUS:\nGREEN LIGHT (CLEAR)", text_color="#4EFA75")
        else:
            self.status_card.configure(fg_color="#2A2A2A")
            self.status_text.configure(text="GATE STATUS:\nLOCKED (RED)", text_color="#FF4C4C")

    def _restore_workflow_controls(self):
        self._configure_step_label(self.lbl_quote, 1, "Quote Drafted", self.quote_ready)
        self._configure_step_label(self.lbl_accept, 2, "Customer Accepted", self.accepted)
        self._configure_step_label(self.lbl_contract, 3, "Contract Signed", self.contract_signed)
        self.btn_accept.configure(state=self._resolve_button_state(self.accepted, self.quote_ready))
        self.btn_sign.configure(state=self._resolve_button_state(self.contract_signed, self.accepted))
        self._update_gate_status_card(self.contract_signed)

if __name__ == "__main__":
    app = UnifiedRoofingOS()
    app.mainloop()