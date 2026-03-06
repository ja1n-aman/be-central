async def send_invite_email(
    to_email: str, invite_token: str, group_name: str, inviter_name: str
) -> None:
    """STUB — just log/print. Replace with real email sending in production."""
    print(f"[EMAIL STUB] Would send invite to {to_email}")
    print(f"  Link: splitsmart://invite?token={invite_token}")
    print(f"  Group: {group_name}, Invited by: {inviter_name}")
