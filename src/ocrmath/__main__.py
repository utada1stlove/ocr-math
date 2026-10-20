"""让 `python -m ocrmath` 直接等于 `ocrmath`。"""

from .cli import main

raise SystemExit(main())
