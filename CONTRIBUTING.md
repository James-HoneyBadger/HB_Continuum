# Contributing to HB Continuum

Public, operational FOSS project. Preserve explicit limitations; do not claim verified restoration, certified chain of custody or safe server deletion.

Use synthetic EML and isolated test archives only. Never commit real messages, credentials, exports or mailbox identifiers. Preserve read-only IMAP behavior, original-byte hashing and provenance; distinguish integrity checks from authenticity. Run `python3 -m unittest discover -s tests -v` and explicitly report untested live IMAP, GUI and recovery paths. Include regression tests for malformed input, failure recovery and privacy-sensitive changes. Keep documentation aligned with actual behavior.

Use focused branches and review changes before merging. Respect applicable licenses and provenance; do not assume permission to redistribute private or third-party material. No support timetable is promised; formal releases remain the owner's decision.

`main` is protected: changes arrive through a pull request, and CI (`test (3.12)`, `test (3.13)`, `typecheck`) plus CodeQL must pass before merging. Direct pushes are rejected even for the owner. Run `mypy` locally with the checked-in `mypy.ini`, and note that `check_untyped_defs` is off while the codebase remains unannotated.

Contributions are accepted under GPL-3.0-only. Submit only material you have the right to license on these terms; retain applicable third-party copyright and license notices.
