# Windows-safe release-transfer tests

The release receiver's checksum normalization is verified in two distinct ways:

- **Portable tests** check the exact bytes of the patched receiver and normalize a CRLF checksum manifest without launching Bash or creating temporary directories. These tests run under native Windows Python, Linux and macOS.
- **Linux integration test** invokes Bash and `sha256sum` against real CRLF checksum entries, preserving the original manifest. Native Windows Python skips this test; CI should run it on Linux.

## Why the previous tests failed

Detecting `bash` on a Windows PATH is not sufficient to make `subprocess.run(["bash", ...])` portable. Native Python passes Windows-style temporary paths that Git Bash does not necessarily understand. The failed process launch triggered a Windows temporary-directory cleanup exception, which was a secondary error.

## Apply only the test correction

Extract the fix ZIP to an ignored staging directory. Copy only `test_receive_hotfix.py` to `scripts/deployment/phase12_6/`. Do not copy test fixtures into production and do not modify the uploaded release, release manifest or existing S3 artifacts.

Validate locally:

```bash
backend/.venv/Scripts/python.exe -m py_compile scripts/deployment/phase12_6/test_receive_hotfix.py
backend/.venv/Scripts/python.exe -m unittest discover -s scripts/deployment/phase12_6 -p test_receive_hotfix.py -v
```

Expected native Windows result: **7 tests, 1 expected Linux-only skip, 0 failures**. Linux CI with `bash`, `tr` and `sha256sum` should execute all seven tests without a skip.

## Resume the existing release only after tests pass

Confirm that `git rev-parse HEAD` still matches `.opsflow-migration/phase12-6d/release.json`. Preserve the original uploaded artifacts. Run the existing read-only `verify_staged_receiver.py`, regenerate the SSM command using the previously corrected `prepare_receive_ssm.py`, then submit one new command and inspect its result. Do not commit before the original release is verified on EC2, because the receiver recovery helper checks the current release commit.

Do not run `terraform apply`, rebuild images, overwrite the existing S3 release or retry a failed SSM command without inspecting the latest error. After successful transfer, independently verify the release marker, production Compose file and three images on EC2; then commit the recovery scripts, tests and this documentation as a separate change.
