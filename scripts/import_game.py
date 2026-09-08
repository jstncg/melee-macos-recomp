#!/usr/bin/env python3
"""Import a supported local disc into an isolated cache; never replace active data."""
import hashlib
import subprocess
import sys
import uuid
from pathlib import Path
from prepare_disc import prepare

ROOT = Path(__file__).resolve().parent.parent
DOL_SHA1 = '08e0bf20134dfcb260699671004527b2d6bb1a45'


def import_game(source):
    destination = ROOT / 'private' / 'imports' / uuid.uuid4().hex
    destination.mkdir(parents=True)
    iso = destination / 'disc.iso'
    prepare(source, iso)
    game = destination / 'game'
    subprocess.run([str(ROOT / 'build/dolrecomp/dolrecomp'), 'extract', str(iso), str(game)], check=True)
    if hashlib.sha1((game / 'sys/main.dol').read_bytes()).hexdigest() != DOL_SHA1:
        raise ValueError('Executable does not match Melee USA revision 2')
    iso.unlink()  # Extracted data is sufficient; preserve the original source image.
    return game


if __name__ == '__main__':
    try:
        print('IMPORTED_GAME=' + str(import_game(Path(sys.argv[1]))), flush=True)
    except Exception as error:
        print(f'Import failed: {error}', file=sys.stderr)
        sys.exit(1)
