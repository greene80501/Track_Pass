# scanner_handler.py
import requests
from pynput import keyboard

# --- Configuration ---
FLASK_APP_URL = "http://127.0.0.1:5000"
# --------------------

class ScannerListener:
    def __init__(self, app_url):
        self.app_url = app_url
        self.buffer = ""

    def on_press(self, key):
        try:
            # Add character to buffer
            self.buffer += key.char
        except AttributeError:
            # Handle special keys
            if key == keyboard.Key.enter:
                if self.buffer.isdigit():
                    print(f"Scanner detected Pass ID: {self.buffer}")
                    self.send_to_app(self.buffer)
                self.buffer = "" # Reset buffer on Enter

    def send_to_app(self, pass_id):
        """Sends the captured Pass ID to the main Flask app."""
        try:
            response = requests.post(f"{self.app_url}/return_pass", data={'pass_id': pass_id})
            if response.status_code == 200:
                print(f"Successfully returned Pass ID {pass_id}.")
            else:
                print(f"Error returning Pass ID {pass_id}: {response.text}")
        except requests.exceptions.ConnectionError as e:
            print(f"[ERROR] Could not connect to the Flask app at {self.app_url}.")
            print(f"        Is the app.py server running? Details: {e}")


def main():
    print("--- Scanner Handler is running ---")
    print("Listening for barcode scans (numeric input followed by Enter)...")
    
    listener = ScannerListener(FLASK_APP_URL)
    with keyboard.Listener(on_press=listener.on_press) as k:
        k.join()

if __name__ == "__main__":
    main()