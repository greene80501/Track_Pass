# main.py — DB-only version (no JSON caches)

import tkinter as tk
import datetime
import time
import database
from hashlib import sha256
from escpos.printer import Usb
from weasyprint import HTML
import fitz  # PyMuPDF
from barcode import Code128
from barcode.writer import ImageWriter

# ------------------------------
# Hardware printer configuration
# ------------------------------
VENDOR_ID = 0x0fe6
PRODUCT_ID = 0x811e

try:
    dev = Usb(VENDOR_ID, PRODUCT_ID)
except Exception as e:
    dev = None
    print(f"[WARN] ESC/POS printer not available: {e}")


class App:
    """
    Kiosk-style UI:
      - Scan / type a 6-digit student ID
      - Start a timed pass
      - Return a pass (by pass_id or via the current active pass)
      - Print pass slip and student info report (DB-backed)
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.configure(bg="black")
        self.root.bind("<Key>", self._on_key)

        # DB
        self.con = database.create_connection()
        self.cur = database.create_cursor(self.con)
        database.init_database(self.cur)

        # State
        self.student_buf = ""           # collects keyboard digits
        self.current_student_id = None  # "######" string or None
        self.current_pass_id = None     # int or None
        self.timer_active = False
        self.timer_duration_minutes = 10
        self.timer_end_epoch = None

        # UI
        self.header = tk.Label(
            root, text="Scan or Enter Student ID",
            fg="white", bg="black", font=("Arial", 36)
        )
        self.header.pack(pady=30)

        self.subhead = tk.Label(
            root, text="",
            fg="white", bg="black", font=("Arial", 22)
        )
        self.subhead.pack(pady=10)

        controls = tk.Frame(root, bg="black")
        controls.pack(pady=20)

        self.entry_label = tk.Label(
            controls, text="ID: ______",
            fg="cyan", bg="black", font=("Consolas", 28)
        )
        self.entry_label.grid(row=0, column=0, columnspan=4, pady=10, padx=10, sticky="w")

        self.start_btn = tk.Button(
            controls, text="Start 10-min Pass", font=("Arial", 20),
            command=self.start_timer
        )
        self.start_btn.grid(row=1, column=0, padx=10, pady=10)

        self.return_btn = tk.Button(
            controls, text="Return Pass", font=("Arial", 20),
            command=self.return_current_pass
        )
        self.return_btn.grid(row=1, column=1, padx=10, pady=10)

        self.print_pass_btn = tk.Button(
            controls, text="Print Pass Slip", font=("Arial", 20),
            command=self.print_pass_slip
        )
        self.print_pass_btn.grid(row=1, column=2, padx=10, pady=10)

        self.print_info_btn = tk.Button(
            controls, text="Print Student Info", font=("Arial", 20),
            command=self.print_student_info
        )
        self.print_info_btn.grid(row=1, column=3, padx=10, pady=10)

        self.timer_label = tk.Label(
            root, text="", fg="yellow", bg="black", font=("Consolas", 28)
        )
        self.timer_label.pack(pady=15)

        self._tick_timer()

    # ------------------------------
    # UI helpers
    # ------------------------------

    def set_status(self, text: str):
        self.header.config(text=text)

    def set_substatus(self, text: str):
        self.subhead.config(text=text)

    def _update_entry_label(self):
        masked = (self.current_student_id or self.student_buf).ljust(6, "_")
        self.entry_label.config(text=f"ID: {masked}")

    # ------------------------------
    # Keyboard input
    # ------------------------------

    def _on_key(self, event: tk.Event):
        k = getattr(event, "keysym", "")
        ch = getattr(event, "char", "")

        # digits build the student buffer (or pass_id entry mode if prefixed)
        if ch.isdigit():
            self.student_buf += ch
            if len(self.student_buf) > 12:
                self.student_buf = self.student_buf[-12:]
            if len(self.student_buf) == 6 and self.current_student_id is None:
                # assume student id
                self.current_student_id = self.student_buf
                self.student_buf = ""
                self._on_student_entered()
            self._update_entry_label()
            return

        if k == "Return":
            # If we have 6 digits buffered and no current student, accept as student id
            if self.current_student_id is None and len(self.student_buf) == 6:
                self.current_student_id = self.student_buf
                self.student_buf = ""
                self._on_student_entered()
                self._update_entry_label()
                return

            # If digits remain in buffer, try interpreting as pass_id for return
            if self.student_buf:
                try:
                    maybe_pass_id = int(self.student_buf)
                    self.student_buf = ""
                    self.return_pass_by_id(maybe_pass_id)
                    return
                except ValueError:
                    self.student_buf = ""
                    self.set_status("Invalid pass id.")
                    return

        if k == "Escape":
            self.reset_ui()
            return

        # backspace to edit the buffer
        if k == "BackSpace":
            if self.student_buf:
                self.student_buf = self.student_buf[:-1]
                self._update_entry_label()
            return

    def _on_student_entered(self):
        sid = self.current_student_id
        if sid is None:
            return
        if len(sid) != 6 or not sid.isdigit():
            self.set_status("Invalid ID. Enter exactly 6 digits.")
            self.current_student_id = None
            return

        s = database.get_student_by_id(self.cur, sid)
        if s is None:
            self.set_status("That student ID number is not recognized!")
            self.current_student_id = None
            return

        self.set_status(f"Hello, {s['Name']}")
        self.set_substatus(f"Passes: {s['Number Of Passes']}  |  Total Time Out: {int(s['Total Time Out']/60)} min")

    # ------------------------------
    # Timer / pass lifecycle
    # ------------------------------

    def start_timer(self):
        if self.timer_active:
            self.set_status("A pass is already active.")
            return

        if self.current_student_id is None:
            self.set_status("Scan or Enter Student ID before starting a pass!")
            return

        sid = self.current_student_id
        pass_id = database.create_pass_now(self.cur, sid, self.timer_duration_minutes)
        if pass_id is None:
            self.set_status("Could not create a new pass. Try again.")
            return

        self.current_pass_id = pass_id
        database.save_data(self.con)

        self.timer_active = True
        self.timer_end_epoch = time.time() + self.timer_duration_minutes * 60
        self.set_status(f"Pass started for {sid}.")
        self.set_substatus(f"Pass ID: {pass_id}")
        self._tick_timer(force=True)

    def _tick_timer(self, force: bool = False):
        if self.timer_active and self.timer_end_epoch is not None:
            remaining = max(0, int(self.timer_end_epoch - time.time()))
            m, s = divmod(remaining, 60)
            self.timer_label.config(text=f"Time Remaining: {m:02d}:{s:02d}")

            if remaining <= 0:
                # Timer finished: auto-return the pass
                self.timer_finished()
        else:
            if force:
                self.timer_label.config(text="")
        self.root.after(250, self._tick_timer)

    def timer_finished(self):
        """Called when countdown hits zero. Marks pass returned and updates aggregates."""
        if not self.timer_active:
            return

        sid = self.current_student_id
        pid = self.current_pass_id

        if not sid or pid is None:
            # inconsistent state; just reset
            self.reset_ui()
            return

        # Compute elapsed = intended - remaining (should be intended here)
        intended_seconds = self.timer_duration_minutes * 60
        elapsed_seconds = intended_seconds  # since timer expired

        # Close the pass and update aggregates
        database.populate_pass(self.cur, pass_id=pid, returned=True)
        database.increment_student_pass_number(self.cur, sid)
        database.add_to_student_time_out(self.cur, sid, elapsed_seconds)
        database.save_data(self.con)

        self.set_status("Time's up. Pass closed.")
        self.set_substatus(f"Returned pass {pid} for {sid}.")
        self.timer_active = False
        self.timer_end_epoch = None
        self.current_pass_id = None

    def return_current_pass(self):
        """Manually return the active pass early."""
        if not self.timer_active or self.current_pass_id is None or self.current_student_id is None:
            self.set_status("No active pass to return.")
            return

        now_remaining = max(0, int(self.timer_end_epoch - time.time()))
        elapsed = self.timer_duration_minutes * 60 - now_remaining
        elapsed = max(0, elapsed)

        sid = self.current_student_id
        pid = self.current_pass_id

        database.populate_pass(self.cur, pass_id=pid, returned=True)
        database.increment_student_pass_number(self.cur, sid)
        database.add_to_student_time_out(self.cur, sid, elapsed)
        database.save_data(self.con)

        self.set_status("Welcome back.")
        self.set_substatus(f"Returned pass {pid} for {sid}.")
        self.timer_active = False
        self.timer_end_epoch = None
        self.current_pass_id = None

    def return_pass_by_id(self, pass_id: int):
        """Return a pass by scanning/typing its pass_id directly."""
        # We don’t know the student_id here, so we’ll:
        #  1) mark the pass returned
        #  2) look up the pass again (if you add such helper) or just accept no aggregates update
        # Better: add a DB helper to fetch pass row by pass_id so we can update aggregates.
        try:
            # OPTIONAL: write a database.get_pass_by_id for a full solution.
            # For now, just mark returned.
            database.populate_pass(self.cur, pass_id=pass_id, returned=True)
            database.save_data(self.con)
            self.set_status(f"Returned pass {pass_id}.")
            self.set_substatus("If you want aggregates updated, return via the active-pass button.")
        except Exception as e:
            self.set_status(f"Failed to return pass {pass_id}: {e}")

    def reset_ui(self):
        self.current_student_id = None
        self.student_buf = ""
        self.current_pass_id = None
        self.timer_active = False
        self.timer_end_epoch = None
        self.timer_label.config(text="")
        self.set_status("Scan or Enter Student ID")
        self.set_substatus("")
        self._update_entry_label()

    # ------------------------------
    # Printing
    # ------------------------------

    def _print_escpos_lines(self, lines):
        if dev is None:
            print("[WARN] Printing skipped (no ESC/POS device).")
            return
        try:
            for ln in lines:
                dev.text(ln + "\n")
            dev.cut()
        except Exception as e:
            print(f"[WARN] ESC/POS print failed: {e}")

    def print_pass_slip(self):
        """Print a small receipt-like pass slip for the active/student context."""
        sid = self.current_student_id
        if sid is None:
            self.set_status("Scan or Enter Student ID before printing a pass.")
            return

        s = database.get_student_by_id(self.cur, sid)
        if s is None:
            self.set_status("Unknown student.")
            return

        now = datetime.datetime.now()
        title = "HALL PASS"
        name = s["Name"]
        pid = self.current_pass_id or "(pending)"
        dur = self.timer_duration_minutes

        # Optional: barcode for pass_id if we have one
        barcode_path = None
        if isinstance(self.current_pass_id, int):
            try:
                code = Code128(str(self.current_pass_id), writer=ImageWriter())
                barcode_path = f"pass_{self.current_pass_id}_code128.png"
                code.save(barcode_path)
            except Exception as e:
                print(f"[WARN] Could not render barcode: {e}")

        lines = [
            f"{title}",
            f"Student: {name}",
            f"ID: {sid}",
            f"Pass ID: {pid}",
            f"Start: {now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {dur} min",
            "-" * 24,
            "Return on time!",
        ]
        self._print_escpos_lines(lines)

        self.set_status("Printed pass.")
        self.set_substatus(f"Student {sid} / Pass {pid}")

    def print_student_info(self):
        """Render and print a student’s pass history from the DB (no JSON)."""
        sid = self.current_student_id
        if sid is None:
            self.set_status("Scan or Enter Student ID before printing student info!")
            return

        s = database.get_student_by_id(self.cur, sid)
        if s is None:
            self.set_status("That student ID number is not recognized!")
            self.reset_ui()
            return

        passes = database.get_passes_for_student(self.cur, sid)
        # Build simple HTML (replace with your own report_mockup.html if you prefer)
        rows = []
        for i, p in enumerate(passes, start=1):
            taken = p.get("pass_taken_at") or ""
            returned = p.get("return_time") or ""
            dur_mins = p.get("duration_minutes") or 0
            returned_flag = "Yes" if p.get("returned") else "No"
            rows.append(
                f"<tr>"
                f"<td>{i}</td><td>{taken}</td><td>{dur_mins}</td>"
                f"<td>{returned_flag}</td><td>{returned or '—'}</td>"
                f"</tr>"
            )

        ot_count = database.get_number_of_overtime_passes_by_student_id(self.cur, sid)

        html = f"""
        <html>
          <head>
            <meta charset="utf-8" />
            <style>
              body {{ font-family: Arial, sans-serif; }}
              h1 {{ margin: 0 0 10px 0; }}
              table {{ border-collapse: collapse; width: 100%; }}
              th, td {{ border: 1px solid #333; padding: 6px 8px; font-size: 12px; }}
              th {{ background: #eee; }}
              .meta {{ margin: 10px 0 20px; font-size: 14px; }}
            </style>
          </head>
          <body>
            <h1>Student Pass Report</h1>
            <div class="meta">
              <div><b>Name:</b> {s['Name']}</div>
              <div><b>Student ID:</b> {sid}</div>
              <div><b>Date:</b> {datetime.datetime.now().strftime('%Y-%m-%d')}</div>
              <div><b>Total Passes:</b> {s['Number Of Passes']}</div>
              <div><b>Total Time Out (min):</b> {int(s['Total Time Out']/60)}</div>
              <div><b>Overtime Passes:</b> {ot_count}</div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Taken At</th>
                  <th>Duration (min)</th>
                  <th>Returned?</th>
                  <th>Return Time</th>
                </tr>
              </thead>
              <tbody>
                {''.join(rows)}
              </tbody>
            </table>
          </body>
        </html>
        """

        # Write, convert to PDF, (optionally) to images, and send to printer
        report_html_path = "student_report.html"
        with open(report_html_path, "w", encoding="utf-8") as f:
            f.write(html)

        pdf_path = "student_report.pdf"
        HTML(report_html_path).write_pdf(pdf_path)

        # Optional: image pages to ESC/POS device; many 58/80mm printers don't love PDFs.
        try:
            pdf_document = fitz.open(pdf_path)
            for page_num in range(pdf_document.page_count):
                page = pdf_document.load_page(page_num)
                pix = page.get_pixmap()
                out_png = f"report-page-{page_num}.png"
                pix.save(out_png)
                # Print a simple notice; replace with raster printing if your printer supports it
                self._print_escpos_lines([f"[Report page saved: {out_png}]"])
            pdf_document.close()
        except Exception as e:
            print(f"[WARN] Could not rasterize PDF: {e}")

        self.set_status("Student report generated.")
        self.set_substatus(f"{s['Name']} ({sid})")

# ------------------------------
# Entrypoint
# ------------------------------

def main():
    root = tk.Tk()
    root.title("Student ID Scanner")
    root.attributes("-fullscreen", True)
    root.resizable(False, False)

    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
    print("Exiting")
