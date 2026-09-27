"""Remove machine-specific build paths from the frozen Python metadata module.

The app never compiles extensions at runtime; interpreter build metadata is only
needed for stdlib/package introspection. Keep its compiler/ABI/platform values.
"""
import importlib
from pathlib import Path
import pprint
import sys
import sysconfig

name=sysconfig._get_sysconfigdata_name()
original=importlib.import_module(name).build_time_vars
prefixes=sorted({str(Path.home()),sys.prefix,sys.base_prefix},key=len,reverse=True)
def clean(value):
    if isinstance(value,str):
        for prefix in prefixes:
            value=value.replace(prefix,'/opt/remote-eye-python')
    return value
out=Path(__file__).resolve().parents[1]/'build/sanitized'
out.mkdir(parents=True,exist_ok=True)
(out/(name+'.py')).write_text('build_time_vars = '+pprint.pformat({k:clean(v) for k,v in original.items()})+'\n')
