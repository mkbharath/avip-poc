<!-- FIXTURE PENDING REAL CLIENT SAMPLES — pcba-tpi-generation. Placeholder only. -->
# Testing Procedure — PCBA 444-027654-003 (RF Driver Board)

## Purpose
Verify RF driver output and gain acceptance criteria before integration.

## Test Steps
1. Visual inspection of RF shielding and connector seating.
2. Apply 12 VDC to J2; confirm bias rail at 8.0 V +/- 3%.
3. Inject a 100 MHz, -10 dBm signal at RFin.
4. Measure gain at RFout (expected 18-22 dB).
5. Confirm harmonic suppression better than -30 dBc.

## Expected Results
- Bias rail within tolerance.
- Gain within stated band.
- Harmonic suppression meets threshold.

## Referenced Equipment
- RF signal generator, spectrum analyzer, calibrated 50-ohm loads.
