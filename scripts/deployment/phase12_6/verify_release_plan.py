"""Verify that only the six Phase 12.6D temporary resources change.

Usage: terraform show -json saved.tfplan | python verify_release_plan.py create|cleanup
"""
import json
import sys

EXPECTED = {
    "aws_s3_bucket.live_release_transfer",
    "aws_s3_bucket_public_access_block.live_release_transfer",
    "aws_s3_bucket_server_side_encryption_configuration.live_release_transfer",
    "aws_s3_bucket_policy.live_release_transfer_https",
    "aws_s3_bucket_lifecycle_configuration.live_release_transfer",
    "aws_iam_role_policy.live_release_transfer",
}


def validate(plan: dict, mode: str) -> tuple[bool, str]:
    if mode not in {"create", "cleanup"}:
        return False, "Mode must be create or cleanup."
    desired = ["create"] if mode == "create" else ["delete"]
    actual = {}
    for resource in plan.get("resource_changes", []):
        if resource.get("mode") != "managed":
            continue
        actions = resource["change"]["actions"]
        if actions != ["no-op"]:
            actual[resource["address"]] = actions
    expected = {name: desired for name in EXPECTED}
    if actual != expected:
        return False, (
            "Unexpected resource changes.\n"
            + "Expected: " + repr(expected) + "\n"
            + "Actual:   " + repr(actual)
        )
    return True, f"PASS: Exactly six temporary release resources will be {'created' if mode == 'create' else 'deleted'}; permanent resources unchanged."


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: verify_release_plan.py create|cleanup", file=sys.stderr)
        return 2
    try:
        plan = json.load(sys.stdin)
    except ValueError as exc:
        print(f"FAIL: Invalid plan JSON: {exc}", file=sys.stderr)
        return 1
    ok, message = validate(plan, sys.argv[1])
    print(message, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
