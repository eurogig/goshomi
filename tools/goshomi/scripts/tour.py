#!/usr/bin/env python3
"""Index, prepare, package and verify a repository-local Goshomi tour."""
import argparse, datetime, hashlib, json, os, re, stat, subprocess, sys
from pathlib import Path

EXCLUDED = {'.git', '.env', '.goshomi', '.tourrific', 'node_modules', 'dist', 'build', '.next', 'coverage', 'vendor', 'tours', '__pycache__'}
SECRET = re.compile(r'(?i)(?:-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|(?:api[_-]?key|secret|password|token)\s*[:=]\s*["\'][^"\'\s]{8,}["\']|(?:sk|ghp|github_pat)-[A-Za-z0-9_-]{16,})')
EXTENSIONS = {'.ts','.tsx','.js','.jsx','.mjs','.json','.py','.go','.rs','.java','.md','.yaml','.yml','.css','.html','.toml','.sh'}
ASSET_ROOT = Path(__file__).resolve().parent.parent
MARKER = '.goshomi-owner.json'
REVIEW_POLICY = 'self-contained-remediation-2026-v3'
PREVIOUS_REVIEW_POLICY = 'security-path-review-2026-v2'
LEGACY_REVIEW_POLICY = 'owasp-genai-2026-v1'

def digest(data): return hashlib.sha256(data.encode('utf-8')).hexdigest()

def target_repo(explicit):
    root = Path(explicit).expanduser().resolve() if explicit else Path.cwd().resolve()
    if not root.is_dir(): raise ValueError('Repository must be an existing directory')
    if not explicit:
        p = subprocess.run(['git','-C',str(root),'rev-parse','--show-toplevel'],capture_output=True,text=True)
        if p.returncode == 0: root = Path(p.stdout.strip()).resolve()
    return root

def safe_file(root, name):
    p = Path(name)
    if p.is_absolute() or '..' in p.parts or any(part in EXCLUDED or part.startswith('.env') for part in p.parts):
        raise ValueError(f'Excluded or unsafe path: {name}')
    f = (root / p).resolve()
    if not f.is_relative_to(root) or not f.is_file() or f.suffix.lower() not in EXTENSIONS:
        raise ValueError(f'Not an allowed source file: {name}')
    if f.stat().st_size > 200_000: raise ValueError(f'File too large: {name}')
    return f

def read(root, name):
    data = safe_file(root, name).read_text(encoding='utf-8')
    if '\0' in data: raise ValueError(f'Binary file: {name}')
    if SECRET.search(data): raise ValueError(f'Possible secret in {name}; omit this file and investigate')
    return data

def revision(root):
    p = subprocess.run(['git','-C',str(root),'rev-parse','HEAD'], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None

def git_snapshot(root, output):
    """Hash Git state and working files; never emit their content or names."""
    git_dir=root
    def git(*args):
        return subprocess.run(['git', '--no-optional-locks', '-C', str(git_dir), *args], capture_output=True)
    top=git('rev-parse','--show-toplevel')
    if top.returncode: raise ValueError('Git snapshot unavailable: target is not a Git repository')
    git_root=Path(os.fsdecode(top.stdout.rstrip(b"\n"))).resolve()
    git_dir=git_root
    tracked=git('ls-files','--stage','-z')
    other=git('ls-files','--others','--exclude-standard','-z')
    if tracked.returncode or other.returncode: raise ValueError('Git snapshot unavailable: could not list repository files')
    entries={}
    for record in tracked.stdout.split(b'\0'):
        if not record: continue
        meta, name=record.split(b'\t',1)
        if meta.startswith(b'160000 '):
            raise ValueError('Git snapshot unavailable: repositories with submodules require fresh analysis')
        entries.setdefault(name,[]).append(meta)
    for name in other.stdout.split(b'\0'):
        if name: entries.setdefault(name,[])
    head=git('rev-parse','--verify','HEAD')
    if head.returncode:
        unborn=git('symbolic-ref','-q','HEAD')
        if unborn.returncode: raise ValueError('Git snapshot unavailable: could not identify HEAD')
        head_bytes=b'unborn:'+unborn.stdout
    else: head_bytes=head.stdout
    state=hashlib.sha256(b'goshomi-git-snapshot-v1\0'+head_bytes)
    for name, stages in sorted(entries.items()):
        relative=Path(os.fsdecode(name))
        if relative.is_absolute() or '..' in relative.parts: raise ValueError('Unsafe Git path')
        path=git_root/relative
        if path == output or output in path.parents: continue
        state.update(len(name).to_bytes(8,'big')); state.update(name)
        for stage in sorted(stages): state.update(b'index:'+stage+b'\0')
        parent=git_root
        blocked=False
        for part in relative.parts[:-1]:
            parent=parent/part
            if parent.is_symlink():
                state.update(b'parent-symlink:'+os.fsencode(os.readlink(parent))+b'\0'); blocked=True; break
        if blocked: continue
        try: info=path.lstat()
        except FileNotFoundError: state.update(b'missing\0'); continue
        state.update(str(stat.S_IFMT(info.st_mode)).encode()+b':'+str(info.st_mode & 0o111).encode()+b'\0')
        if stat.S_ISLNK(info.st_mode): state.update(os.fsencode(os.readlink(path)))
        elif stat.S_ISREG(info.st_mode):
            content=hashlib.sha256()
            with path.open('rb') as file:
                for chunk in iter(lambda:file.read(1024*1024),b''): content.update(chunk)
            state.update(content.digest())
        elif not stat.S_ISDIR(info.st_mode): raise ValueError('Git snapshot unavailable: unsupported file type')
        state.update(b'\0')
    # Also include ignored files eligible for semantic indexing; other ignored output is excluded.
    state.update(b'indexed-source-v1\0')
    for item in index(root,output):
        name=os.fsencode(item['path']); state.update(len(name).to_bytes(8,'big')); state.update(name); state.update(item['sha256'].encode())
    return state.hexdigest()

def index(root, output=None):
    files=[]
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not d.startswith('.env') and not (Path(base)/d).is_symlink() and (Path(base)/d).resolve() != output)
        for name in sorted(names):
            p=Path(base)/name
            if p.suffix.lower() not in EXTENSIONS or p.is_symlink(): continue
            rel=p.relative_to(root).as_posix()
            try:
                data=read(root,rel)
                files.append({'path':rel,'lines':len(data.splitlines()),'sha256':digest(data)})
            except (ValueError,UnicodeError,OSError): pass
    return files

def all_refs(obj):
    if isinstance(obj,dict):
        if set(('path','start','end')).issubset(obj): yield obj
        for value in obj.values(): yield from all_refs(value)
    elif isinstance(obj,list):
        for value in obj: yield from all_refs(value)

def output_path(root, option):
    raw = Path(option).expanduser() if option else root / '.goshomi'
    # Resolve parent separately so an output-directory symlink is never followed.
    if raw.is_symlink(): raise ValueError('Output directory cannot be a symlink')
    out=raw.resolve()
    if out == root or root.is_relative_to(out): raise ValueError('Output must not be the repository root or its ancestor')
    # Never write into this checkout while analyzing a different repository.
    checkout=ASSET_ROOT.parent.parent
    if (checkout / '.agents/skills/goshomi/SKILL.md').exists() and root != checkout and out.is_relative_to(checkout):
        raise ValueError('Output cannot be inside the Goshomi source checkout for a different target')
    return out

def owner_id(root): return digest(str(root))

def output_status(out):
    """Report Git exposure without creating or modifying the output directory."""
    ancestor = out
    while not ancestor.exists(): ancestor = ancestor.parent
    if not ancestor.is_dir(): ancestor = ancestor.parent
    def git(*args):
        return subprocess.run(['git', '-C', str(ancestor), *args], capture_output=True)
    top = git('rev-parse', '--show-toplevel')
    if top.returncode:
        inside = git('rev-parse', '--is-inside-work-tree')
        if inside.returncode == 128 and b'not a git repository' in inside.stderr.lower():
            return {'status': 'outside_git', 'output': str(out)}
        raise ValueError('Cannot determine whether output is inside a Git repository')
    git_root = Path(os.fsdecode(top.stdout.rstrip(b'\n'))).resolve()
    if not out.is_relative_to(git_root): return {'status': 'outside_git', 'output': str(out)}
    ancestor = git_root
    relative = out.relative_to(git_root).as_posix()
    tracked = git('ls-files', '-z', '--', ':(literal)' + relative)
    if tracked.returncode: raise ValueError('Cannot inspect tracked output files')
    tracked_files = [os.fsdecode(name) for name in tracked.stdout.split(b'\0') if name]
    # Check an arbitrary future file as well as existing files, since negated
    # patterns can leave individual files exposed inside an ignored directory.
    paths = [out / name for name in ('.goshomi-ignore-probe', MARKER, 'analysis.json',
             'index.html', 'tour.json', 'assets/viewer.js', 'assets/viewer.css',
             'sources/' + '0' * 64 + '.txt')]
    if out.is_dir():
        for base, dirs, names in os.walk(out, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(base) / d).is_symlink()]
            paths.extend(Path(base) / name for name in names)
    exposed = []
    for path in paths:
        result = git('check-ignore', '--no-index', '-q', '--', str(path))
        if result.returncode == 1: exposed.append(path.relative_to(git_root).as_posix())
        elif result.returncode != 0: raise ValueError('Cannot inspect Git ignore rules for output')
    status = 'tracked' if tracked_files else 'exposed' if exposed else 'ignored'
    return {'status': status, 'output': str(out), 'git_root': str(git_root),
            'tracked_files': tracked_files, 'exposed_paths': exposed}

def prepare(root,out):
    if out.exists() and not out.is_dir(): raise ValueError('Output must be a directory')
    marker=out/MARKER
    if marker.is_symlink(): raise ValueError('Owner marker cannot be a symlink')
    if marker.exists():
        owner=json.loads(marker.read_text())
        if owner.get('repositoryId') != owner_id(root): raise ValueError('Output belongs to a different repository')
        if not isinstance(owner.get('files'), list): raise ValueError('Invalid owner marker')
        return owner
    if out.exists() and any(out.iterdir()): raise ValueError('Output directory is not empty and has no Goshomi ownership marker')
    out.mkdir(parents=True,exist_ok=True)
    owner={'version':1,'repositoryId':owner_id(root),'files':[]}
    marker.write_text(json.dumps(owner,indent=2)+'\n')
    return owner

def safe_output(out,name):
    p=Path(name)
    if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] not in ('sources','assets') and name not in ('index.html','tour.json'):
        raise ValueError('Unsafe managed output path')
    path=out/p
    for part in [path,*path.parents]:
        if part == out: break
        if part.is_symlink(): raise ValueError(f'Symlink in output path: {name}')
    return path

def excerpts(root,tour):
    refs=list(all_refs({k:v for k,v in tour.items() if k!='sources'})); grouped={}
    for ref in refs:
        name=ref['path']; data=read(root,name); lines=data.splitlines(); start,end=ref['start'],ref['end']
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines): raise ValueError(f'Invalid range {name}:{start}-{end}')
        if ref.get('symbol') and ref['symbol'] not in '\n'.join(lines[start-1:end]): raise ValueError(f"Symbol {ref['symbol']} absent in {name}:{start}-{end}")
        if name not in grouped: grouped[name]=[lines,set()]
        grouped[name][1].update(range(start-1,end))
    sources={}
    for name,(lines,included) in grouped.items():
        # Blank unreferenced lines retain original line numbers without exposing their contents.
        content='\n'.join(line if i in included else '' for i,line in enumerate(lines[:max(included)+1]))
        sources[name]={'content':content,'sha256':digest(content)}
    return sources

def package(root,analysis,out,baseline=None,review_policy=None):
    if baseline is not None and (not re.fullmatch(r'[0-9a-f]{64}', baseline) or git_snapshot(root,out) != baseline):
        raise ValueError('Repository changed since analysis began; refresh the analysis before packaging')
    tour=json.loads(Path(analysis).read_text(encoding='utf-8'))
    tour['repository'].pop('gitFingerprint',None)
    # Only an explicit post-analysis attestation can mark the new review complete.
    tour['repository'].pop('threatReviewPolicy',None)
    if review_policy is not None: tour['repository']['threatReviewPolicy']=review_policy
    if baseline is not None: tour['repository']['gitFingerprint']=baseline
    tour['sources']=excerpts(root,tour)
    tour['repository']['revision']=revision(root)
    tour['repository']['generatedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    tour['repository']['snapshot']=digest(''.join(k+v['sha256'] for k,v in sorted(tour['sources'].items())))
    from validate import validate
    errors=validate(tour)
    if review_policy == REVIEW_POLICY:
        for chapter in tour.get('chapters', []):
            for step in chapter.get('steps', []):
                for field, prompt_key in (('finding', 'fixPrompt'), ('risk', 'mitigationPrompt')):
                    item = step.get(field)
                    if not isinstance(item, dict): continue
                    prompt = item.get(prompt_key, '')
                    if not isinstance(prompt, str): continue  # Schema reports invalid types.
                    for ref in step.get('refs', []):
                        if not all(k in ref for k in ('path', 'start', 'end')): continue
                        citation = f"{ref['path']}:{ref['start']}-{ref['end']}"
                        if citation not in prompt:
                            errors.append(f"{field}.{prompt_key} for {step.get('id', '?')} must include {citation}")
                    if not prompt.strip():
                        errors.append(f"{field}.{prompt_key} for {step.get('id', '?')} is required")
    if errors: raise ValueError('Invalid tour:\n'+'\n'.join(errors))
    dist=ASSET_ROOT/'viewer/dist/assets'
    js=list(dist.glob('*.js')); css=list(dist.glob('*.css'))
    if len(js)!=1 or len(css)!=1: raise ValueError('Viewer assets missing or ambiguous; build the viewer first')
    payload=json.dumps(tour,indent=2,ensure_ascii=False)+'\n'
    if re.search(r'(?i)(?:/(?:users|home)/[^/\s\"\\]+|[a-z]:\\\\users\\\\[^\\\\\s\"]+)', payload):
        raise ValueError('Tour contains a developer-specific absolute home path; remove or redact it before packaging')
    inline=json.dumps(tour,ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    html='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Goshomi — Your Code. Explained.</title><link rel="stylesheet" href="assets/viewer.css"><script>window.GOSHOMI_TOUR='+inline+';</script><script defer src="assets/viewer.js"></script></head><body><div id="root"></div></body></html>\n'
    files={'index.html':html.encode(),'tour.json':payload.encode(),'assets/viewer.js':js[0].read_bytes(),'assets/viewer.css':css[0].read_bytes()}
    for name,source in tour['sources'].items(): files['sources/'+digest(name)+'.txt']=source['content'].encode()
    if baseline is not None and git_snapshot(root,out) != baseline:
        raise ValueError('Repository changed during packaging; refresh the analysis')
    owner=prepare(root,out); previous=set(owner['files'])
    for name in previous | set(files):
        dest=safe_output(out,name)
        if name not in previous and dest.exists(): raise ValueError(f'Refusing to replace unmanaged output file: {name}')
        if dest.exists() and not dest.is_file(): raise ValueError(f'Output path is not a file: {name}')
    # No deletion or write occurs outside output; only files in the previous manifest can be replaced.
    for name,data in files.items():
        dest=safe_output(out,name); dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(data)
    for name in previous-set(files):
        dest=safe_output(out,name)
        if dest.exists(): dest.unlink()
    owner['files']=sorted(files)
    owner['fileHashes']={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    (out/MARKER).write_text(json.dumps(owner,indent=2)+'\n')
    print(f'Generated tour: {out / "index.html"}')

def verify(root,out):
    marker=out/MARKER
    if not marker.is_file() or marker.is_symlink(): raise ValueError('Missing ownership marker')
    if json.loads(marker.read_text()).get('repositoryId') != owner_id(root): raise ValueError('Output belongs to a different repository')
    tour=json.loads((out/'tour.json').read_text()); actual=excerpts(root,tour)
    if actual != tour['sources']: raise ValueError('Referenced source excerpts changed since packaging')
    for name,source in actual.items():
        path=safe_output(out,'sources/'+digest(name)+'.txt')
        if not path.is_file() or path.read_text()!=source['content']: raise ValueError(f'Source snapshot mismatch: {name}')
    if revision(root)!=tour['repository'].get('revision'): raise ValueError('Git revision changed')
    from validate import validate
    errors=validate(tour)
    if errors: raise ValueError('\n'.join(errors))
    print('Schema, source excerpts, references, symbols and revision verified.')

def check_reusable(root,out):
    marker=out/MARKER
    if not marker.is_file() or marker.is_symlink(): raise ValueError('No reusable tour: missing ownership marker')
    owner=json.loads(marker.read_text())
    if owner.get('repositoryId') != owner_id(root): raise ValueError('No reusable tour: output belongs to a different repository')
    files=owner.get('files'); hashes=owner.get('fileHashes')
    if not isinstance(files,list) or not isinstance(hashes,dict) or set(files)!=set(hashes):
        raise ValueError('No reusable tour: output has no integrity manifest')
    if not {'index.html','tour.json','assets/viewer.js','assets/viewer.css'}.issubset(files):
        raise ValueError('No reusable tour: viewer files are missing from the manifest')
    for name in files:
        path=safe_output(out,name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=hashes[name]:
            raise ValueError(f'No reusable tour: generated file missing or changed: {name}')
    tour=json.loads((out/'tour.json').read_text())
    from validate import validate
    errors=validate(tour)
    if errors: raise ValueError('No reusable tour: invalid data')
    for chapter in tour.get('chapters',[]):
        for step in chapter.get('steps',[]):
            risk=step.get('risk')
            if risk and (not risk.get('assessment') or not risk.get('mitigationPrompt')):
                raise ValueError('No reusable tour: threat findings need qualitative assessments and mitigation prompts')
    if tour.get('repository',{}).get('threatReviewPolicy') != REVIEW_POLICY:
        raise ValueError('No reusable tour: security path review needs refresh')
    baseline=tour.get('repository',{}).get('gitFingerprint')
    if not isinstance(baseline,str) or not re.fullmatch(r'[0-9a-f]{64}',baseline):
        raise ValueError('No reusable tour: no Git snapshot was captured before analysis')
    if git_snapshot(root,out)!=baseline: raise ValueError('No reusable tour: repository changed since analysis')
    print(f'Tour is current: {out / "index.html"}')

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    for command in ('index','prepare','package','verify','snapshot','check','output-status'):
        c=sub.add_parser(command); c.add_argument('--repo',help='Target directory (default: current project Git root, or current directory)'); c.add_argument('--output',help='Output directory (default: REPO/.goshomi)')
        if command=='package':
            c.add_argument('--analysis',required=True,help='Agent-authored analysis JSON')
            c.add_argument('--baseline',help='Git snapshot captured before analysis; enables safe reuse')
            c.add_argument('--review-policy',choices=[REVIEW_POLICY, PREVIOUS_REVIEW_POLICY, LEGACY_REVIEW_POLICY],help='Attest that the agent completed the specified review before packaging')
    a=p.parse_args(); root=target_repo(a.repo); out=output_path(root,a.output)
    checkout=ASSET_ROOT.parent.parent
    if a.cmd in ('prepare','package') and not a.repo and root == checkout and (checkout / '.agents/skills/goshomi/SKILL.md').exists():
        raise ValueError('Select the Goshomi source checkout explicitly with --repo before writing a tour here')
    if a.cmd=='output-status': print(json.dumps(output_status(out), indent=2))
    elif a.cmd=='index': print(json.dumps({'revision':revision(root),'files':index(root,out)},indent=2))
    elif a.cmd=='prepare': prepare(root,out); print(f'Output ready: {out}')
    elif a.cmd=='package': package(root,a.analysis,out,a.baseline,a.review_policy)
    elif a.cmd=='verify': verify(root,out)
    elif a.cmd=='snapshot': print(git_snapshot(root,out))
    else: check_reusable(root,out)

if __name__=='__main__':
    try: main()
    except (ValueError,OSError,UnicodeError,json.JSONDecodeError,KeyError,TypeError) as e: print(str(e),file=sys.stderr); sys.exit(1)
