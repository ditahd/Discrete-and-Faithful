"""Call the original per-certificate branch verifier, preserving its assertions."""
import hashlib,json,sys
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise RuntimeError('Assertions must remain enabled')
source=Path(sys.argv[1]).resolve();certificate=Path(sys.argv[2]).resolve();content=source.read_bytes();digest=hashlib.sha256(content).hexdigest()
scope={'__file__':str(source),'__name__':'_release_native_branch'}
exec(compile(content,str(source),'exec',dont_inherit=True,optimize=0),scope)
report=scope['verify'](str(certificate))
assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
print(json.dumps({'status':'ORIGINAL_BRANCH_CERTIFICATE_REPLAYED','native_source_sha256':digest,'native_source_unchanged':True,'result':report}),flush=True)
