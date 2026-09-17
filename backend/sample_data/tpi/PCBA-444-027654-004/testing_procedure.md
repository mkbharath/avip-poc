<!-- FIXTURE PENDING REAL CLIENT SAMPLES — pcba-tpi-generation. Placeholder only. -->
# Testing Procedure — PCBA 444-027654-004 (Power Distribution Board)

## Purpose
Verify distribution rails, current limits, and fault behavior.

## Test Steps
1. Visual inspection of high-current traces and connector torque.
2. Apply 48 VDC to J5; confirm 12 V and 5 V distribution rails.
3. Load each output to rated current; confirm regulation within +/- 4%.
4. Trigger an overcurrent event; confirm the rail trips and latches.
5. Confirm fault flag asserts on the status header J7.

## Expected Results
- Rails within tolerance under full load.
- Overcurrent protection latches as specified.
- Fault flag asserts on trip.

## Referenced Equipment
- Programmable electronic load, 48 V bench supply, calibrated DMM, oscilloscope.
