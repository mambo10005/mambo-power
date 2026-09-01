# M1 environment attestation — uv + Python toolchain

Date: 2026-08-20. Machine: Windows 11 Pro 10.0.26200, Git Bash. Recorded by the M1 pre-flight subagent.
Every block below is the command run followed by its output, trimmed to the relevant lines.

## Summary

| Item | Value |
|---|---|
| uv binary | `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts\uv.exe` |
| uv version | `uv 0.12.5 (210d1f678 2026-08-14 x86_64-pc-windows-msvc)` |
| uv on PATH (fresh Git Bash) | **No** — add `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts` (Git Bash: `/c/Users/mambo/AppData/Roaming/Python/Python314/Scripts`) |
| Project interpreter | CPython 3.12.14, `C:\Users\mambo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe` (resolved by `uv python find 3.12`) |
| `python3.12` on PATH (fresh Git Bash) | Yes — uv wrote a launcher to `C:\users\mambo\.local\bin\python3.12.exe`, which is already on PATH |
| Installed CPythons visible to uv | 3.14.2 (system, `%LOCALAPPDATA%\Python\pythoncore-3.14-64`), 3.12.14 (uv-managed) |

Nothing under `/c/Users/mambo/AppData/Local/Temp/claude/C--Claude-Projects-mambo-power/0d397067-49ef-4969-aefa-5709948393ef/scratchpad/bionic-unified` was touched except this file. No pyproject, venv, or lockfile was created.

## 1. Install uv

```
$ uv run --project "/c/Claude Projects/mambo-power" python --version
Python 3.14.2

$ uv run --project "/c/Claude Projects/mambo-power" python -m pip install --user uv
Installing collected packages: uv
Successfully installed uv-0.12.5
```

(pip also printed an upgrade notice, 25.3 -> 26.2.1; ignored.)

## 2. Locate the binary and check PATH

```
$ uv run --project "/c/Claude Projects/mambo-power" python -m pip show -f uv | grep -iE "^Location|uv\.exe"
Location: C:\Users\mambo\AppData\Roaming\Python\Python314\site-packages
  ..\Scripts\uv.exe

$ ls -la "$APPDATA/Python/Python314/Scripts/uv.exe"
-rwxr-xr-x 1 mambo 197121 51103232 Aug 20 14:54 C:\Users\mambo\AppData\Roaming/Python/Python314/Scripts/uv.exe

$ ls "$HOME/.local/bin/uv.exe" "$LOCALAPPDATA/Python/pythoncore-3.14-64/Scripts/uv.exe"
ls: cannot access ... No such file or directory   (both — pip --user did not place uv there)

$ "$APPDATA/Python/Python314/Scripts/uv.exe" --version
uv 0.12.5 (210d1f678 2026-08-14 x86_64-pc-windows-msvc)

$ bash -lc 'which uv'
which: no uv in (...)     # fresh login shell: NOT on PATH

$ echo "$PATH" | tr ':' '\n' | grep -iE "python|\.local"
/c/Users/mambo/AppData/Local/Programs/Python/Python313/Scripts
/c/Users/mambo/AppData/Local/Programs/Python/Python313
/c/users/mambo/.local/bin
/c/Users/mambo/AppData/Local/Python/bin
```

PATH fix required for bare `uv` to work: add `C:\Users\mambo\AppData\Roaming\Python\Python314\Scripts`
(user-level PATH via Windows settings, or `export PATH="$APPDATA/Python/Python314/Scripts:$PATH"` in `~/.bashrc`).
Until then, invoke as `uv run --project "/c/Claude Projects/mambo-power" python -m uv ...` (works from any shell where `python` is 3.14) or by absolute path.

## 3. Python versions

```
$ uv python list          # before install; trimmed to CPython rows
cpython-3.15.0rc1-windows-x86_64-none    <download available>
cpython-3.14.7-windows-x86_64-none       <download available>
cpython-3.14.2-windows-x86_64-none       C:\Users\mambo\AppData\Local\Python\pythoncore-3.14-64\python.exe
cpython-3.14.2-windows-x86_64-none       C:\Users\mambo\AppData\Local\Python\bin\python.exe   (+ python3.exe, python3.14.exe)
cpython-3.13.15-windows-x86_64-none      <download available>
cpython-3.12.14-windows-x86_64-none      <download available>
cpython-3.11.16-windows-x86_64-none      <download available>
cpython-3.10.21-windows-x86_64-none      <download available>
cpython-3.9.25-windows-x86_64-none       <download available>
cpython-3.8.20-windows-x86_64-none       <download available>
(pypy 3.8–3.11 and graalpy 3.10–3.12 also listed as downloadable; omitted)

$ uv python install 3.12
Downloading cpython-3.12.14-windows-x86_64-none (download) (21.0MiB)
 Downloaded cpython-3.12.14-windows-x86_64-none (download)
Installed Python 3.12.14 in 9.08s
 + cpython-3.12.14-windows-x86_64-none (python3.12.exe)

$ uv python find 3.12
C:\Users\mambo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe

$ uv python list --only-installed    # after
cpython-3.14.2-windows-x86_64-none     C:\Users\mambo\AppData\Local\Python\pythoncore-3.14-64\python.exe
cpython-3.14.2-windows-x86_64-none     C:\Users\mambo\AppData\Local\Python\bin\python3.exe
cpython-3.14.2-windows-x86_64-none     C:\Users\mambo\AppData\Local\Python\bin\python3.14.exe
cpython-3.14.2-windows-x86_64-none     C:\Users\mambo\AppData\Local\Python\bin\python.exe
cpython-3.12.14-windows-x86_64-none    C:\users\mambo\.local\bin\python3.12.exe
cpython-3.12.14-windows-x86_64-none    C:\Users\mambo\AppData\Roaming\uv\python\cpython-3.12.14-windows-x86_64-none\python.exe
cpython-3.12.14-windows-x86_64-none    C:\Users\mambo\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe

$ bash -lc 'which python3.12; python3.12 --version'
/c/users/mambo/.local/bin/python3.12
Python 3.12.14
```

Note: the PATH also carries `...\Programs\Python\Python313` and pyenv-win shims, but `uv python list` did not
report a 3.13 interpreter there — that directory appears to be stale (unverified beyond uv's scan).

## Exit condition

- `uv --version` succeeds: yes (`uv 0.12.5`).
- `uv python find 3.12` resolves: yes (`...\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\python.exe`).
