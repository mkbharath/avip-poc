# PCBA TPI Generation — Sample Fixtures

**Feature:** pcba-tpi-generation
**Status:** FIXTURES PENDING REAL CLIENT SAMPLES — do not treat as authoritative.

This directory holds a small set of sample PCBAs (target 3-5 per Req 10.1) used
to exercise the TPI generation pipeline end to end
(ingestion → extraction → generation → review → final TPI) with the multimodal
LLM provider on its **mock** default. Every file here is a clearly-marked
placeholder created for development; none is a real Lam Research document.

## Layout

```
sample_data/tpi/
  <PCBA-ID>/
    testing_procedure.md      # text input  (Word/PDF stand-in)
    operating_procedure.md    # text input  (Word/PDF stand-in)
    circuit_diagram.txt       # visual input stand-in [CONFIRM format]
    drawing.txt               # visual input stand-in [CONFIRM format]
  README.md
```

Each PCBA folder carries the four confirmed input types (FR2-1): testing
procedure, operating procedure, circuit diagram, drawing.

## Open [CONFIRM] items reflected here

These are surfaced, not silently resolved (see requirements.md "Open Items"):

- **Visual-input format.** The real file format of circuit diagrams and drawings
  is unconfirmed (CAD export, PDF, or image). The `circuit_diagram` and
  `drawing` fixtures are `.txt` stand-ins so the pipeline can run; the ingestion
  service detects and *reports* the format rather than assuming one (Req 1.3).
  Replace these with real-format samples once confirmed.
- **Client TPI template.** The client's own TPI template is not yet available.
  Generation uses the documented placeholder structure (test steps, expected
  results, referenced equipment) until the real template is provided
  (Req 3.2, 5.3); the template is swappable without touching extraction.
- **Human-authored TPI for validation.** No human-authored TPI is bundled here.
  If one is provided for a sample PCBA, the UI's optional side-by-side view
  becomes available (Req 10.3).
- **Full catalog size.** These 3-5 samples are the demonstration scope only;
  full-catalog coverage remains out of scope for this release (Req 10.4).

## Replacing the fixtures

When real client samples arrive, drop them into a per-PCBA folder using the same
four filenames (any extension), remove the placeholder stand-ins, and confirm
the visual-input format so `detected_format` reflects reality.
