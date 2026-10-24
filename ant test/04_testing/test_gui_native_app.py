"""Automated verification test for Native Tkinter Backscatter GUI Dashboard.
Tests headless/virtual instantiation, mock streaming, snapshot generation, and shutdown.
"""

import os
import sys
import time

# Ensure 03_sdr_software is on path
SDR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "03_sdr_software"))
if SDR_DIR not in sys.path:
    sys.path.insert(0, SDR_DIR)

import tkinter as tk
from backscatter_gui_app import BackscatterTkGUI


def test_gui_app_lifecycle():
    print("[TEST] 1. Initializing BackscatterTkGUI (force_mock=True)...")
    root = tk.Tk()
    app = BackscatterTkGUI(root, force_mock=True)

    print("[TEST] 2. Verifying initial GUI configuration...")
    assert app.current_mode_key == "mode1"
    assert app.modes["mode1"]["center_freq"] == 2440.0e6

    print("[TEST] 3. Testing mode switching...")
    app.apply_mode_config("mode2")
    assert app.current_mode_key == "mode2"
    assert app.modes["mode2"]["center_freq"] == 868.0e6

    app.apply_mode_config("mode3")
    assert app.current_mode_key == "mode3"
    assert app.modes["mode3"]["center_freq"] == 2437.0e6

    print("[TEST] 4. Testing streaming toggle and UI event pump...", flush=True)
    print("  -> Calling toggle_streaming()", flush=True)
    app.toggle_streaming()
    print("  -> toggle_streaming() returned, worker alive:", app.worker.is_alive(), flush=True)
    assert app.worker is not None and app.worker.is_alive()

    # Process Tkinter loop events for 1 second
    start = time.time()
    frames = 0
    print("  -> Running mainloop for 1 second...", flush=True)
    app.root.after(1000, app.root.quit)
    app.root.mainloop()
    print("  -> Mainloop exited normally", flush=True)

    print(f"[TEST] Processed {frames} UI update cycles successfully.")

    print("[TEST] 5. Testing snapshot trigger...", flush=True)
    app.trigger_snapshot()
    app.root.after(800, app.root.quit)
    app.root.mainloop()

    print("[TEST] 6. Stopping stream and destroying window...", flush=True)
    app.toggle_streaming()
    assert app.worker is None
    app.root.destroy()
    print("[TEST] [SUCCESS] Native GUI lifecycle test completed 100% cleanly!", flush=True)


if __name__ == "__main__":
    test_gui_app_lifecycle()
