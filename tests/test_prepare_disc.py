import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('prepare_disc', Path(__file__).resolve().parents[1] / 'scripts/prepare_disc.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DiscPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_size = module.DISC_SIZE
        module.DISC_SIZE = 0x1800
        self.header = bytearray(0x800)
        self.header[:8] = b'GALE01\x00\x02'
        struct.pack_into('>I', self.header, 0x1c, 0xc2339f3d)

    def tearDown(self):
        module.DISC_SIZE = self.old_size
        self.temp.cleanup()

    def ciso(self, trailer=b''):
        h = bytearray(module.HEADER_SIZE)
        h[:4] = b'CISO'
        struct.pack_into('<I', h, 4, 0x800)
        h[8:11] = b'\x01\x00\x01'
        p = self.root / 'input.ciso'
        p.write_bytes(h + self.header + bytes([42]) * 0x800 + trailer)
        return p

    def test_sparse_mapping_and_nkit_trailer(self):
        p = self.ciso(b'NKIT  v2' + bytes(568))
        out = self.root / 'out.iso'
        module.prepare(p, out)
        self.assertEqual(out.read_bytes(), self.header + bytes(0x800) + bytes([42]) * 0x800)

    def test_truncated_payload_rejected(self):
        p = self.ciso()
        p.write_bytes(p.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            module.prepare(p, self.root / 'out.iso')
        self.assertFalse((self.root / 'out.iso').exists())

    def test_wrong_revision_rejected(self):
        self.header[7] = 0
        p = self.ciso()
        with self.assertRaisesRegex(ValueError, 'revision 2'):
            module.prepare(p, self.root / 'out.iso')

    def test_existing_output_preserved(self):
        p = self.ciso()
        out = self.root / 'out.iso'
        out.write_bytes(b'preserve')
        with self.assertRaises(ValueError):
            module.prepare(p, out)
        self.assertEqual(out.read_bytes(), b'preserve')

    def test_unknown_trailer_rejected(self):
        with self.assertRaisesRegex(ValueError, 'trailer'):
            module.prepare(self.ciso(b'unknown!'), self.root / 'out.iso')

if __name__ == '__main__':
    unittest.main()
