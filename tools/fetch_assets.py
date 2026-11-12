#!/usr/bin/env python3
"""Download, verify and safely extract the release's independent tar assets."""
import http.client
import argparse,gzip,hashlib,json,os,shutil,tarfile,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path,PurePosixPath

def read(p):return json.loads(p.read_bytes())
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def need(ok,message):
 if not ok:raise ValueError(message)
def records(repo,asset):
 p=repo/asset['manifest'];need(sha(p)==asset['manifest_sha256'],'file manifest SHA-256 mismatch')
 with gzip.open(p,'rt',encoding='utf-8')as f:
  for line in f:yield json.loads(line)
def safe(root,name):
 p=PurePosixPath(name);need(not p.is_absolute()and '..'not in p.parts and p.parts and p.parts[0]=='payload','unsafe member path')
 dest=root/str(p);need(dest.resolve().is_relative_to(root.resolve()),'extraction escapes destination');return dest

def archive(repo,path,asset,destination=None,predicate=None):
 need(path.stat().st_size==asset['bytes'] and path.stat().st_size<2**31,'asset size mismatch or limit exceeded')
 need(sha(path)==asset['sha256'],'asset SHA-256 mismatch: '+path.name)
 expected=iter(records(repo,asset));count=0;total=0;extracted_files=0;extracted_bytes=0
 with tarfile.open(path,'r|*')as tf:
  for member in tf:
   tf.members.clear()
   row=next(expected,None);need(row is not None and member.name==row['path']and member.size==row['bytes']and member.isfile(),'member manifest/type mismatch')
   stream=tf.extractfile(member);h=hashlib.sha256();out=None
   if destination is not None and(predicate is None or predicate(member.name)):
    dest=safe(destination,member.name);dest.parent.mkdir(parents=True,exist_ok=True);need(not dest.exists(),'refuse overwrite: '+str(dest));out=dest.open('xb')
    extracted_files+=1;extracted_bytes+=member.size
   try:
    while True:
     b=stream.read(1024*1024)
     if not b:break
     h.update(b)
     if out:out.write(b)
   finally:
    if out:out.close()
   need(h.hexdigest()==row['sha256'],'payload SHA-256 mismatch: '+member.name);count+=1;total+=member.size
 need(next(expected,None)is None and count==asset['files']and total==asset['payload_bytes'],'complete member census mismatch')
 return {'asset':path.name,'files':count,'payload_bytes':total,'sha256':asset['sha256'],'regular_files_only':True,'extracted_files':extracted_files,'extracted_payload_bytes':extracted_bytes}

def verify_payload(repo,root):
 release=read(repo/'manifests/release-v1.json');count=0;total=0
 for asset in release['assets']:
  for row in records(repo,asset):
   p=safe(root,row['path']);need(p.is_file()and not p.is_symlink()and p.stat().st_size==row['bytes']and sha(p)==row['sha256'],'payload integrity failure: '+row['path']);count+=1;total+=row['bytes']
 need(count==release['files']and total==release['payload_bytes'],'payload census mismatch')
 return {'status':'ALL_PAYLOAD_BYTES_VERIFIED','files':count,'bytes':total}

def download(url, destination, item, attempts=5, opener=urllib.request.urlopen, retry_delay=1):
 """Resume interrupted bytes, but promote only a complete hash-verified asset."""
 destination=Path(destination);part=destination.with_suffix(destination.suffix+'.part')
 last_error=None
 for attempt in range(attempts):
  try:
   if part.is_symlink():part.unlink()
   if part.exists():
    need(part.is_file(),'Partial download is not a regular file')
    length=part.stat().st_size
    if length==item['bytes'] and sha(part)==item['sha256']:
     os.replace(part,destination);return
    if length>=item['bytes']:part.unlink()
   offset=part.stat().st_size if part.exists() else 0
   request=urllib.request.Request(url,headers=dict({'Accept-Encoding':'identity'},**({'Range':f'bytes={offset}-'}if offset else{})))
   with opener(request,timeout=30)as response:
    status=response.status if hasattr(response,'status')else response.getcode()
    if offset and status==206:
     content_range=response.headers.get('Content-Range','')
     if not(content_range.startswith(f'bytes {offset}-')and content_range.endswith('/'+str(item['bytes']))):
      part.unlink();raise ValueError('Invalid HTTP resume range')
     mode='ab'
    else:
     need(status==200,'Unexpected HTTP download status')
     mode='wb';offset=0
    with part.open(mode)as out:
     total=offset
     while True:
      block=response.read(1024*1024)
      if not block:break
      total+=len(block);need(total<=item['bytes'],'Download exceeds declared size');out.write(block)
     out.flush();os.fsync(out.fileno())
   need(part.stat().st_size==item['bytes'],'Incomplete download')
   if sha(part)!=item['sha256']:
    part.unlink();raise ValueError('Download SHA-256 mismatch')
   os.replace(part,destination);return
  except (OSError,ValueError,http.client.HTTPException,urllib.error.URLError)as error:
   last_error=error
   if isinstance(error,urllib.error.HTTPError)and error.code==416 and part.exists():part.unlink()
   if attempt+1<attempts and retry_delay:time.sleep(min(retry_delay*(attempt+1),3))
 raise ValueError(f'Download failed after {attempts} attempts: {last_error}')

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--base-url',help='Release download base URL, for example https://github.com/OWNER/REPO/releases/download/TAG')
 ap.add_argument('--assets-dir',type=Path,default=Path('assets'));ap.add_argument('--destination',type=Path,default=Path('.'));ap.add_argument('--verify-only',action='store_true');ap.add_argument('--group',action='append',help='Optional asset group subset; omit for complete release')
 a=ap.parse_args();repo=Path(__file__).resolve().parents[1];release=read(repo/'manifests/release-v1.json');a.assets_dir.mkdir(parents=True,exist_ok=True)
 selected=[r for r in release['assets']if not a.group or r['group']in a.group];need(selected,'No matching assets')
 for item in selected:
  p=a.assets_dir/item['name']
  if not p.exists():
   need(a.base_url,'Missing asset; supply --base-url or place local assets in --assets-dir');url=a.base_url.rstrip('/')+'/'+urllib.parse.quote(item['name'])
   need(urllib.parse.urlparse(url).scheme=='https','Downloads require HTTPS');download(url,p,item)
  row=archive(repo,p,item,None if a.verify_only else a.destination.resolve());print(json.dumps(row),flush=True)
if __name__=='__main__':main()
