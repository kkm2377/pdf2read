from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

try:
    import resource
except ImportError:  # Windows
    resource = None

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pdf2read.convert import convert_book
from tests.fixtures.builders import build_large_pdf
from tests.quality.harness import audit_output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=200)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="pdf2read-bench-") as directory:
        root = Path(directory)
        pdf = build_large_pdf(root / "large.pdf", pages=args.pages)
        started = time.perf_counter()
        result = convert_book(
            pdf,
            root / "out",
            profile="fast",
            page_images="never",
        )
        elapsed = time.perf_counter() - started
        audit = audit_output(root / "out")
        report = {
            "pages": args.pages,
            "seconds": round(elapsed, 3),
            "pages_per_second": round(args.pages / max(elapsed, 0.001), 2),
            "max_rss": (
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                if resource is not None else None
            ),
            "units": result["units"],
            "missing_refs": len(audit["missing_refs"]),
        }
        print(json.dumps(report, indent=2))
        return 0 if not audit["missing_refs"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
