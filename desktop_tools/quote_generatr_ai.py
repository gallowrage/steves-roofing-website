import customtkinter as ctk
from tkinter import messagebox
import threading
import os

# --- CHECK FOR SDK INSTALLATION ---
GENAI_SDK = None
IMPORT_ERROR_MSG = ""

try:
    from google import genai
    GENAI_SDK = "genai"
except ImportError:
    GENAI_SDK = None
    IMPORT_ERROR_MSG = "Google GenAI SDK not installed.\nRun: pip install google-genai"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AIQuoteApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Steve's Roofing - AI Quote Engine")
        self.geometry("1150x760")
        self.minsize(950, 650)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_ui()

    def _build_ui(self):
        # Left Panel: Input & Controls
        self.left_panel = ctk.CTkFrame(self, width=380, corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.left_panel.grid_rowconfigure(3, weight=1)

        lbl_title = ctk.CTkLabel(
            self.left_panel, 
            text="AI ESTIMATOR\n& PROPOSAL DRAFTER", 
            font=("Arial", 18, "bold")
        )
        lbl_title.grid(row=0, column=0, padx=20, pady=(20, 15))

        # API Key Field
        lbl_key = ctk.CTkLabel(self.left_panel, text="Gemini API Key:", font=("Arial", 11, "bold"))
        lbl_key.grid(row=1, column=0, padx=20, pady=(5, 2), sticky="w")

        self.entry_key = ctk.CTkEntry(self.left_panel, placeholder_text="AQ.Ab8...", show="*")
        self.entry_key.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Customer Notes Input
        lbl_notes = ctk.CTkLabel(self.left_panel, text="Steve's Field Notes:", font=("Arial", 12, "bold"))
        lbl_notes.grid(row=3, column=0, padx=20, pady=(10, 2), sticky="nw")

        self.txt_input = ctk.CTkTextbox(self.left_panel, height=280)
        self.txt_input.grid(row=3, column=0, padx=20, pady=(35, 10), sticky="nsew")
        
        default_notes = (
            "David Galloway\n"
            "690 Dogwood Lane, Buncombe County, NC\n"
            "Roughly 1,400 sq ft footprint, 6/12 pitch roof.\n"
            "Old architectural shingles are failing; complete tear-off needed.\n"
            "Wants standing seam 26-gauge Galvalume metal roof, black finish.\n"
            "Needs high-temp synthetic underlayment + ice & water shield in valleys.\n"
            "Chimney needs re-flashing. Access is good on the driveway side."
        )
        self.txt_input.insert("0.0", default_notes)

        # Action Button
        self.btn_generate = ctk.CTkButton(
            self.left_panel, 
            text="⚡ Generate AI Proposal", 
            font=("Arial", 14, "bold"),
            height=40,
            command=self.start_ai_generation
        )
        self.btn_generate.grid(row=4, column=0, padx=20, pady=(10, 20), sticky="ew")

        # Right Panel: Output Preview
        self.right_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.right_panel.grid_rowconfigure(1, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)

        lbl_preview = ctk.CTkLabel(self.right_panel, text="Generated Customer Quote & Contract", font=("Arial", 16, "bold"))
        lbl_preview.grid(row=0, column=0, sticky="w", pady=(0, 10))

        self.txt_output = ctk.CTkTextbox(self.right_panel, font=("Consolas", 12))
        self.txt_output.grid(row=1, column=0, sticky="nsew")
        self.txt_output.insert("0.0", "Paste your new API key on the left and click 'Generate AI Proposal'...")

    def start_ai_generation(self):
        notes = self.txt_input.get("0.0", "end").strip()
        api_key = self.entry_key.get().strip()

        if not api_key:
            messagebox.showwarning("Key Missing", "Please paste your Gemini API key in the box on the left.")
            return

        if not notes:
            messagebox.showwarning("Notes Missing", "Please provide customer field notes.")
            return

        if GENAI_SDK is None:
            self.txt_output.delete("0.0", "end")
            self.txt_output.insert("0.0", f"[ERROR] SDK Not Found:\n\n{IMPORT_ERROR_MSG}\n\nMake sure to run 'pip install google-genai' inside VS Code.")
            return

        self.btn_generate.configure(state="disabled", text="Connecting to Gemini...")
        self.txt_output.delete("0.0", "end")
        self.txt_output.insert("0.0", "Contacting Gemini API...\nCalculating roofing squares and waste factors for David Galloway...\nDrafting proposal...")

        threading.Thread(target=self._run_generation, args=(api_key, notes), daemon=True).start()

    def _run_generation(self, api_key, notes):
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
            if GENAI_SDK == "genai":
                from google import genai
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=prompt
                )
                output_text = response.text
            else:
                output_text = f"[ERROR] SDK Not Available:\n\n{IMPORT_ERROR_MSG}"

        except Exception as e:
            output_text = f"[API ERROR]: {str(e)}\n\nPlease ensure your API key is active and has permissions enabled."

        self.after(0, self._render_result, output_text)

    def _render_result(self, text):
        self.txt_output.delete("0.0", "end")
        self.txt_output.insert("0.0", text)
        self.btn_generate.configure(state="normal", text="⚡ Generate AI Proposal")

if __name__ == "__main__":
    app = AIQuoteApp()
    app.mainloop()