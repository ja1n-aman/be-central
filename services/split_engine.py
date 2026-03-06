from decimal import Decimal, ROUND_DOWN


def compute_splits(
    amount: Decimal, members: list[dict], split_type: str
) -> list[dict]:
    """
    Compute the actual_amount for each member based on split_type.

    members: [{"user_id": str|None, "email": str|None, "value": Decimal}]
    Returns: [{"user_id", "email", "value", "actual_amount"}]
    """
    if split_type == "equal":
        return _split_equal(amount, members)
    elif split_type == "exact":
        return _split_exact(amount, members)
    elif split_type == "percentage":
        return _split_percentage(amount, members)
    elif split_type == "shares":
        return _split_shares(amount, members)
    else:
        raise ValueError(f"Unknown split_type: {split_type}")


def _split_equal(amount: Decimal, members: list[dict]) -> list[dict]:
    n = len(members)
    base = (amount / n).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    remainder = amount - (base * n)
    splits = []
    for i, m in enumerate(members):
        share = base + (remainder if i == n - 1 else Decimal("0"))
        splits.append({**m, "value": share, "actual_amount": share})
    return splits


def _split_exact(amount: Decimal, members: list[dict]) -> list[dict]:
    total = sum(m["value"] for m in members)
    if abs(total - amount) > Decimal("0.01"):
        raise ValueError(f"Exact splits sum to {total}, expected {amount}")
    return [{**m, "actual_amount": m["value"]} for m in members]


def _split_percentage(amount: Decimal, members: list[dict]) -> list[dict]:
    total_pct = sum(m["value"] for m in members)
    if abs(total_pct - Decimal("100")) > Decimal("0.01"):
        raise ValueError(f"Percentages sum to {total_pct}, expected 100")
    splits = []
    running_total = Decimal("0")
    for i, m in enumerate(members):
        if i == len(members) - 1:
            actual = amount - running_total
        else:
            actual = (amount * m["value"] / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_DOWN
            )
            running_total += actual
        splits.append({**m, "actual_amount": actual})
    return splits


def _split_shares(amount: Decimal, members: list[dict]) -> list[dict]:
    total_shares = sum(m["value"] for m in members)
    if total_shares <= 0:
        raise ValueError("Total shares must be positive")
    splits = []
    running_total = Decimal("0")
    for i, m in enumerate(members):
        if i == len(members) - 1:
            actual = amount - running_total
        else:
            actual = (amount * m["value"] / total_shares).quantize(
                Decimal("0.01"), rounding=ROUND_DOWN
            )
            running_total += actual
        splits.append({**m, "actual_amount": actual})
    return splits
