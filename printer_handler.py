# printer_handler.py
import os
from datetime import datetime
from barcode import Code128
from barcode.writer import ImageWriter
from escpos.printer import Usb

# --- Hardware Configuration ---
# Find these values by running usb_detect.py from the original project
VENDOR_ID = 0x0fe6
PRODUCT_ID = 0x811e
# -----------------------------

# Create a directory for barcode images
os.makedirs("barcodes", exist_ok=True)

def print_pass_slip(student_name: str, student_id: str, pass_id: int, duration_minutes: int):
    """
    Connects to the ESC/POS printer and prints a hall pass slip.
    """
    try:
        dev = Usb(VENDOR_ID, PRODUCT_ID)
    except Exception as e:
        print(f"[ERROR] Could not connect to printer: {e}")
        print("[INFO] Printing skipped.")
        return

    # --- Generate Barcode ---
    try:
        barcode_path_base = os.path.join("barcodes", f"pass_{pass_id}")
        code = Code128(str(pass_id), writer=ImageWriter())
        barcode_path = code.save(barcode_path_base)
    except Exception as e:
        print(f"[WARN] Could not render barcode: {e}")
        barcode_path = None

    try:
        # --- Print Header ---
        dev.set(align='center', width=2, height=2)
        dev.set(text_type='B')  # Bold text
        dev.text("HALL PASS\n")
        
        # --- Reset to normal and print details ---
        dev.set(align='left', width=1, height=1)
        dev.set(text_type='normal')
        dev.text("-" * 32 + "\n")
        
        dev.text(f"Student: {student_name}\n")
        dev.text(f"ID: {student_id}\n")
        dev.text(f"Pass ID: {pass_id}\n")
        
        now = datetime.now()
        dev.text(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
        dev.text(f"Duration: {duration_minutes} minutes\n")
        dev.text("-" * 32 + "\n\n")

        # --- Print Barcode ---
        if barcode_path:
            dev.set(align='center')
            try:
                dev.image(barcode_path)
                dev.text("Scan this code upon return\n")
            except Exception as e:
                print(f"[WARN] Could not print barcode: {e}")
                dev.text(f"Pass ID: {pass_id}\n")

        dev.text("\n")
        dev.cut()
        print(f"[SUCCESS] Printed pass slip for Pass ID: {pass_id}")
        
    except Exception as e:
        print(f"[ERROR] Failed to print pass: {e}")
    finally:
        try:
            dev.close()
        except:
            pass