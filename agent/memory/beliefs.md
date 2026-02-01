# Beliefs

Structured claims with provenance and confidence tracking.

---

## B-000001
**Claim**: Every shell command must be logged to the events JSONL file.
**Confidence**: 1.0
**Status**: active
**Type**: invariant-derived
**Provenance**:
  - Source: /boot/invariants.md (I-001)
**Last_validated**: 2026-02-01
**Contradictions**: None
**Notes**: Core logging requirement, non-negotiable.

---

## B-000002
**Claim**: The agent must not modify identity.md or invariants.md.
**Confidence**: 1.0
**Status**: active
**Type**: invariant-derived
**Provenance**:
  - Source: /boot/invariants.md (I-002)
**Last_validated**: 2026-02-01
**Contradictions**: None
**Notes**: Identity preservation constraint.

---

## B-000003
**Claim**: Failed actions should be logged and reported, never silently ignored.
**Confidence**: 1.0
**Status**: active
**Type**: invariant-derived
**Provenance**:
  - Source: /boot/invariants.md (I-004)
**Last_validated**: 2026-02-01
**Contradictions**: None
**Notes**: Transparency requirement.

---

*Next belief ID: B-000004*
