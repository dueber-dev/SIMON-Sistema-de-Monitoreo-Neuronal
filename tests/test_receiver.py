import csv
from pathlib import Path
import tempfile
import unittest
from codigo_esp32_prueba2 import MAX_LINE_BYTES, parse_record, read_lines, record_connection

class FakeSocket:
    def __init__(self, chunks): self.chunks = iter(chunks)
    def recv(self, _size): return next(self.chunks, b'')

class ReceiverTests(unittest.TestCase):
    def test_valid_record_preserves_precision_and_sign(self):
        self.assertEqual(parse_record('1,2.550,-0.20,0.00,25.0,50.0'),
                         ['1', '2.550', '-0.20', '0.00', '25.0', '50.0'])

    def test_invalid_numeric_data(self):
        for line in ['bad,2,3,4,5,6', '1,2,nan,4,5,6', '1,2,3,inf,5,6',
                     '1,2,3,4,5', '1,2,3,4,5,101', '-1,2,3,4,5,6']:
            with self.subTest(line=line), self.assertRaises(ValueError): parse_record(line)

    def test_fragmented_and_combined_lines(self):
        sock = FakeSocket([b'1,2,', b'3,4,5,6\r\n2,3,4,5,6,7\npartial'])
        self.assertEqual(list(read_lines(sock)), ['1,2,3,4,5,6', '2,3,4,5,6,7'])

    def test_bounded_incomplete_and_complete_line(self):
        for suffix in [b'', b'\n']:
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                list(read_lines(FakeSocket([b'0' * (MAX_LINE_BYTES + 1) + suffix])))

    def test_restart_starts_new_csv_and_reconnect_preserves_session(self):
        with tempfile.TemporaryDirectory() as directory:
            state = {'file': None, 'writer': None, 'last_seconds': -1}
            try:
                record_connection(FakeSocket([b'10,2,3,4,5,6\n']), state, directory)
                record_connection(FakeSocket([b'11,2,3,4,5,6\n']), state, directory)
                record_connection(FakeSocket([b'0,2,3,4,5,6\n']), state, directory)
            finally:
                if state['file']: state['file'].close()
            files = sorted(Path(directory).glob('*.csv'))
            self.assertEqual(len(files), 2)
            with files[0].open(encoding='utf-8', newline='') as file:
                self.assertEqual(len(list(csv.reader(file))), 3)
            with files[1].open(encoding='utf-8', newline='') as file:
                self.assertEqual(list(csv.reader(file))[1][0], '0')

    def test_invalid_record_never_creates_file(self):
        with tempfile.TemporaryDirectory() as directory:
            state = {'file': None, 'writer': None, 'last_seconds': -1}
            record_connection(FakeSocket([b'nan,2,3,4,5,6\n']), state, directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

if __name__ == '__main__': unittest.main()
