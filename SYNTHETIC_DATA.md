# Synthetic Data Notice

**All student data, names, IDs, and records used by this project are entirely synthetic. No real personally identifiable information from any educational record exists anywhere in this repository, its tests, its demo transcripts, or its documentation.**

## Why this notice exists

RegRails is a proof-of-concept for codifying FERPA (34 CFR Part 99) into machine-readable rules and demonstrating how an AI advisor would consult those rules before answering questions about student data. To make the demo concrete and runnable, the project must use *some* example data — student names, queries, contexts.

All such data is fabricated. Specifically:

- The names used in `demo/queries.txt` (e.g., "Jane Doe", "Lincoln High School") are textbook placeholders with no connection to any real person or institution.
- The demo's mock student-record fixtures (`tests/conftest.py`) are generated for testing only and contain no real records.
- The hypothetical "school official" / "outsourced vendor" scenarios in the research-stream queries reference *categories* of actors, never named individuals.

## What this project does NOT do

- It does NOT collect, store, transmit, or process any real student records.
- It does NOT integrate with any Student Information System (SIS), Learning Management System (LMS), or institutional database.
- It does NOT recommend that any educational institution use this code to make actual FERPA-disclosure decisions about real students. (For that, you need a production system, an institutional FERPA officer, and legal review — none of which is what a weekend proof-of-concept replaces.)

## Reporting concerns

If you believe this repository contains real PII or any data resembling real student records, please open an issue at <https://github.com/Polycentric-Labs/regrails/issues> or contact the maintainer directly at allen@allenfbyrd.com. The maintainer will treat such reports as a security incident and respond within 24 hours.
