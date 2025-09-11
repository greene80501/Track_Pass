import usb.core
import usb.util
import usb.backend.libusb1

backend = usb.backend.libusb1.get_backend()

def list_usb_devices():
    devices = usb.core.find(backend=backend, find_all=True)
    dev_list = []
    print("Connected USB devices:\n")
    for i, dev in enumerate(devices):
        try:
            # Manufacturer and product strings may require device to be set first
            manufacturer = usb.util.get_string(dev, dev.iManufacturer) or "Unknown"
            product = usb.util.get_string(dev, dev.iProduct) or "Unknown"
        except (usb.core.USBError, ValueError):
            manufacturer = "Unknown"
            product = "Unknown"

        print(f"[{i}] VID: {hex(dev.idVendor)}, PID: {hex(dev.idProduct)}, "
              f"Manufacturer: {manufacturer}, Product: {product}")
        dev_list.append(dev)
    return dev_list

def select_device():
    try: 
        dev_list = list_usb_devices()
    except usb.core.NoBackendError:
        print(f"No core.\n       ╰─> Try: sudo apt install libusb-1.0-0-dev")
        return
    
    if not dev_list:
        print("No USB devices found.")
        return None
    choice = int(input("\nSelect device number: "))
    return dev_list[choice]

if __name__ == "__main__":
    print("DEVICE SELECTION DEMO")
    dev = select_device()
    if dev:
        print(f"\nSelected device: VID={hex(dev.idVendor)}, PID={hex(dev.idProduct)}")

