TEST DATA — upload sample for pcba-tpi-generation (PCBA-778-100200-050, RF Power Amplifier Module)
# Testing Procedure — PCBA 778-100200-050 (RF Power Amplifier Module)

## Purpose
Verify the RF Power Amplifier Module meets RF gain, return-loss, and thermal
acceptance criteria before it is released to the enclosure assembly line.

## Test Steps
1. Visual inspection of the RF connectors (J1 IN, J2 OUT) for bent pins and of
   the amplifier die U7 for solder voids.
2. Apply 28.0 VDC bias to J3; confirm the drain current settles to 210-260 mA
   with no RF drive applied (quiescent bias check).
3. Inject a -10 dBm CW tone at 2.45 GHz into J1; measure small-signal gain at
   J2 and confirm 18.0 dB +/- 1.0 dB.
4. Sweep input from -10 dBm to +5 dBm; confirm the 1 dB compression point (P1dB)
   at the output is at or above +33 dBm.
5. Measure input return loss at J1 across 2.40-2.50 GHz; confirm better than
   -14 dB across the band.
6. Run the module at full drive for 10 minutes; confirm the case temperature at
   thermocouple pad TP4 stays below 85 degC.

## Expected Results
- Quiescent drain current within the 210-260 mA band.
- Small-signal gain 18.0 dB +/- 1.0 dB at 2.45 GHz.
- Output P1dB at or above +33 dBm.
- Input return loss better than -14 dB across 2.40-2.50 GHz.
- Case temperature below 85 degC after 10 minutes at full drive.

## Referenced Equipment
- Vector network analyzer (10 MHz - 6 GHz), calibrated signal generator,
  RF power meter with 3 GHz-capable head, bench DC supply (0-30 V, 3 A),
  and a calibrated thermocouple thermometer.
