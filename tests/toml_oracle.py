"""Independent Python 3.11+ TOML syntax oracle for cross-version tests."""
import json
from pathlib import Path
import sys
import tomllib
print(json.dumps(tomllib.loads(Path(sys.argv[1]).read_text()),default=str))
