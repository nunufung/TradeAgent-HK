"""Extract locally with pinned book-to-skill; synthesis is a separate review."""
from pathlib import Path
import subprocess
import sys


def main() -> int:
    script = Path(__file__).resolve().parents[1] / 'tools/book-to-skill/scripts/extract.py'
    if not script.is_file():
        print('Initialize the converter: git submodule update --init tools/book-to-skill', file=sys.stderr)
        return 1
    return subprocess.run([sys.executable, str(script), *sys.argv[1:],
                           '--install-missing', 'no'], check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
