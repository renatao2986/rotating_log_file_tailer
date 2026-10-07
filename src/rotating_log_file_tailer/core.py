import os
import errno


class TailError(Exception):
    """Raised for I/O or constraint failures that prevent producing a tail."""


class RotatingLogTailer:
    """Read the last N lines from a file that may be concurrently written or rotated.

    The tailer never holds the file open between calls. Each ``tail`` call opens the
    file by path, reads from the end, and closes it. If between two successive
    ``tail`` calls the file was rotated (current inode changed) or truncated
    (current size shrank below the size last seen), the tailer detects this from
    fresh ``os.stat`` data and reopens from the head instead of seeking backward
    from an incorrect offset.

    Whitespace policy (deliberately chosen, see README): every line's trailing
    newline is stripped, and trailing per-line whitespace is also stripped. Lines
    are returned as ``bytes`` because log encodings are not assumed.
    """

    def __init__(self, path, max_lines=1000, chunk_size=4096):
        if not isinstance(path, (str, bytes, os.PathLike)):
            raise TypeError("path must be str, bytes, or os.PathLike")
        if not isinstance(max_lines, int) or isinstance(max_lines, bool):
            raise TypeError("max_lines must be an int")
        if max_lines <= 0:
            raise ValueError("max_lines must be positive")
        if not isinstance(chunk_size, int) or isinstance(chunk_size, bool):
            raise TypeError("chunk_size must be an int")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")

        self._path = os.fspath(path)
        self._max_lines = max_lines
        self._chunk_size = chunk_size
        self._last_inode = None
        self._last_size = None

    def tail(self):
        """Return a list of up to ``max_lines`` trailing lines from the file.

        On rotation or truncation the returned lines cover from the start of the
        new file. On ENOENT the result is an empty list. Other I/O errors raise
        ``TailError``.
        """
        try:
            st = os.stat(self._path)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                self._last_inode = None
                self._last_size = None
                return []
            raise TailError("stat failed for %r: %s" % (self._path, exc)) from exc

        rotated = (
            self._last_inode is not None
            and (st.st_ino != self._last_inode or st.st_dev != self._last_dev)
        )
        truncated = self._last_size is not None and st.st_size < self._last_size

        self._last_inode = st.st_ino
        self._last_dev = st.st_dev
        self._last_size = st.st_size

        if st.st_size == 0:
            return []

        try:
            with open(self._path, "rb") as f:
                if rotated or truncated:
                    return self._tail_from_head(f)
                return self._tail_from_end(f, st.st_size)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                self._last_inode = None
                self._last_size = None
                return []
            raise TailError("read failed for %r: %s" % (self._path, exc)) from exc

    def _tail_from_end(self, f, file_size):
        tail = b""
        pos = file_size
        while pos > 0:
            read_size = min(self._chunk_size, pos)
            pos -= read_size
            f.seek(pos)
            tail = f.read(read_size) + tail
            if tail.count(b"\n") > self._max_lines:
                break
        return self._split(tail)

    def _tail_from_head(self, f):
        data = f.read()
        return self._split(data)

    def _split(self, data):
        lines = data.split(b"\n")
        if lines and lines[-1] == b"":
            lines.pop()
        lines = [ln.rstrip() for ln in lines]
        if len(lines) > self._max_lines:
            lines = lines[-self._max_lines:]
        return lines
