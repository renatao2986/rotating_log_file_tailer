# Rotating Log File Tailer

Reads the last N lines from a file that may be concurrently written to or rotated, reopening by path when truncation or rename is detected.

```python
from rotating_log_file_tailer import RotatingLogTailer, TailError

tailer = RotatingLogTailer("/var/log/app.log", max_lines=100)
try:
    lines = tailer.tail()
except TailError as exc:
    # I/O failure other than the file simply being absent
    raise
print(lines)  # list[bytes], trailing newlines stripped
```

## Why

Log integrations rotate files. A naive tailer that caches a file descriptor misses rotations; one that caches a byte offset misses truncations. This tailer opens the file by path on every call and checks the inode and size against the values seen last time. If either has changed in a way that makes the old offset meaningless, it reads from the head of the new file instead of seeking backward from a stale size. The trade-off: each call does a stat plus an open, so this is intended for periodic polling rather than tight streaming loops.

## Whitespace policy

One choice, stated plainly: every returned line has its trailing newline stripped, and trailing per-line whitespace is also stripped. Lines are returned as `bytes` because log encodings are not assumed. If you need the raw bytes including whitespace, this is the wrong library.

## Awkward edge

If a log is truncated to a non-zero size smaller than what was previously seen, the tailer treats it as a full reset and returns content from the start of the (now shorter) file. It does not try to resume from the new size as a live offset; partial truncation is rare enough in real log tooling that the simplicity of always-from-head on shrinkage is worth more than guessing at a salvageable continuation point.
