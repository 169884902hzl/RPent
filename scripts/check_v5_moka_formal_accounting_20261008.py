"""Formal accounting distinguishes measured no-execution from startup failure."""


def check_formal_rows(rows):
    if not rows:
        raise ValueError("formal run produced no episode records")
    physical, no_execution = [], []
    for row in rows:
        result, receipt = row.get("result", {}), row.get("first_receipt", {})
        name = row.get("case", {}).get("name", "unknown")
        if (result.get("status") in ("startup", "startup_error")
                or result.get("infrastructure_failure") or row.get("case_had_infrastructure_failure")
                or row.get("raised_error") or receipt.get("verification") == "execution_error"):
            raise ValueError("startup/infrastructure/execution error: " + name)
        controls = row.get("server_chunk_execution") or {}
        requested = int(controls.get("requested_controls", 0))
        if requested > 0:
            physical.append(name)
        elif (requested == 0 and result.get("status") == "completed"
                and receipt.get("executed") is False
                and row.get("executed_vla_actions") == 0
                and row.get("executed_public_motion_actions") == 0):
            no_execution.append({"case_name": name, "failure_reason": receipt.get("failure_reason"),
                                 "outcome": "unknown", "retained_in_registered_denominator": True})
        else:
            raise ValueError("zero controls without completed explicit no-execution evidence: " + name)
    return {"status": "pass", "episodes": len(rows), "physical_execution_cases": physical,
            "legitimate_no_execution_cases": no_execution,
            "no_execution_is_not_startup_error": True,
            "no_execution_is_not_a_private_failure_label": True}
