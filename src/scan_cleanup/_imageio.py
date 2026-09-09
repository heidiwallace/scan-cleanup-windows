"""Unicode-safe image file reading and writing.

OpenCV's ``cv2.imread`` / ``cv2.imwrite`` hand the filename to the C runtime's
``fopen``, which cannot open paths containing non-ASCII characters on Windows:
``imread`` returns ``None`` and ``imwrite`` returns ``False``, both silently.
The Windows temp directory embeds the account name
(``C:\\Users\\<name>\\AppData\\Local\\Temp\\...``) and source PDFs may have
accented file names, so this is a real failure mode.

Routing the bytes through NumPy's ``fromfile`` / ``tofile`` avoids it: those use
Python's own file handling, which is Unicode-aware on every platform. The image
encode/decode still happens in OpenCV.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def imread_unicode(path: Path, flags: int = cv2.IMREAD_COLOR) -> np.ndarray | None:
    """Read an image file, tolerating non-ASCII characters in ``path``.

    Mirrors ``cv2.imread``'s contract: returns ``None`` on any failure (missing
    or empty file, unreadable bytes, undecodable image).
    """
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)


def imwrite_unicode(path: Path, image: np.ndarray) -> bool:
    """Write ``image`` to ``path``, tolerating non-ASCII characters in ``path``.

    The file extension selects the encoder, as with ``cv2.imwrite``. Returns
    ``True`` on success, ``False`` on encode or write failure.
    """
    success, buffer = cv2.imencode(path.suffix, image)
    if not success:
        return False
    try:
        buffer.tofile(str(path))
    except OSError:
        return False
    return True
