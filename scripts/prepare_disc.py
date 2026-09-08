#!/usr/bin/env python3
"""Expand a locally supplied GameCube CISO and verify Melee USA revision 2."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import uuid

DISC_SIZE = 1459978240
HEADER_SIZE = 0x8000


def prepare(source, target):
    if source.resolve() == target.resolve():
        raise ValueError('Input and output must differ')
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.partial')
    if target.exists():
        raise ValueError(f'Output already exists: {target}')
    try:
        with source.open('rb') as src, temporary.open('xb') as dst:
            magic = src.read(4)
            src.seek(0)
            if magic == b'CISO':
                header = src.read(HEADER_SIZE)
                if len(header) != HEADER_SIZE:
                    raise ValueError('Truncated CISO header')
                block_size = struct.unpack_from('<I', header, 4)[0]
                block_map = header[8:]
                if block_size < 0x800 or block_size > 32 * 1024 * 1024 or block_size & (block_size-1):
                    raise ValueError('Invalid CISO block size')
                if set(block_map) - {0, 1}:
                    raise ValueError('Invalid CISO block map')
                payload_end = HEADER_SIZE + sum(block_map) * block_size
                if source.stat().st_size < payload_end:
                    raise ValueError('Truncated CISO payload')
                if source.stat().st_size > payload_end:
                    src.seek(payload_end)
                    if src.read(8) != b'NKIT  v2':
                        raise ValueError('Unrecognized CISO trailer')
                    src.seek(HEADER_SIZE)
                count = (DISC_SIZE + block_size - 1) // block_size
                if count > len(block_map) or any(block_map[count:]):
                    raise ValueError('Image is larger than a GameCube disc')
                for i in range(count):
                    size = min(block_size, DISC_SIZE - i * block_size)
                    if block_map[i]:
                        data = src.read(block_size)
                        if len(data) != block_size:
                            raise ValueError('Truncated CISO data')
                        dst.write(data[:size])
                    else:
                        dst.seek(size, os.SEEK_CUR)
                dst.truncate(DISC_SIZE)
            else:
                if source.stat().st_size != DISC_SIZE:
                    raise ValueError('Expected a full GameCube ISO/GCM or CISO')
                while data := src.read(8 * 1024 * 1024):
                    dst.write(data)
        with temporary.open('rb') as f:
            header = f.read(0x440)
            if header[:8] != b'GALE01\x00\x02':
                raise ValueError(f'Expected Melee USA revision 2, got {header[:8]!r}')
            if struct.unpack_from('>I', header, 0x1c)[0] != 0xc2339f3d:
                raise ValueError('Invalid GameCube disc magic')
            f.seek(0)
            digest = hashlib.file_digest(f, 'sha256').hexdigest()
        temporary.rename(target)
        manifest = {'source': str(source.resolve()), 'disc_id': 'GALE01', 'revision': 2,
                    'bytes': DISC_SIZE, 'sha256': digest,
                    'note': 'Expanded scrubbed CISO; hash is not a pristine retail ISO hash.'}
        target.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps(manifest, indent=2))
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('target', type=Path)
    args = parser.parse_args()
    prepare(args.source, args.target)
