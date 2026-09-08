#!/usr/bin/env python3
"""Compare every CPUState field's size and offset across the two pinned APIs."""
from pathlib import Path
import re
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
runtime = root/'upstream/ModernGekko-Template/lib/ModernGekko'
headers = [runtime/'include/moderngekko/cpu_state.h', runtime/'vendor/dolphin/GXRuntime/include/core/cpu.h']
results = []
for header in headers:
    body = re.search(r'struct CPUState\s*\{(.*?)\};', header.read_text(), re.S).group(1)
    fields = re.findall(r'\b(\w+)\s*(?:\[\d+\])?;', body)
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp)/'check.c'
        binary = Path(temp)/'check'
        code = ['#include <stddef.h>', '#include <stdio.h>', f'#include "{header}"', 'int main(void) {',
                'printf("ABI %u size %zu\\n", GXRUNTIME_CPU_ABI_VERSION, sizeof(CPUState));']
        for field in fields:
            code.append(f'printf("{field} %zu %zu\\n", offsetof(CPUState,{field}), sizeof(((CPUState*)0)->{field}));')
        source.write_text('\n'.join(code+['return 0; }']))
        subprocess.run(['clang',str(source),'-I'+str(runtime/'vendor/dolphin/GXRuntime/include'),'-o',str(binary)],check=True)
        results.append(subprocess.check_output([str(binary)],text=True))
if results[0] != results[1]:
    raise SystemExit('CPU state ABI mismatch:\n'+'\n'.join(results))
print('CPU state ABI layouts match:',results[0].splitlines()[0],f'({len(results[0].splitlines())-1} fields)')
