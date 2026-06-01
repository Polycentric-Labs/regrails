# RegRails — rule-to-scenario coverage matrix

_31/37 encoded rules are exercised by at least one of 22 golden scenarios. This is a proof-of-concept: partial coverage is expected and the gaps below are intentional and visible._

| Rule | Framework | Section | Risk | # scenarios | Scenarios |
| --- | --- | --- | --- | --- | --- |
| `FERPA-99.30-1` | FERPA | `34-CFR-99.30` | - | 12 | ferpa-aggregate-research-allow, ferpa-directory-optedout-block, ferpa-directory-roster-escalate, ferpa-emergency-allow, ferpa-empty-default-block, ferpa-gpa-default-block, ferpa-parent-auditlog-allow, ferpa-redisclosure-block, ferpa-ssn-combined-block, ferpa-studies-noagreement-escalate, ferpa-vendor-unverified, ferpa-vendor-verified |
| `FERPA-99.30-2` | FERPA | `34-CFR-99.30` | - | 12 | ferpa-aggregate-research-allow, ferpa-directory-optedout-block, ferpa-directory-roster-escalate, ferpa-emergency-allow, ferpa-empty-default-block, ferpa-gpa-default-block, ferpa-parent-auditlog-allow, ferpa-redisclosure-block, ferpa-ssn-combined-block, ferpa-studies-noagreement-escalate, ferpa-vendor-unverified, ferpa-vendor-verified |
| `FERPA-99.30-3` | FERPA | `34-CFR-99.30` | - | 0 | _(none — gap)_ |
| `FERPA-99.31-A1` | FERPA | `34-CFR-99.31` | - | 2 | ferpa-vendor-unverified, ferpa-vendor-verified |
| `FERPA-99.31-A1B` | FERPA | `34-CFR-99.31` | - | 2 | ferpa-vendor-unverified, ferpa-vendor-verified |
| `FERPA-99.31-A3` | FERPA | `34-CFR-99.31` | - | 0 | _(none — gap)_ |
| `FERPA-99.31-A4` | FERPA | `34-CFR-99.31` | - | 0 | _(none — gap)_ |
| `FERPA-99.31-A6` | FERPA | `34-CFR-99.31` | - | 2 | ferpa-aggregate-research-allow, ferpa-studies-noagreement-escalate |
| `FERPA-99.31-A9` | FERPA | `34-CFR-99.31` | - | 0 | _(none — gap)_ |
| `FERPA-99.31-A10` | FERPA | `34-CFR-99.31` | - | 1 | ferpa-emergency-allow |
| `FERPA-99.31-B1` | FERPA | `34-CFR-99.31` | - | 1 | ferpa-aggregate-research-allow |
| `FERPA-99.32-A1` | FERPA | `34-CFR-99.32` | - | 12 | ferpa-aggregate-research-allow, ferpa-directory-optedout-block, ferpa-directory-roster-escalate, ferpa-emergency-allow, ferpa-empty-default-block, ferpa-gpa-default-block, ferpa-parent-auditlog-allow, ferpa-redisclosure-block, ferpa-ssn-combined-block, ferpa-studies-noagreement-escalate, ferpa-vendor-unverified, ferpa-vendor-verified |
| `FERPA-99.32-A5` | FERPA | `34-CFR-99.32` | - | 2 | ferpa-emergency-allow, ferpa-parent-auditlog-allow |
| `FERPA-99.33-A1` | FERPA | `34-CFR-99.33` | - | 1 | ferpa-redisclosure-block |
| `FERPA-99.33-A2` | FERPA | `34-CFR-99.33` | - | 0 | _(none — gap)_ |
| `FERPA-99.33-C` | FERPA | `34-CFR-99.33` | - | 1 | ferpa-redisclosure-block |
| `FERPA-99.36-A` | FERPA | `34-CFR-99.36` | - | 1 | ferpa-emergency-allow |
| `FERPA-99.36-C` | FERPA | `34-CFR-99.36` | - | 1 | ferpa-emergency-allow |
| `FERPA-99.36-B1` | FERPA | `34-CFR-99.36` | - | 0 | _(none — gap)_ |
| `FERPA-99.37-A` | FERPA | `34-CFR-99.37` | - | 2 | ferpa-directory-optedout-block, ferpa-directory-roster-escalate |
| `FERPA-99.37-A-OPT-OUT` | FERPA | `34-CFR-99.37` | - | 2 | ferpa-directory-optedout-block, ferpa-directory-roster-escalate |
| `FERPA-99.37-C` | FERPA | `34-CFR-99.37` | - | 2 | ferpa-directory-optedout-block, ferpa-directory-roster-escalate |
| `FERPA-99.37-E` | FERPA | `34-CFR-99.37` | - | 3 | ferpa-directory-optedout-block, ferpa-directory-roster-escalate, ferpa-ssn-combined-block |
| `TIV-668.34-A1` | Title IV | `34-CFR-668.34` | low | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.34-A3i` | Title IV | `34-CFR-668.34` | low | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.34-A4ii` | Title IV | `34-CFR-668.34` | medium | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.34-MAXTF` | Title IV | `34-CFR-668.34` | medium | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.34-A7` | Title IV | `34-CFR-668.34` | high | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.34-A8i` | Title IV | `34-CFR-668.34` | medium | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.34-A8ii` | Title IV | `34-CFR-668.34` | medium | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.34-A9ii` | Title IV | `34-CFR-668.34` | medium | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.32-A1i` | Title IV | `34-CFR-668.32` | medium | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.32-E1` | Title IV | `34-CFR-668.32` | medium | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.32-F` | Title IV | `34-CFR-668.32` | medium | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.32-G1` | Title IV | `34-CFR-668.32` | high | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.32-G2` | Title IV | `34-CFR-668.32` | medium | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |
| `TIV-668.32-I` | Title IV | `34-CFR-668.32` | medium | 9 | tiv-determination-insufficient-facts, tiv-eligibility-determination-humanreview, tiv-failed-sap-determination-humanreview, tiv-general-question-allow, tiv-loan-default-humanreview, tiv-probation-allow, tiv-probation-appeal-allow, tiv-sap-explainer-allow, tiv-warning-allow |

## Coverage gaps (6 rules with no scenario)

- `FERPA-99.30-3` (34-CFR-99.30) — no golden scenario exercises it yet.
- `FERPA-99.31-A3` (34-CFR-99.31) — no golden scenario exercises it yet.
- `FERPA-99.31-A4` (34-CFR-99.31) — no golden scenario exercises it yet.
- `FERPA-99.31-A9` (34-CFR-99.31) — no golden scenario exercises it yet.
- `FERPA-99.33-A2` (34-CFR-99.33) — no golden scenario exercises it yet.
- `FERPA-99.36-B1` (34-CFR-99.36) — no golden scenario exercises it yet.

