# usb_detect.py
"""
USB Device Detection Script for ESC/POS Printers
Helps identify printer vendor and product IDs
"""

def detect_usb_devices():
    """Detect USB devices using different methods based on available libraries"""
    
    print("=" * 60)
    print("USB DEVICE DETECTION FOR ESC/POS PRINTERS")
    print("=" * 60)
    
    # Method 1: Try usb.core (pyusb)
    try:
        import usb.core
        print("✅ Using pyusb library for device detection\n")
        
        devices = usb.core.find(find_all=True)
        
        if not devices:
            print("❌ No USB devices found")
            return
        
        print("Found USB devices:")
        print("-" * 40)
        
        for device in devices:
            try:
                vendor_id = device.idVendor
                product_id = device.idProduct
                
                # Try to get manufacturer and product strings
                try:
                    manufacturer = usb.util.get_string(device, device.iManufacturer)
                except:
                    manufacturer = "Unknown"
                
                try:
                    product = usb.util.get_string(device, device.iProduct)
                except:
                    product = "Unknown"
                
                print(f"Vendor ID:  0x{vendor_id:04x} ({vendor_id})")
                print(f"Product ID: 0x{product_id:04x} ({product_id})")
                print(f"Manufacturer: {manufacturer}")
                print(f"Product: {product}")
                print(f"Bus: {device.bus}, Address: {device.address}")
                
                # Check if this might be a printer
                if is_likely_printer(manufacturer, product, vendor_id):
                    print("🖨️  *** LIKELY PRINTER DEVICE ***")
                
                print("-" * 40)
                
            except Exception as e:
                print(f"Error reading device: {e}")
                print("-" * 40)
        
        return True
        
    except ImportError:
        print("❌ pyusb not available")
    
    # Method 2: Try platform-specific commands
    print("\n📋 Alternative detection methods:")
    print("-" * 40)
    
    import subprocess
    import sys
    
    if sys.platform.startswith('linux') or sys.platform == 'darwin':
        try:
            # Try lsusb command
            print("Running 'lsusb' command:")
            result = subprocess.run(['lsusb'], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'printer' in line.lower() or 'pos' in line.lower():
                        print(f"🖨️  {line}")
                    else:
                        print(f"   {line}")
            else:
                print("❌ lsusb command failed")
        except FileNotFoundError:
            print("❌ lsusb command not found")
    
    elif sys.platform == 'win32':
        try:
            # Try wmic command for Windows
            print("Running Windows device detection:")
            result = subprocess.run([
                'wmic', 'path', 'Win32_USBDevice', 'get', 
                'Name,DeviceID,Manufacturer', '/format:table'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    if line.strip() and ('printer' in line.lower() or 'pos' in line.lower()):
                        print(f"🖨️  {line.strip()}")
                    elif line.strip():
                        print(f"   {line.strip()}")
            else:
                print("❌ Windows device query failed")
        except Exception as e:
            print(f"❌ Windows detection error: {e}")

def is_likely_printer(manufacturer, product, vendor_id):
    """Check if device is likely a printer based on manufacturer/product info"""
    
    # Common printer keywords
    printer_keywords = [
        'printer', 'pos', 'thermal', 'receipt', 'epson', 'star', 'citizen',
        'bixolon', 'custom', 'sewoo', 'partner', 'rongta', 'xprinter'
    ]
    
    # Common printer vendor IDs (in decimal)
    printer_vendor_ids = [
        0x04b8,  # Epson
        0x0519,  # Star Micronics
        0x1504,  # Citizen
        0x0fe6,  # ICS Advent (your current printer)
        0x2cf7,  # Custom Engineering SPA
        0x154f,  # Wincor Nixdorf
        0x0b03,  # Hewlett-Packard
    ]
    
    # Check manufacturer and product strings
    text_to_check = f"{manufacturer} {product}".lower()
    for keyword in printer_keywords:
        if keyword in text_to_check:
            return True
    
    # Check vendor ID
    if vendor_id in printer_vendor_ids:
        return True
    
    return False

def test_escpos_connection():
    """Test connection to known printer configurations"""
    
    print("\n" + "=" * 60)
    print("TESTING ESCPOS PRINTER CONNECTIONS")
    print("=" * 60)
    
    # Common printer configurations
    printer_configs = [
        (0x0fe6, 0x811e, "ICS Advent (Your current config)"),
        (0x04b8, 0x0202, "Epson TM-T88V"),
        (0x04b8, 0x0005, "Epson TM-T20"),
        (0x0519, 0x0001, "Star TSP650"),
        (0x1504, 0x0006, "Citizen CT-S310"),
    ]
    
    try:
        from escpos.printer import Usb
    except ImportError:
        print("❌ python-escpos library not available")
        print("Install with: pip install python-escpos")
        return
    
    for vendor_id, product_id, description in printer_configs:
        print(f"\nTesting: {description}")
        print(f"Vendor ID: 0x{vendor_id:04x}, Product ID: 0x{product_id:04x}")
        
        try:
            printer = Usb(vendor_id, product_id)
            print("✅ Connection successful!")
            
            # Try a simple test print
            try:
                printer.text("Test connection\n")
                printer.cut()
                print("✅ Test print sent successfully!")
            except Exception as e:
                print(f"⚠️  Connected but print failed: {e}")
            
            printer.close()
            break  # Stop after first successful connection
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")

def main():
    """Main function"""
    print("ESC/POS Printer USB Detection Tool")
    
    while True:
        print("\nSelect option:")
        print("1. Detect all USB devices")
        print("2. Test ESC/POS printer connections")
        print("3. Show installation requirements")
        print("0. Exit")
        
        choice = input("\nEnter choice (0-3): ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            detect_usb_devices()
        elif choice == "2":
            test_escpos_connection()
        elif choice == "3":
            show_requirements()
        else:
            print("Invalid choice.")

def show_requirements():
    """Show installation requirements"""
    print("\n" + "=" * 60)
    print("INSTALLATION REQUIREMENTS")
    print("=" * 60)
    
    print("\nRequired Python packages:")
    print("pip install python-escpos")
    print("pip install python-barcode[images]")
    print("pip install pyusb")
    print("pip install Pillow")
    
    print("\nSystem requirements:")
    print("- USB printer drivers (if required)")
    print("- libusb (Linux: sudo apt-get install libusb-1.0-0-dev)")
    print("- For Windows: Install libusb-win32 or WinUSB driver")
    
    print("\nPermissions (Linux):")
    print("- Add user to 'lp' group: sudo usermod -a -G lp $USER")
    print("- Or create udev rule for your printer")
    
    print("\nTroubleshooting:")
    print("- Check printer is powered on and connected")
    print("- Try different USB ports/cables")
    print("- Check if printer appears in system device manager")
    print("- Some printers need specific drivers installed first")

if __name__ == "__main__":
    main()