#!/usr/bin/env python3
"""
Save the ESP32 logger's serial output to a CSV file that calibrate.py reads directly.

    pip install pyserial
    python3 serial_to_csv.py COM5 data/cell1/T2_heating.csv            (Windows)
    python3 serial_to_csv.py /dev/ttyUSB0 data/cell1/T4_soc50.csv      (Linux / macOS)

Stop with Ctrl+C. Lines starting with '#' (including alarms) are kept as comments, which calibrate.py
ignores. Alarms are also printed on screen.

For T1 / T4 files, calibrate.py needs t_s,V,I_A,T_C; the extra Tamb_C column is ignored.
For T2_heating.csv, the Tamb_C column is used.
"""
import sys, serial

def main():
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(1)
    port, path = sys.argv[1], sys.argv[2]
    n = 0
    with serial.Serial(port, 115200, timeout=2) as ser, open(path, "w", newline="") as f:
        print(f"logging {port} -> {path}  (Ctrl+C to stop)")
        try:
            while True:
                line = ser.readline().decode(errors="replace").strip()
                if not line: continue
                f.write(line + "\n"); f.flush()
                if line.startswith("#"):
                    print(line)
                else:
                    n += 1
                    if n % 50 == 0: print(f"{n} samples, last: {line}")
        except KeyboardInterrupt:
            print(f"\nstopped, {n} samples written to {path}")

if __name__ == "__main__":
    main()
