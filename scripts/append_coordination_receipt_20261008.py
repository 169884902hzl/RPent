"""Append a prepared receipt through git apply while preserving concurrent edits."""

import argparse
import fcntl
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coordination", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    target = args.coordination.resolve(strict=True)
    receipt = args.receipt.resolve(strict=True).read_text().strip() + "\n"
    with target.open("r") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        original = stream.read()
        if receipt in original:
            print("Receipt already present")
            return
        if not original.endswith("\n"):
            raise ValueError("Coordination file must end with a newline before append")
        count = len(original.splitlines())
        added = ["", *receipt.splitlines(), ""]
        patch = (f"--- a/{target.name}\n+++ b/{target.name}\n"
                 f"@@ -{count},0 +{count + 1},{len(added)} @@\n"
                 + "".join("+" + line + "\n" for line in added))
        subprocess.run(["git", "apply", "--unidiff-zero", "--whitespace=nowarn", "-"],
                       input=patch, text=True, cwd=target.parent, check=True)
        fcntl.flock(stream, fcntl.LOCK_UN)
    print(f"Appended {args.receipt.name}")


if __name__ == "__main__":
    main()
