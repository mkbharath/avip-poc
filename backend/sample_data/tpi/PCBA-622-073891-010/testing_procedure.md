<!-- FIXTURE PENDING REAL CLIENT SAMPLES — pcba-tpi-generation. Placeholder only. -->
# Testing Procedure — PCBA 622-073891-010 (Sensor Interface Breakout Board)

## Purpose
Verify signal integrity and isolation on the sensor interface breakout.

## Test Steps
1. Visual inspection of isolation barrier and connector alignment.
2. Apply 5 VDC to J3; confirm isolated 5 V secondary rail.
3. Inject a 1 kHz test tone at each analog input; confirm passthrough gain of 1.0 +/- 2%.
4. Verify isolation resistance across the barrier exceeds 10 Mohm.
5. Confirm digital I/O levels at header J6 (3.3 V logic).

## Expected Results
- Isolated rail present and within tolerance.
- Analog passthrough gain within band.
- Isolation resistance above threshold.
- Digital levels correct.

## Referenced Equipment
- Function generator, insulation resistance meter, calibrated DMM, logic analyzer.
