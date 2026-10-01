"""Use the registered v5r measured-requirement completion bands."""

PROGRESS_CHOICES = dict(zip(map(str, range(5)), (
    "0: no measured requirements complete",
    "1: less than half complete",
    "2: at least half but less than three quarters complete",
    "3: at least three quarters complete, requirements remain",
    "4: all complete",
)))
PROGRESS_QUESTION = "Which measured completion band applies to the current instruction?"


def measured_progress(completed, total):
    if total <= 0 or not 0 <= completed <= total:
        raise ValueError("progress requires explicit nonempty requirement counts")
    fraction = completed / total
    level = (0 if fraction == 0 else 1 if fraction < .5 else
             2 if fraction < .75 else 3 if fraction < 1 else 4)
    return str(level), {"kind": "explicit_requirement_fraction", "fraction": fraction,
                        "satisfied_count": completed, "total_count": total}
