"""Remove passwords and session tokens from Playwright traces before CI uploads them.

    python3 e2e/redact_diagnostics.py e2e/test-results

A trace records every request and action: the test accounts' passwords (typed into
the login form and sent to the API), the session cookie and the CSRF token. The
accounts are deleted after each test, but diagnostics must not carry credentials
at all. Passwords are replaced by value (listed in .fixtures/secrets.txt by the
tests); tokens by pattern. Standard library only, so it runs on the runner's Python.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

SECRETS = Path(__file__).resolve().parent / ".fixtures" / "secrets.txt"
REDACTED = "[redacted]"
PATTERNS = [
    re.compile(r"(ase_session=)[^;\s\"\\]+"),
    re.compile(r"(\"(?:csrf_token|password)\"\s*:\s*\")[^\"]*"),
    re.compile(r"(\"name\"\s*:\s*\"(?:ase_session|x-csrf-token)\"\s*,\s*\"value\"\s*:\s*\")[^\"]*", re.IGNORECASE),
    re.compile(r"(\"x-csrf-token\"\s*:\s*\")[^\"]*", re.IGNORECASE),
]


def redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        text = text.replace(secret, REDACTED)
    for pattern in PATTERNS:
        text = pattern.sub(rf"\g<1>{REDACTED}", text)
    return text


def redact_zip(path: Path, secrets: list[str]) -> None:
    with zipfile.ZipFile(path) as source:
        entries = [(info, source.read(info)) for info in source.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as target:
        for info, data in entries:
            try:
                data = redact(data.decode("utf-8"), secrets).encode("utf-8")
            except UnicodeDecodeError:
                pass  # screenshots and other binary resources
            target.writestr(info, data)


def main(folders: list[str]) -> None:
    secrets = [line for line in SECRETS.read_text().splitlines() if line] if SECRETS.is_file() else []
    for folder in folders:
        for path in Path(folder).rglob("*"):
            if path.suffix == ".zip":
                redact_zip(path, secrets)
            elif path.suffix in {".md", ".txt", ".json"}:
                path.write_text(redact(path.read_text(encoding="utf-8"), secrets), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
