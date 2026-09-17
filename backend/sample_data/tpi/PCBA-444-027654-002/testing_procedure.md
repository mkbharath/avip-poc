<!-- FIXTURE PENDING REAL CLIENT SAMPLES — pcba-tpi-generation. Placeholder only. -->
# Testing Procedure — PCBA 444-027654-002 (ESC Controller Board)

## Purpose
Verify the ESC Controller Board meets electrical acceptance criteria prior to assembly.

## Test Steps
1. Visual inspection for solder bridging and missing components.
2. Apply 24 VDC to J1; confirm 3.3 V and 5.0 V rails within +/- 5%.
3. Measure quiescent current draw at J1 (expected 120-180 mA).
4. Toggle enable line EN1; confirm status LED D3 illuminates.
5. Verify I2C address response at 0x48 on connector J4.

## Expected Results
- All rails within tolerance.
- Quiescent current within stated band.
- Status LED responds to enable line.
- I2C device acknowledges at 0x48.

## Referenced Equipment
- Bench DC supply (0-30 V), calibrated DMM, I2C bus analyzer.
