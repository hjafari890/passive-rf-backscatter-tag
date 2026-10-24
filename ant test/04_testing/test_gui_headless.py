"""Automated headless test for BackscatterGUI and SDRWorker."""

import os
import sys
import time
from PyQt5.QtWidgets import QApplication

# Add sdr_pipeline to sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from backscatter_gui import BackscatterGUI

def test_gui_headless():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    print("[TEST] 1. Instantiating BackscatterGUI with force_mock=True...")
    gui = BackscatterGUI(force_mock=True)
    gui.show()

    print("[TEST] 2. Testing mode switching...")
    for mode in ["mode1", "mode2", "mode3", "mode1"]:
        gui.apply_mode_config(mode)
        cfg = gui.modes[mode]
        print(f"  Switched to {mode}: Freq={gui.spin_freq.value()} MHz, Rate={gui.combo_rate.currentText()}")
        assert abs(gui.spin_freq.value() - cfg["center_freq"] / 1e6) < 1e-3

    print("[TEST] 3. Testing streaming start...")
    gui.toggle_streaming()
    assert gui.worker is not None
    assert gui.worker.isRunning()
    print("  Worker running successfully!")

    print("[TEST] 4. Letting worker stream 1.5 seconds of synthetic data...")
    start_t = time.time()
    while time.time() - start_t < 1.5:
        app.processEvents()
        time.sleep(0.05)

    print(f"  Live metric: Prx = {gui.lbl_metric_prx.text()}, State = {gui.card_state.text()}")

    print("[TEST] 5. Testing auto-zero baseline...")
    gui.trigger_autozero()
    app.processEvents()

    print("[TEST] 6. Testing snapshot export (.npz, .mat, .csv)...")
    export_dir = os.path.join(script_dir, "output", "snapshots")
    os.makedirs(export_dir, exist_ok=True)

    snapshot_done = []
    gui.worker.sig_snapshot_saved.connect(lambda p: snapshot_done.append(p))
    gui.worker.request_snapshot(export_dir, "headless_test_snapshot")

    # Wait for snapshot signal
    start_t = time.time()
    while time.time() - start_t < 3.0 and not snapshot_done:
        app.processEvents()
        time.sleep(0.05)

    assert len(snapshot_done) > 0, "sig_snapshot_saved was not received!"
    print(f"  Signal received: {snapshot_done[0]}")

    # Check that export files exist
    mat_files = [f for f in os.listdir(export_dir) if f.startswith("headless_test_snapshot") and f.endswith(".mat")]
    npz_files = [f for f in os.listdir(export_dir) if f.startswith("headless_test_snapshot") and f.endswith(".npz")]
    csv_files = [f for f in os.listdir(export_dir) if f.startswith("headless_test_snapshot") and f.endswith(".csv")]

    print(f"  Export verified: Found {len(mat_files)} .mat, {len(npz_files)} .npz, {len(csv_files)} .csv files.")
    assert len(mat_files) > 0, "No .mat file generated!"
    assert len(npz_files) > 0, "No .npz file generated!"
    assert len(csv_files) > 0, "No .csv file generated!"

    print("[TEST] 7. Testing streaming stop...")
    gui.toggle_streaming()
    assert gui.worker is None
    print("  Worker stopped cleanly.")

    gui.close()
    app.processEvents()
    app.quit()
    print("[SUCCESS] All headless GUI and Worker tests passed with 100% success!", flush=True)

if __name__ == "__main__":
    test_gui_headless()
