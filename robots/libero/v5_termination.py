# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Evidence-based terminal bookkeeping, independent of the finish score."""

V2_CATEGORIES = ("success", "grasp_failure_abandonment", "skill_execution_error", "unresolved_ask_help")


def classify_v2(result, action, receipts):
    """Return a supported new category, or None to retain the existing cause."""
    if result.get("official_success") and result.get("native_terminated"):
        return "success", "official solved and native termination; explicit finish counted separately"
    substantive = [r for r in receipts if r.get("tool") not in
                   ("finish", "ask_help", "retreat", "reperceive")]
    recent = substantive[-1] if substantive else {}
    if recent.get("error") or recent.get("verification") == "execution_error":
        return "skill_execution_error", str(recent.get("error", "execution_error receipt"))
    if getattr(action, "tool", None) == "ask_help":
        if recent.get("tool") in ("grasp", "regrasp_restage") and recent.get("grasp_verified") is False:
            return "grasp_failure_abandonment", "failed grasp verification followed by ask_help"
        return "unresolved_ask_help", "ask_help without sufficient evidence for a physical root cause"
    return None
