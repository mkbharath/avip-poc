TEST DATA — upload sample for pcba-tpi-generation (PCBA-778-100200-050, RF Power Amplifier Module)
# Operating Procedure — PCBA 778-100200-050 (RF Power Amplifier Module)

## Setup
1. Mount the RF Power Amplifier Module onto the heatsink fixture and torque the
   four M3 screws to 0.6 N·m.
2. Connect J1 (RF IN) to the source and J2 (RF OUT) to a 50-ohm load rated for
   at least 5 W.
3. Connect the 28 VDC bias supply to J3, observing the keyed connector polarity.

## Operation
1. Enable the 28 VDC bias first and allow the drain current to settle for 30 s.
2. Apply RF drive only after bias is stable; keep input drive at or below +5 dBm.
3. Monitor case temperature at TP4 during operation; do not exceed 85 degC.
4. If the drain current exceeds 400 mA, remove RF drive immediately and inspect.

## Shutdown
1. Remove RF drive first, then disable the 28 VDC bias supply.
2. Allow the module to cool below 40 degC before removing it from the fixture.
3. Cap the RF connectors J1 and J2 before storage.
