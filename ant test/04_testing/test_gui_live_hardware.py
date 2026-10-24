"""Hardware live test for BackscatterGUI connected to NI USRP-2900."""

import os
import sys
import time
from PyQt5.QtWidgets import QApplication

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from backscatter_gui import BackscatterGUI

def test_live_hardware_gui():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    print("[LIVE-HW] 1. Instantiating BackscatterGUI with physical hardware...", flush=True)
    gui = BackscatterGUI(force_mock=False)
    gui.show()

    print("[LIVE-HW] 2. Starting acquisition on physical NI USRP-2900...", flush=True)
    gui.toggle_streaming()

    # Wait 1 second for USRP connection signal
    start_t = time.time()
    while time.time() - start_t < 1.5:
        app.processEvents()
        time.sleep(0.05)

    print(f"  Hardware status: {gui.hw_status_label.text()}", flush=True)
    assert gui.worker is not None
    assert gui.worker.is_hardware, "Worker did not connect to physical USRP hardware!"

    print("[LIVE-HW] 3. Streaming live RF backscatter from physical air for 2.0 seconds...", flush=True)
    start_t = time.time()
    while time.time() - start_t < 2.0:
        app.processEvents()
        time.sleep(0.05)

    print(f"  Live RF Power: {gui.lbl_metric_prx.text()}", flush=True)
    print(f"  Live State: {gui.card_state.text()}", flush=True)

    print("[LIVE-HW] 4. Triggering Auto-Zero Baseline Leakage Cancellation...", flush=True)
    gui.trigger_autozero()
    app.processEvents()

    print("[LIVE-HW] 5. Exporting physical measurement snapshot...", flush=True)
    export_dir = os.path.join(script_dir, "output", "snapshots")
    gui.worker.request_snapshot(export_dir, "live_hardware_test_snapshot")

    start_t = time.time()
    while time.time() - start_t < 2.0:
        app.processEvents()
        time.sleep(0.05)

    mat_files = [f for f in os.listdir(export_dir) if f.startswith("live_hardware_test_snapshot") and f.endswith(".mat")]
    print(f"  Found {len(mat_files)} live hardware .mat export files in {export_dir}.", flush=True)
    assert len(mat_files) > 0, "No live hardware .mat file was exported!"

    print("[LIVE-HW] 6. Stopping physical SDR stream...", flush=True)
    gui.toggle_streaming()
    app.processEvents()

    gui.close()
    app.processEvents()
    app.quit()
    print("[SUCCESS] Live physical NI USRP-2900 GUI integration test passed with 100% success!", flush=True)

if __name__ == "__main__":
    test_live_hardware_gui()
