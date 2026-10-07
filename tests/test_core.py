import os
import errno
import unittest

from rotating_log_file_tailer import RotatingLogTailer, TailError


class RotatingLogTailerTests(unittest.TestCase):

    def setUp(self):
        self.path = os.path.join(os.path.dirname(__file__), "_tail_target.log")
        if os.path.exists(self.path):
            os.remove(self.path)

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def _write(self, text):
        with open(self.path, "ab") as f:
            f.write(text)

    def test_missing_file_returns_empty(self):
        t = RotatingLogTailer(self.path)
        self.assertEqual(t.tail(), [])

    def test_basic_tail(self):
        self._write(b"first\nsecond\nthird\n")
        t = RotatingLogTailer(self.path, max_lines=10)
        self.assertEqual(t.tail(), [b"first", b"second", b"third"])

    def test_max_lines_cap(self):
        self._write(b"a\nb\nc\nd\n")
        t = RotatingLogTailer(self.path, max_lines=2)
        self.assertEqual(t.tail(), [b"c", b"d"])

    def test_no_trailing_newline(self):
        self._write(b"one\ntwo")
        t = RotatingLogTailer(self.path, max_lines=10)
        self.assertEqual(t.tail(), [b"one", b"two"])

    def test_empty_file_returns_empty(self):
        self._write(b"")
        t = RotatingLogTailer(self.path)
        self.assertEqual(t.tail(), [])

    def test_returns_bytes(self):
        self._write(b"hello\n")
        t = RotatingLogTailer(self.path)
        result = t.tail()
        self.assertEqual(result, [b"hello"])
        self.assertIsInstance(result[0], bytes)

    def test_append_then_tail(self):
        self._write(b"one\n")
        t = RotatingLogTailer(self.path, max_lines=10)
        t.tail()
        self._write(b"two\nthree\n")
        self.assertEqual(t.tail(), [b"one", b"two", b"three"])

    def test_trailing_whitespace_stripped(self):
        self._write(b"line   \n  spaced\t\n")
        t = RotatingLogTailer(self.path, max_lines=10)
        self.assertEqual(t.tail(), [b"line", b"  spaced"])

    def test_max_lines_zero_raises(self):
        with self.assertRaises(ValueError):
            RotatingLogTailer(self.path, max_lines=0)

    def test_negative_max_lines_raises(self):
        with self.assertRaises(ValueError):
            RotatingLogTailer(self.path, max_lines=-5)

    def test_bad_path_type_raises(self):
        with self.assertRaises(TypeError):
            RotatingLogTailer(123)

    def test_rotation_detected_after_rename(self):
        self._write(b"old\n")
        t = RotatingLogTailer(self.path, max_lines=10)
        self.assertEqual(t.tail(), [b"old"])
        os.rename(self.path, self.path + ".1")
        with open(self.path, "wb") as f:
            f.write(b"fresh\n")
        self.assertEqual(t.tail(), [b"fresh"])

    def test_truncation_detected(self):
        self._write(b"first\nsecond\nthird\n")
        t = RotatingLogTailer(self.path, max_lines=10)
        self.assertEqual(t.tail(), [b"first", b"second", b"third"])
        with open(self.path, "wb") as f:
            f.write(b"only\n")
        self.assertEqual(t.tail(), [b"only"])

    def test_rotation_then_truncation_both_paths(self):
        # First call populates inode/size, no rotation yet.
        self._write(b"v1\n")
        t = RotatingLogTailer(self.path, max_lines=10)
        self.assertEqual(t.tail(), [b"v1"])
        # Truncate to smaller content (same inode, smaller size).
        with open(self.path, "wb") as f:
            f.write(b"v2\n")
        self.assertEqual(t.tail(), [b"v2"])
        # Rotate: new file, new inode.
        os.rename(self.path, self.path + ".bak")
        with open(self.path, "wb") as f:
            f.write(b"v3\nnew\n")
        self.assertEqual(t.tail(), [b"v3", b"new"])

    def test_nonexistent_then_appears(self):
        t = RotatingLogTailer(self.path, max_lines=10)
        self.assertEqual(t.tail(), [])
        self._write(b"appeared\n")
        self.assertEqual(t.tail(), [b"appeared"])

    def test_directory_raises_tail_error(self):
        dir_path = os.path.join(os.path.dirname(__file__), "_tail_dir_fixture")
        os.makedirs(dir_path, exist_ok=True)
        try:
            t = RotatingLogTailer(dir_path)
            with self.assertRaises(TailError):
                t.tail()
        finally:
            os.rmdir(dir_path)

    def test_large_file_streaming(self):
        chunk = b"0123456789\n"
        n = 500
        with open(self.path, "wb") as f:
            for _ in range(n):
                f.write(chunk)
        t = RotatingLogTailer(self.path, max_lines=3, chunk_size=128)
        result = t.tail()
        self.assertEqual(result, [b"0123456789"] * 3)
        self.assertEqual(len(result), 3)

    def test_more_lines_than_max(self):
        self._write(b"a\nb\nc\nd\ne\nf\n")
        t = RotatingLogTailer(self.path, max_lines=3)
        self.assertEqual(t.tail(), [b"d", b"e", b"f"])

    def test_max_lines_one(self):
        self._write(b"only\n")
        t = RotatingLogTailer(self.path, max_lines=1)
        self.assertEqual(t.tail(), [b"only"])

    def test_repeated_tail_idempotent(self):
        self._write(b"stable\ncontent\n")
        t = RotatingLogTailer(self.path, max_lines=10)
        first = t.tail()
        second = t.tail()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
