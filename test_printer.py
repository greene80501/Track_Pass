# test_printer.py
import sys
import time
from printer_handler import print_pass_slip, VENDOR_ID, PRODUCT_ID
from escpos.printer import Usb

def test_printer_connection():
    """Test basic printer connectivity"""
    print("=" * 50)
    print("TESTING PRINTER CONNECTION")
    print("=" * 50)
    
    try:
        dev = Usb(VENDOR_ID, PRODUCT_ID)
        print("✅ Successfully connected to printer!")
        
        # Test basic printing
        dev.set(align='center', width=2, height=2)
        dev.text("CONNECTION TEST\n")
        dev.set(align='left', width=1, height=1)
        dev.text("If you can read this, the printer is working!\n")
        dev.text(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        dev.cut()
        dev.close()
        
        print("✅ Test print sent successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Printer connection failed: {e}")
        print("\nTroubleshooting tips:")
        print("1. Check USB connection")
        print("2. Verify printer is powered on")
        print("3. Check if printer drivers are installed")
        print("4. Run 'lsusb' (Linux/Mac) or Device Manager (Windows) to verify device")
        print(f"5. Look for device with Vendor ID: {hex(VENDOR_ID)}, Product ID: {hex(PRODUCT_ID)}")
        return False

def test_sample_passes():
    """Test printing with sample data"""
    print("\n" + "=" * 50)
    print("TESTING SAMPLE HALL PASSES")
    print("=" * 50)
    
    test_cases = [
        {
            "student_name": "John Smith",
            "student_id": "JS12345",
            "pass_id": 1001,
            "duration_minutes": 15
        },
        {
            "student_name": "Maria Garcia-Rodriguez",  # Test long name
            "student_id": "MG67890",
            "pass_id": 1002,
            "duration_minutes": 30
        },
        {
            "student_name": "李小明",  # Test unicode characters
            "student_id": "LX99999",
            "pass_id": 1003,
            "duration_minutes": 10
        },
        {
            "student_name": "A",  # Test short name
            "student_id": "A1",
            "pass_id": 1004,
            "duration_minutes": 5
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['student_name']}")
        print("-" * 30)
        
        try:
            print_pass_slip(
                student_name=test_case["student_name"],
                student_id=test_case["student_id"],
                pass_id=test_case["pass_id"],
                duration_minutes=test_case["duration_minutes"]
            )
            print("✅ Pass printed successfully!")
            
            # Wait between prints
            if i < len(test_cases):
                print("Waiting 3 seconds before next test...")
                time.sleep(3)
                
        except Exception as e:
            print(f"❌ Failed to print pass: {e}")

def test_barcode_only():
    """Test barcode generation without printing"""
    print("\n" + "=" * 50)
    print("TESTING BARCODE GENERATION")
    print("=" * 50)
    
    try:
        from barcode import Code128
        from barcode.writer import ImageWriter
        import os
        
        os.makedirs("test_barcodes", exist_ok=True)
        
        test_ids = [9999, 1234567890, 42]
        
        for pass_id in test_ids:
            try:
                barcode_path_base = os.path.join("test_barcodes", f"test_pass_{pass_id}")
                code = Code128(str(pass_id), writer=ImageWriter())
                barcode_path = code.save(barcode_path_base)
                print(f"✅ Barcode generated for ID {pass_id}: {barcode_path}")
            except Exception as e:
                print(f"❌ Failed to generate barcode for ID {pass_id}: {e}")
                
    except ImportError:
        print("❌ Barcode library not available. Install with: pip install python-barcode[images]")

def interactive_test():
    """Interactive test mode"""
    print("\n" + "=" * 50)
    print("INTERACTIVE TEST MODE")
    print("=" * 50)
    
    while True:
        print("\nEnter student details (or 'quit' to exit):")
        
        student_name = input("Student Name: ").strip()
        if student_name.lower() == 'quit':
            break
            
        student_id = input("Student ID: ").strip()
        if not student_id:
            student_id = "TEST123"
            
        try:
            duration = int(input("Duration (minutes) [15]: ") or "15")
        except ValueError:
            duration = 15
            
        try:
            pass_id = int(input("Pass ID [auto-generate]: ") or str(int(time.time()) % 10000))
        except ValueError:
            pass_id = int(time.time()) % 10000
        
        print(f"\nPrinting pass for: {student_name} (ID: {student_id})")
        print(f"Duration: {duration} minutes, Pass ID: {pass_id}")
        
        confirm = input("Print this pass? (y/N): ").strip().lower()
        if confirm == 'y':
            print_pass_slip(student_name, student_id, pass_id, duration)
        else:
            print("Pass cancelled.")

def main():
    """Main test function"""
    print("HALL PASS PRINTER TEST SUITE")
    print("=" * 50)
    
    while True:
        print("\nSelect test option:")
        print("1. Test printer connection")
        print("2. Test sample hall passes")
        print("3. Test barcode generation only")
        print("4. Interactive test mode")
        print("5. Run all tests")
        print("0. Exit")
        
        choice = input("\nEnter choice (0-5): ").strip()
        
        if choice == "0":
            print("Exiting test suite.")
            break
        elif choice == "1":
            test_printer_connection()
        elif choice == "2":
            if test_printer_connection():
                test_sample_passes()
        elif choice == "3":
            test_barcode_only()
        elif choice == "4":
            if test_printer_connection():
                interactive_test()
        elif choice == "5":
            # Run all tests
            if test_printer_connection():
                test_barcode_only()
                test_sample_passes()
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()