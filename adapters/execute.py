"""Isolated native helper launcher; source bytes are compiled with optimize=0."""
import os,sys
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise RuntimeError('Assertions must remain enabled')
source=Path(sys.argv[1]).resolve();mode=sys.argv[2];arguments=sys.argv[3:]
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path.cwd()));sys.argv=[str(source)]+arguments
if mode=='script':
 # Use the real main-module namespace. Native multiprocessing must be able
 # to pickle its task functions and re-import the original script on spawn.
 __file__=str(source)
 exec(compile(source.read_bytes(),str(source),'exec',dont_inherit=True,optimize=0),globals())
else:
 scope={'__file__':str(source),'__name__':'_release_native_helper'}
 exec(compile(source.read_bytes(),str(source),'exec',dont_inherit=True,optimize=0),scope)
 if mode=='replay':
  scope['ROOT']=Path.cwd();scope['main'](arguments[0])
 elif mode=='basic':scope['main'](Path(arguments[0]),Path(arguments[1]))
 else:raise ValueError(mode)
