#!/usr/bin/env python3
"""Reproduce byte-identical tar assets from extracted payload and public manifests."""
import argparse,gzip,hashlib,json,os,tarfile
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fetch_assets import records,safe,need
class Reader:
 def __init__(self,f):self.f=f;self.hash=hashlib.sha256()
 def read(self,n=-1):
  b=self.f.read(n);self.hash.update(b);return b
class Writer:
 def __init__(self,f):self.f=f;self.hash=hashlib.sha256()
 def write(self,b):self.hash.update(b);return self.f.write(b)
 def tell(self):return self.f.tell()
 def flush(self):self.f.flush()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--data-root',type=Path,default=Path('.'));ap.add_argument('--output',type=Path,required=True);ap.add_argument('--group',action='append');ap.add_argument('--asset',action='append',help='Select individual asset names for bounded repacking');a=ap.parse_args()
 repo=Path(__file__).resolve().parents[1];release=json.loads((repo/'manifests/release-v1.json').read_bytes());a.output.mkdir(parents=True,exist_ok=True)
 chosen=[v for v in release['assets']if(not a.group or v['group']in a.group)and(not a.asset or v['name']in a.asset)];need(chosen,'No matching asset group')
 for asset in chosen:
  path=a.output/asset['name']
  with path.open('xb')as raw:
   writer=Writer(raw)
   compressed=gzip.GzipFile(filename='',mode='wb',fileobj=writer,compresslevel=1,mtime=0) if asset.get('compression',{}).get('format')=='gzip' else None
   with tarfile.open(fileobj=compressed or writer,mode='w|',format=tarfile.PAX_FORMAT)as tf:
    for row in records(repo,asset):
     p=safe(a.data_root.resolve(),row['path']);need(p.is_file()and not p.is_symlink()and p.stat().st_size==row['bytes'],'missing or changed payload file')
     info=tarfile.TarInfo(row['path']);info.size=row['bytes'];info.mode=0o644;info.mtime=0
     with p.open('rb')as f:
      reader=Reader(f);tf.addfile(info,reader);need(reader.hash.hexdigest()==row['sha256'],'payload hash mismatch')
     tf.members.clear()
   if compressed:compressed.close()
   writer.flush();os.fsync(raw.fileno())
  need(path.stat().st_size==asset['bytes']and writer.hash.hexdigest()==asset['sha256'],'repacked asset is not byte-identical')
  print(json.dumps({'name':path.name,'status':'BYTE_IDENTICAL','bytes':asset['bytes'],'sha256':asset['sha256']}),flush=True)
if __name__=='__main__':main()
