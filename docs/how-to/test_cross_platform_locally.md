---
title: "How-To: Test Cross-Platform Logic Locally with Wine and CI"
tags: ["how-to", "runbook", "testing", "wine", "cross-platform", "windows", "ci"]
created_at: "2026-10-07"
last_updated_at: "2026-10-07"
---

# How-To: Test Cross-Platform Logic Locally with Wine and CI

This runbook guides developers on verifying platform-specific code paths—such as the Win32 `WindowsPathStrategy` and Linux `LinuxProtonPathStrategy`—from a Linux workstation (`prd-mgr-01`) and via GitHub Actions.

---

## 1. Quick Local Verification (Tier 1 & 2 Fast-Path)

Everyday development on Linux does not require Wine or a Windows VM. To run unit tests and ctypes binary ABI layout checks:

```bash
# Execute full Tier 2 quality gates (Ruff, Mypy, Import Linter, Pytest)
python scripts/verify.py
```

To run only the Win32 binary ABI memory layout checks:
```bash
pytest tests/unit/test_windows_simulant.py -v
```

---

## 2. Testing Windows Execution Locally via Wine (Tier 3)

If you have made modifications to Windows-specific code (e.g. `ctypes.windll` or `winreg`) and want to test them against an authentic Windows runtime on your Linux machine without pushing to CI:

### Step 1: Provision the Isolated Wine Environment
Run the setup script. This checks for system Wine packages and downloads an isolated, portable Windows Python runtime into `.cache/winepfx/`:

```bash
./scripts/setup_wine_simulant.sh
```

> **Note:** If `wine` is not installed on your host, install it via:
> ```bash
> sudo apt-get update && sudo apt-get install -y wine64 wine-binfmt
> ```

### Step 2: Execute Tests Under Windows Python
Run the test launcher script:

```bash
./scripts/run_wine_tests.sh
```

This executes `python.exe` inside the isolated Wine prefix, exercising the real C-extension `winreg` and Windows system DLLs.

---

## 3. Native Windows CI Verification (Tier 4)

When you push code or open a Pull Request, GitHub Actions automatically executes our test suite across both:
* **`ubuntu-latest`:** Verifies POSIX and Linux Steam Proton discovery.
* **`windows-latest`:** Verifies Win32 NT kernel APIs, real Known Folders (`FOLDERID_SavedGames`), and registry operations on a native Windows 11 / Server VM.

### Inspecting Results
Check the **CI Pipeline** workflow status on GitHub:
* If the `ubuntu-latest` job passes but `windows-latest` fails, inspect Windows path separators (`\` vs `/`), file access modes, or ctypes struct alignments.
