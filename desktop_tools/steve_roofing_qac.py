import customtkinter as ctk
from tkinter import messagebox

# Set theme styling
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class SteveRoofingApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Steve's Roofing OS - QAC Workflow & Field Estimator")
        self.geometry("1100x720")
        self.minsize(950, 650)

        # ---------------- State Variables ----------------
        self.quote_ready = False
        self.accepted = False
        self.contract_signed = False

        # Grid configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_panel()

    # ---------------- UI BUILDERS ----------------
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar.grid_rowconfigure(8, weight=1)

        title_label = ctk.CTkLabel(
            self.sidebar, 
            text="STEVE'S ROOFING\nOPERATIONS", 
            font=("Arial", 18, "bold")
        )
        title_label.grid(row=0, column=0, padx=20, pady=(25, 20))

        # Pipeline progress indicators
        status_header = ctk.CTkLabel(self.sidebar, text="PIPELINE GATE", font=("Arial", 12, "bold"), text_color="gray")
        status_header.grid(row=1, column=0, padx=20, pady=(10, 5), sticky="w")

        self.lbl_quote = ctk.CTkLabel(self.sidebar, text="[  ] 1. Quote Drafted", text_color="#A0A0A0", anchor="w")
        self.lbl_quote.grid(row=2, column=0, padx=20, pady=4, sticky="w")

        self.lbl_accept = ctk.CTkLabel(self.sidebar, text="[  ] 2. Customer Accepted", text_color="#A0A0A0", anchor="w")
        self.lbl_accept.grid(row=3, column=0, padx=20, pady=4, sticky="w")

        self.lbl_contract = ctk.CTkLabel(self.sidebar, text="[  ] 3. Contract Signed", text_color="#A0A0A0", anchor="w")
        self.lbl_contract.grid(row=4, column=0, padx=20, pady=4, sticky="w")

        # Operational Status Indicator Card
        self.status_card = ctk.CTkFrame(self.sidebar, fg_color="#2A2A2A")
        self.status_card.grid(row=5, column=0, padx=15, pady=25, sticky="ew")

        self.status_text = ctk.CTkLabel(
            self.status_card, 
            text="GATE STATUS:\nLOCKED (RED)", 
            font=("Arial", 13, "bold"), 
            text_color="#FF4C4C"
        )
        self.status_text.pack(padx=10, pady=12)

        # Reset button
        self.btn_reset = ctk.CTkButton(
            self.sidebar, 
            text="Reset Job Workflow", 
            fg_color="#3A3A3A", 
            hover_color="#505050",
            command=self.reset_workflow
        )
        self.btn_reset.grid(row=9, column=0, padx=20, pady=20)

    def _build_main_panel(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_container.grid_rowconfigure(1, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # Top section: Job intake and QAC controls
        self._build_qac_intake_card()

        # Bottom section: Unlocked execution details
        self._build_execution_view()

    def _build_qac_intake_card(self):
        intake_frame = ctk.CTkFrame(self.main_container)
        intake_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        intake_frame.grid_columnconfigure(1, weight=1)

        header = ctk.CTkLabel(intake_frame, text="Stage 1: Job Intake & QAC Validation", font=("Arial", 16, "bold"))
        header.grid(row=0, column=0, columnspan=3, padx=15, pady=(12, 10), sticky="w")

        # Customer notes input
        lbl_notes = ctk.CTkLabel(intake_frame, text="Customer Raw Notes / Field Log:")
        lbl_notes.grid(row=1, column=0, padx=15, pady=5, sticky="nw")

        self.txt_notes = ctk.CTkTextbox(intake_frame, height=90)
        self.txt_notes.grid(row=1, column=1, columnspan=2, padx=(0, 15), pady=5, sticky="ew")
        self.txt_notes.insert("0.0", "Customer: Marcus Vance\nAddress: 412 Dogwood Lane, Buncombe County, NC\nScope: Remove existing asphalt shingles, install standing seam metal roof (26 ga, Galvalume). Pitch: 6/12.")

        # Interactive QAC action buttons
        action_bar = ctk.CTkFrame(intake_frame, fg_color="transparent")
        action_bar.grid(row=2, column=0, columnspan=3, padx=15, pady=12, sticky="ew")

        self.btn_generate_quote = ctk.CTkButton(
            action_bar, 
            text="1. Draft Quote", 
            command=self.action_draft_quote
        )
        self.btn_generate_quote.pack(side="left", padx=5)

        self.btn_customer_accept = ctk.CTkButton(
            action_bar, 
            text="2. Mark Accepted", 
            state="disabled", 
            command=self.action_mark_accepted
        )
        self.btn_customer_accept.pack(side="left", padx=5)

        self.btn_sign_contract = ctk.CTkButton(
            action_bar, 
            text="3. Sign Contract (QAC Gate)", 
            state="disabled", 
            command=self.action_sign_contract
        )
        self.btn_sign_contract.pack(side="left", padx=5)

    def _build_execution_view(self):
        self.tabs = ctk.CTkTabview(self.main_container)
        self.tabs.grid(row=1, column=0, sticky="nsew")

        self.tab_codes = self.tabs.add("NC Building Codes & Permits")
        self.tab_materials = self.tabs.add("Field Materials & Execution Plan")

        # Tab 1: Codes & Permits (Initially locked)
        self.txt_codes = ctk.CTkTextbox(self.tab_codes, font=("Consolas", 12))
        self.txt_codes.pack(fill="both", expand=True, padx=10, pady=10)
        self.txt_codes.insert("0.0", "=== LOCKED ===\nComplete Quote -> Acceptance -> Contract (QAC) above to unlock NC Building Code and Permitting requirements.")
        self.txt_codes.configure(state="disabled")

        # Tab 2: Materials & Tools (Initially locked)
        self.txt_materials = ctk.CTkTextbox(self.tab_materials, font=("Consolas", 12))
        self.txt_materials.pack(fill="both", expand=True, padx=10, pady=10)
        self.txt_materials.insert("0.0", "=== LOCKED ===\nComplete Quote -> Acceptance -> Contract (QAC) above to unlock material specifications and order checklists.")
        self.txt_materials.configure(state="disabled")

    # ---------------- LOGIC HANDLERS ----------------
    def action_draft_quote(self):
        notes = self.txt_notes.get("0.0", "end").strip()
        if not notes:
            messagebox.showwarning("Missing Data", "Please input customer field notes first.")
            return

        self.quote_ready = True
        self.lbl_quote.configure(text="[OK] 1. Quote Drafted", text_color="#4CAF50")
        self.btn_customer_accept.configure(state="normal")
        self.btn_generate_quote.configure(state="disabled")

    def action_mark_accepted(self):
        self.accepted = True
        self.lbl_accept.configure(text="[OK] 2. Customer Accepted", text_color="#4CAF50")
        self.btn_sign_contract.configure(state="normal")
        self.btn_customer_accept.configure(state="disabled")

    def action_sign_contract(self):
        self.contract_signed = True
        self.lbl_contract.configure(text="[OK] 3. Contract Signed", text_color="#4CAF50")
        self.btn_sign_contract.configure(state="disabled")

        # Unlock Green Light & Content
        self.trigger_green_light()

    def trigger_green_light(self):
        self.status_card.configure(fg_color="#143D1A")
        self.status_text.configure(
            text="GATE STATUS:\nGREEN LIGHT (CLEAR)", 
            text_color="#4EFA75"
        )

        # Populate NC Code Data
        self.txt_codes.configure(state="normal")
        self.txt_codes.delete("0.0", "end")
        nc_code_manifest = (
            "======================================================================\n"
            "STATE COMPLIANCE & PERMIT BRIEF: NORTH CAROLINA RESIDENTIAL CODE (NCRC)\n"
            "======================================================================\n\n"
            "[+] JURISDICTION:\n"
            "    - Local Authority Having Jurisdiction (AHJ): Buncombe County Permitting\n"
            "    - Code Base: 2018/2024 NC Residential Code, Chapter 9 (Roof Assemblies)\n\n"
            "[+] PERMIT REQUIREMENTS:\n"
            "    - Building Permit: REQUIRED for structural re-roofing or material change.\n"
            "    - Decking Inspection: Required once shingles are stripped to confirm decking\n"
            "      meets minimum 7/16-inch OSB or 1/2-inch nominal plywood nailer standards.\n\n"
            "[+] TECHNICAL CODE REQUIREMENTS:\n"
            "    - Wind Resistance (NCRC R905.10): Fasteners must resist local basic design\n"
            "      wind speed (typically 115 mph in western/central NC, higher on the coast).\n"
            "    - Underlayment (NCRC R905.1.1): Self-adhering polymer-modified bitumen sheet\n"
            "      required at eaves and valleys (ice & water shield) where pitch is 6/12 or lower.\n"
            "    - Metal Panel Standard: Must comply with ASTM A792 (55% Al-Zn alloy coated steel).\n"
        )
        self.txt_codes.insert("0.0", nc_code_manifest)
        self.txt_codes.configure(state="disabled")

        # Populate Materials & Tools
        self.txt_materials.configure(state="normal")
        self.txt_materials.delete("0.0", "end")
        materials_manifest = (
            "======================================================================\n"
            "PHASED EXECUTION: MATERIALS, TOOLS & STAGING LIST\n"
            "======================================================================\n\n"
            "PHASE 1: TEAR-OFF & DEMOLITION\n"
            "----------------------------------------------------------------------\n"
            "  [ ] Tools: Pitch hoes, roofing shovels, magnetic sweepers, tarp runners\n"
            "  [ ] Dumpster: 20-yard roll-off (positioned under north drip-edge)\n"
            "  [ ] Safety: 50-ft OSHA lifeline ropes, harness kits, ridge anchor brackets\n\n"
            "PHASE 2: DECK REPAIR & SUBSTRATE PREP\n"
            "----------------------------------------------------------------------\n"
            "  [ ] Materials: 4x8 ft 7/16\" OSB sheathing sheets (buffer: 4 replacement sheets)\n"
            "  [ ] Fasteners: 8d ring-shank nails\n"
            "  [ ] Underlayment: High-temp synthetic underlayment (rated for metal roofs)\n"
            "  [ ] Valley Barrier: 36\" self-adhering ice & water shield\n\n"
            "PHASE 3: STANDING SEAM METAL INSTALLATION\n"
            "----------------------------------------------------------------------\n"
            "  [ ] Panels: 26 ga Galvalume Standing Seam (Custom run to slope length)\n"
            "  [ ] Flashing & Trim: Drip edge, ridge cap, rake/gable trim, sidewall flashing\n"
            "  [ ] Fasteners: #10 pancake-head screws (concealed clips) & gasketed hex screws\n"
            "  [ ] Sealants: Class A non-curing butyl tape & exterior-grade polyurethane sealant\n\n"
            "PHASE 4: SITE CLEANUP & INSPECTION READY\n"
            "----------------------------------------------------------------------\n"
            "  [ ] Sign-off inspection request logged with county inspector\n"
        )
        self.txt_materials.insert("0.0", materials_manifest)
        self.txt_materials.configure(state="disabled")

        messagebox.showinfo("Green Light Cleared", "QAC is 100% complete!\nPermits and phase execution manifests have been unlocked.")

    def reset_workflow(self):
        self.quote_ready = False
        self.accepted = False
        self.contract_signed = False

        self.lbl_quote.configure(text="[  ] 1. Quote Drafted", text_color="#A0A0A0")
        self.lbl_accept.configure(text="[  ] 2. Customer Accepted", text_color="#A0A0A0")
        self.lbl_contract.configure(text="[  ] 3. Contract Signed", text_color="#A0A0A0")

        self.btn_generate_quote.configure(state="normal")
        self.btn_customer_accept.configure(state="disabled")
        self.btn_sign_contract.configure(state="disabled")

        self.status_card.configure(fg_color="#2A2A2A")
        self.status_text.configure(text="GATE STATUS:\nLOCKED (RED)", text_color="#FF4C4C")

        self.txt_codes.configure(state="normal")
        self.txt_codes.delete("0.0", "end")
        self.txt_codes.insert("0.0", "=== LOCKED ===\nComplete Quote -> Acceptance -> Contract (QAC) above to unlock NC Building Code and Permitting requirements.")
        self.txt_codes.configure(state="disabled")

        self.txt_materials.configure(state="normal")
        self.txt_materials.delete("0.0", "end")
        self.txt_materials.insert("0.0", "=== LOCKED ===\nComplete Quote -> Acceptance -> Contract (QAC) above to unlock material specifications and order checklists.")
        self.txt_materials.configure(state="disabled")

if __name__ == "__main__":
    app = SteveRoofingApp()
    app.mainloop()