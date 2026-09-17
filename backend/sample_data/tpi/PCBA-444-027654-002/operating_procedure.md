<!-- FIXTURE PENDING REAL CLIENT SAMPLES — pcba-tpi-generation. Placeholder only. -->
# Operating Procedure — PCBA 444-027654-002 (ESC Controller Board)

## Setup
1. Mount the board on the ESD-safe test fixture FX-102.
2. Connect J1 to the regulated supply; leave EN1 low until step 3.

## Operation
1. Power on the supply and confirm no fault LED.
2. Raise EN1 to begin the control loop.
3. Observe telemetry over the I2C bus at 1 Hz.

## Shutdown
1. Lower EN1, then power down the supply.
2. Discharge bulk capacitors before removing the board.

## Notes
Handle with wrist strap; board contains moisture-sensitive components.
