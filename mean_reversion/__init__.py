from __future__ import annotations

from pathlib import Path


# When running from a repo root, resolve the package from that checkout's
# src/ tree before any editable install points at a different checkout.
_SRC_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "src" / "mean_reversion"
__path__ = [str(_SRC_PACKAGE_DIR)]
__file__ = str(_SRC_PACKAGE_DIR / "__init__.py")

exec(__file__ and Path(__file__).read_text(), globals())
