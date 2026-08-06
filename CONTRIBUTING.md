# Contributing

Corrections are welcome, especially when they make the model easier to audit or expose a result that depends on an assumption we overlooked.

Before opening a pull request:

1. Read the relevant protocol in `study/` and the known deviations in `study/DEVIATIONS.md`.
2. Keep real hospital information out of the repository.
3. Add or update a test when changing model behavior.
4. Run `pytest` and `python -m grrc.cli validate --no-report`.
5. Explain whether the change affects previously generated CSV files, figures, or manuscript claims.

Please do not silently regenerate frozen data. If a correction changes a study output, preserve the original file, document the reason, use fresh scenario identifiers where appropriate, and update the analysis manifest.

Small documentation corrections can be submitted directly. Larger model changes should begin with an issue describing the scientific reason for the change.
