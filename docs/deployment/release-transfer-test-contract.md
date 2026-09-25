# Release transfer regression test contract

The release-transfer unit tests must match the current SSM receiver's function contract. The one-time recovery helper `prepare_receive_ssm.build_commands` requires six arguments: AWS Region, bucket, original release tag, expected original-receiver SHA-256, expected patched-receiver SHA-256, and Base64 patch payload. An earlier regression test still called the retired three-argument helper and failed before it could verify checksum handling.

`test_release_transfer.py` now checks that signature explicitly, supplies all six inputs, and tests that generated recovery commands normalize carriage returns and check both checksums without changing uploaded S3 release files. It does not execute Linux Bash from native Windows Python. Shell-level checksum verification belongs in `test_receive_hotfix.py` and runs only on Linux CI; Windows runs portable byte-level coverage.

## Local validation (Windows + Git Bash)

From the OpsFlow repository root:

```bash
backend/.venv/Scripts/python.exe -m py_compile scripts/deployment/phase12_6/test_release_transfer.py
backend/.venv/Scripts/python.exe -m unittest discover -s scripts/deployment/phase12_6 -p test_release_transfer.py -v
backend/.venv/Scripts/python.exe -m unittest discover -s scripts/deployment/phase12_6 -p test_receive_hotfix.py -v
backend/.venv/Scripts/python.exe -m unittest discover -s scripts/deployment/phase12_6 -p test_runtime_preflight.py -v
```

The release-transfer suite contains eight tests. The Windows hotfix suite has one intentional Linux-only integration skip. All other tests must pass. These tests make no AWS infrastructure changes and do not rebuild, upload, or replace the existing release.

Before restarting the SSM transfer, verify the read-only S3 receiver diagnostic and that the original release manifest still refers to the intended Git commit. Do not commit corrections first if the helper still requires the original commit to remain at `HEAD`; preserve the existing S3 release until independently installed and verified on EC2.
