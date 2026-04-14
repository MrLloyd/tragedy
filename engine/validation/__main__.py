"""
命令行：python -m engine.validation [--data-dir PATH]

默认校验仓库根目录下的 data/。存在任一 ValidationIssue 时退出码为 1。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engine.validation.runner import default_data_dir, validate_data_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate tragedy data/*.json contracts.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=f"path to data directory (default: {default_data_dir()})",
    )
    args = parser.parse_args()
    root = args.data_dir if args.data_dir is not None else default_data_dir()
    issues = validate_data_root(root)
    if not issues:
        print(f"OK: no issues under {root.resolve()}")
        sys.exit(0)
    for iss in issues:
        print(f"{iss.path}: {iss.message}")
    sys.exit(1)


if __name__ == "__main__":
    main()
