# Training Smoke Guide

## SWIFT
- Train smoke:
  - `bash training/swift/train_swift.sh`
- Eval smoke:
  - `bash training/swift/eval_swift.sh`

Scripts intentionally fallback to smoke success when runtime dependencies are missing (no GPU / no framework).

## VERL
- Run smoke:
  - `bash training/verl/run_verl.sh training/verl/config/smoke.yaml`

If VERL runtime is unavailable, script prints a clear fallback message and exits with success.
