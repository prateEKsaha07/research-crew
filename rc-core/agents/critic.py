def critic(state: dict) -> dict:
    count = state["revision_count"]
    if count >= 1:
        return {
            "critique": "approved",
            "is_approved": True,
            "revision_count": count + 1,
            "confidence_scores": {
                "coverage": 8, "evidence": 9, "structure": 9, "clarity": 8, "avg": 8.5,
            },
        }
    return {
        "critique": "Add more citations in Key Findings",
        "is_approved": False,
        "revision_count": count + 1,
        "confidence_scores": {
            "coverage": 6, "evidence": 5, "structure": 8, "clarity": 7, "avg": 6.5,
        },
    }