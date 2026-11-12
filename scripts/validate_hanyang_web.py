"""Validate web extension hashes, scope metadata and existing parser compatibility."""
from pathlib import Path
import hashlib,json,sys

def validate_web_extension(data_root, manifest_path, parser, extractor):
 data_root=Path(data_root);manifest_path=Path(manifest_path)
 manifest=json.loads(manifest_path.read_text());folder=data_root/'filter_ready'/('web_'+manifest['retrieved_on'])
 schema=json.loads(manifest_path.with_name(manifest_path.name.replace('.manifest.json','.schema.json')).read_text())
 parsed={};raw_checked=set();units=manifest['units']
 assert manifest['prepared_documents']==len(units)
 for r in manifest['records']:
  if r['status']!='downloaded':continue
  p=data_root/r['raw_source_path']
  if p not in raw_checked:
   assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],p
   raw_checked.add(p)
 for u in units:
  p=folder/u['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==u['sha256'],p
  doc=parser.parse(p);meta=extractor.extract(doc).extra;expected=u['metadata']
  assert doc.title==expected['title'];assert set(schema['required_fields'])-{'title'}<=meta.keys()
  from app.rag.schemas import metadata_values,RetrievalFilter
  for k,v in expected.items():
   if k!='title':assert metadata_values(meta.get(k))==metadata_values(v),(p,k)
  assert meta['retrieved_on']=='2026-11-12'
  assert meta['campus'] in ('SEOUL','ERICA')
  assert meta['source_url'] in doc.full_text()
  assert doc.sections and all(s.heading and s.text for s in doc.sections)
  assert not any(x in doc.full_text().lower() for x in ['<script','skip to content','consent to the privacy policy','세션id'])
  if meta['scope']=='college':assert 'department' not in meta
  if 'academic_year' in meta:
   assert meta['source_type']=='pdf' and meta['academic_year']=='2027' and meta['term']=='spring'
   assert meta['academic_level']=='undergraduate' and meta['campus']=='SEOUL'
  else:assert 'effective_date' not in meta
  assert RetrievalFilter(conditions={'campus':[meta['campus'].lower()]},include_unknown=False).matches(meta)
  other='erica' if meta['campus']=='SEOUL' else 'seoul'
  assert not RetrievalFilter(conditions={'campus':[other]},include_unknown=False).matches(meta)
  parsed[str(p.relative_to(data_root/'filter_ready'))]=(doc,meta)
 actual={p for p in folder.glob('*.md') if p.name!='README.md'}
 assert actual=={folder/u['path'] for u in units}
 tuition=[m for _,m in parsed.values() if m['topic']=='tuition'];assert tuition and all(m['fee_reference_year']=='2026' for m in tuition)
 report={'status':'PASS','documents':len(units),'selected_source_urls':manifest['selected_source_urls'],'raw_files_hash_checked':len(raw_checked),'downloaded_responses':manifest['downloaded_responses'],'checks':['Raw archive SHA-256','Prepared file SHA-256','Current parser and metadata extractor','Campus filter inclusion and exclusion','Unknown year retained on undated web pages','Tuition reference period differs from admission cycle','College-wide pages omit department','Declared unit set equals active files'],'index_changed':False}
 return report,parsed

if __name__=='__main__':
 import argparse
 from types import SimpleNamespace
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--data-root',type=Path,default=Path('data'));ap.add_argument('--report',type=Path);a=ap.parse_args()
 sys.path.insert(0,str(Path.cwd()/'backend'))
 from app.rag.blocks.ingestion.parsing.basic_parser import BasicDocumentParser
 from app.rag.blocks.ingestion.metadata_extraction.basic_extractor import BasicMetadataExtractor
 services=SimpleNamespace(settings=SimpleNamespace(data_dir=a.data_root))
 report,_=validate_web_extension(a.data_root,a.data_root/'filter_ready.web_2026-11-12.manifest.json',BasicDocumentParser({},services),BasicMetadataExtractor({},services))
 if a.report:a.report.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
