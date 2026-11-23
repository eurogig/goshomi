#!/usr/bin/env python3
"""Validate a tour against the schema subset used by tour.schema.json and cross-links."""
import json,sys
from urllib.parse import urlsplit
from pathlib import Path
schema=json.loads((Path(__file__).resolve().parent.parent/'schema/tour.schema.json').read_text())
errors=[]
def check(value, rule, path='$'):
    if '$ref' in rule: return check(value, schema['definitions'][rule['$ref'].split('/')[-1]], path)
    types=rule.get('type'); types=[types] if isinstance(types,str) else types
    predicates={'object':lambda x:isinstance(x,dict),'array':lambda x:isinstance(x,list),'string':lambda x:isinstance(x,str),'integer':lambda x:isinstance(x,int) and not isinstance(x,bool),'number':lambda x:isinstance(x,(int,float)) and not isinstance(x,bool),'null':lambda x:x is None}
    if types and not any(predicates[t](value) for t in types): errors.append(f'{path}: expected {types}'); return
    if 'const' in rule and value != rule['const']: errors.append(f'{path}: unexpected value')
    if 'enum' in rule and value not in rule['enum']: errors.append(f'{path}: invalid choice')
    if isinstance(value,str) and len(value)<rule.get('minLength',0): errors.append(f'{path}: empty string')
    if isinstance(value,(int,float)) and not isinstance(value,bool) and value<rule.get('minimum',float('-inf')): errors.append(f'{path}: below minimum')
    if isinstance(value,list):
        if len(value)<rule.get('minItems',0) or len(value)>rule.get('maxItems',float('inf')): errors.append(f'{path}: invalid item count')
        for i,item in enumerate(value): check(item,rule.get('items',{}),f'{path}[{i}]')
    if isinstance(value,dict):
        for k in rule.get('required',[]):
            if k not in value: errors.append(f'{path}: missing {k}')
        props=rule.get('properties',{})
        for k,v in value.items():
            if k in props: check(v,props[k],f'{path}.{k}')
            elif isinstance(rule.get('additionalProperties'),dict): check(v,rule['additionalProperties'],f'{path}.{k}')
            elif rule.get('additionalProperties') is False: errors.append(f'{path}: unexpected {k}')
def validate(tour):
    global errors
    errors=[]
    check(tour,schema)
    return crosscheck(tour)

def crosscheck(tour):
  try:
      ids=[n['id'] for n in tour['nodes']]
      if len(ids)!=len(set(ids)): errors.append('duplicate node IDs')
      for edge in tour['edges']:
          if edge['source'] not in ids or edge['target'] not in ids: errors.append('edge references missing node')
      for chapter in tour['chapters']:
          for step in chapter['steps']:
              if step['node'] not in ids: errors.append('step references missing node')
              risk=step.get('risk',{})
              for reference in risk.get('assessment',{}).get('references',[]):
                  parsed=urlsplit(reference['url'])
                  host=(parsed.hostname or '').lower()
                  if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None,443) or not (host=='owasp.org' or host.endswith('.owasp.org') or host=='mitre.org' or host.endswith('.mitre.org')):
                      errors.append('reference must link to an official OWASP or MITRE HTTPS page')
              path=risk.get('attackPath',[])
              if isinstance(path,list):
                  for node_id in path:
                      if node_id not in ids: errors.append('attack path references missing node: '+str(node_id))
                  for source,target in zip(path,path[1:]):
                      if not any({edge['source'],edge['target']} == {source,target} and source != target for edge in tour['edges']):
                          errors.append(f'attack path has no architecture connection: {source} -> {target}')
      from tour import all_refs, SECRET
      for r in all_refs({k:v for k,v in tour.items() if k!='sources'}):
          if r['path'] not in tour['sources']: errors.append('reference missing packaged source: '+r['path'])
      for name,source in tour['sources'].items():
          if SECRET.search(source['content']): errors.append('possible secret in packaged source: '+name)
  except (KeyError,TypeError,ValueError,AttributeError): errors.append('cross-link validation failed due to invalid structure')
  return errors

if __name__ == '__main__':
    errors=validate(json.loads(Path(sys.argv[1]).read_text()))
    if errors: print('\n'.join(errors),file=sys.stderr); sys.exit(1)
    print('Schema and cross-links valid.')
