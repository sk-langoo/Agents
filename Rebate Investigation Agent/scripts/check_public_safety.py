"""Scan the files Git would upload, without printing any matched secret values."""

from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SENSITIVE_NAMES = {".env", "credentials.json", "secrets.json", "id_rsa"}
SENSITIVE_SUFFIXES = {".pem", ".p12", ".pfx", ".key"}
PATTERNS = {
    "OpenAI-style API key": re.compile(rb"sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}"),
    "GitHub token": re.compile(rb"(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_)[A-Za-z0-9_]{20,}"),
    "private key block": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "personal home path": re.compile(b"/" + rb"Users/[^/\s\"']+/"),
    "email address": re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
}


def repository_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=PROJECT_DIR,
        capture_output=True,
        check=True,
        text=True,
    )
    return Path(result.stdout.strip())


def candidate_paths(root: Path) -> list[Path]:
    command = ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    result = subprocess.run(command, cwd=root, capture_output=True, check=True)
    return [root / part.decode("utf-8") for part in result.stdout.split(b"\0") if part]


def scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    name = path.name.casefold()
    if name in SENSITIVE_NAMES or name.startswith(".env.") or path.suffix.casefold() in SENSITIVE_SUFFIXES:
        findings.append("credential-like filename")
    if path.is_symlink():
        findings.append("symlink")
        return findings
    if not path.is_file():
        return findings

    try:
        if path.suffix.casefold() == ".xlsx":
            with zipfile.ZipFile(path) as workbook:
                contents = b"\n".join(
                    workbook.read(name)
                    for name in workbook.namelist()
                    if name.endswith((".xml", ".rels"))
                )
        else:
            contents = path.read_bytes()
    except (OSError, zipfile.BadZipFile) as error:
        return findings + [f"could not inspect ({type(error).__name__})"]

    for label, pattern in PATTERNS.items():
        if pattern.search(contents):
            findings.append(label)
    return findings


def main() -> int:
    try:
        root = repository_root()
        paths = candidate_paths(root)
    except (OSError, subprocess.CalledProcessError):
        print("Initialize Git in this folder before running the public-safety scan.")
        return 2
    print(f"Checking {len(paths)} files that Git could include...")
    findings = [(path.relative_to(root), scan_file(path)) for path in paths]
    unsafe = [(path, problems) for path, problems in findings if problems]
    for path, problems in unsafe:
        print(f"REVIEW {path}: {', '.join(problems)}")
    if unsafe:
        print("Public-safety scan FAILED. Do not publish until these findings are resolved.")
        return 1
    print("Public-safety scan passed. No recognized secrets or personal paths found.")
    print("This is a safety check, not a guarantee; review staged changes before pushing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
