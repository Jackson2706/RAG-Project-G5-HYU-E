from collections import Counter, defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

sys.path.insert(0,str(Path.cwd()/'backend'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_hanyang_web import validate_web_extension
from app.rag.blocks.ingestion.document_loading.local_loader import LocalFolderLoader
from app.rag.blocks.ingestion.parsing.basic_parser import BasicDocumentParser
from app.rag.blocks.ingestion.metadata_extraction.basic_extractor import BasicMetadataExtractor
from app.rag.blocks.ingestion.chunking.section_chunker import SectionTokenChunker
from app.rag.blocks.ingestion.chunking.recursive_chunker import RecursiveChunker
from app.rag.schemas import FilterCriteria, RetrievalFilter, metadata_values
from transformers import AutoTokenizer

ap=argparse.ArgumentParser(description='Validate the supplied filter-ready corpus without changing the index.')
ap.add_argument('folder',nargs='?',type=Path,default=Path('data/filter_ready'))
ap.add_argument('--report',type=Path,help='Optionally save the JSON result; otherwise validation is read-only.')
args=ap.parse_args()
folder=args.folder
manifest=json.loads(folder.with_suffix('.manifest.json').read_text())
schema=json.loads(folder.with_suffix('.schema.json').read_text())
vocabulary=json.loads(folder.with_suffix('.vocabulary.json').read_text())
services=SimpleNamespace(settings=SimpleNamespace(data_dir=folder.parent))
files,skipped=LocalFolderLoader({},services).load(folder)
assert not skipped,skipped
all_files=files
extension_files=set()
web_reports=[]
web_parsed={}
for extension in manifest.get('extensions',[]):
    web_report,extension_parsed=validate_web_extension(folder.parent,folder.parent/extension['manifest'],BasicDocumentParser({},services),BasicMetadataExtractor({},services))
    web_reports.append(web_report)
    web_parsed.update(extension_parsed)
    extension_files.update(folder/path for path in extension_parsed)
files=[p for p in all_files if p not in extension_files]
assert len(all_files)==len(files)+len(extension_files)
assert len(files)==manifest['counts']['output_documents']
assert {p.relative_to(folder).as_posix() for p in files}=={u['path'] for u in manifest['units']}
assert len({u['path'] for u in manifest['units']})==len(files)
assert len({u['metadata']['unit_id'] for u in manifest['units']})==len(files)
parser=BasicDocumentParser({},services)
extractor=BasicMetadataExtractor({},services)
parsed={}
spans=defaultdict(list)
source_sections={}
# Original section IDs and lengths are historical provenance, not disk dependencies.
source_sections={(s['parent_source_uri'],s['section_index']):s for s in manifest['source_sections']}
source_pdf_hashes={name:hashlib.sha256((Path('data/raw')/name).read_bytes()).hexdigest() for name in ['2025_guidebook_en.pdf','Undergraduate Admission Guide.pdf']}
for unit in manifest['units']:
    path=folder/unit['path']
    raw=path.read_text()
    assert hashlib.sha256(path.read_bytes()).hexdigest()==unit['sha256']
    doc=parser.parse(path)
    meta=extractor.extract(doc).extra
    expected=unit['metadata']
    assert doc.title==expected['title']
    for field,value in expected.items():
        if field!='title':
            assert metadata_values(meta.get(field))==metadata_values(value),(path,field,meta.get(field),value)
    assert set(schema['required_fields'])-{'title'}<=meta.keys()
    assert meta['source_sha256']==source_pdf_hashes[meta['source_pdf']]
    assert doc.sections and all(s.heading and s.text for s in doc.sections)
    assert len(doc.sections)==len({s.heading for s in doc.sections}),(path,'duplicate heading')
    assert meta['audience']==meta['academic_level']
    assert metadata_values(meta['topics'])==metadata_values(meta['topic'])
    for field,values in schema['allowed_values'].items():
        if field in meta:
            assert set(metadata_values(meta[field]))<={str(v).lower() for v in values},(path,field)
    for field in schema['identifier_fields']:
        for value in metadata_values(meta.get(field)):
            assert value=='all' or re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',value),(path,field,value)
    if meta['source_group']=='majors_guidebook':
        assert 'academic_year' not in meta and 'term' not in meta and 'effective_date' not in meta
        assert meta['campus']=='SEOUL' and meta['academic_level']=='undergraduate'
        assert meta['source_cover_year']=='2024' and meta['source_filename_year']=='2025'
        assert 'student_category' not in meta
    else:
        assert meta['academic_year']=='2027' and meta['term']=='spring'
        assert 'effective_date' not in meta
    if meta['department_scope']=='all_departments':
        assert meta['department']=='ALL'
    if meta['scope']=='department':
        assert meta.get('department') not in (None,'ALL')
    if meta['college_scope']=='all_colleges':
        assert meta['college']=='ALL'
    for f in unit['coverage']:
        section=source_sections[(f['parent_source_uri'],f['section_index'])]
        assert section['heading']==f['section_heading']
        assert 0<=f['start']<f['end']<=section['body_length']
        assert re.fullmatch('[0-9a-f]{64}',f['sha256'])
        spans[(f['parent_source_uri'],f['section_index'])].append((f['start'],f['end']))
    parsed[unit['path']]=(doc,meta)

assert len(source_sections)==manifest['counts']['source_sections']
assert set(spans)==set(source_sections)

def find(predicate):
    matches=[(path,doc,md) for path,(doc,md) in parsed.items() if predicate({**md,'title':doc.title})]
    assert matches,'Missing validation witness'
    return matches[0]

checks=[]
def check(name,conditions,md,expected,unknown=False):
    predicate=RetrievalFilter(conditions={k:metadata_values(v) for k,v in conditions.items()},include_unknown=unknown)
    assert predicate.matches(md)==expected,name
    checks.append(name)

_,architecture,am=find(lambda m:m.get('department')=='architecture' and m['topic']=='overview' and m['document_type']=='major_guide')
check('Seoul undergraduate architecture overview matches',{'campus':'seoul','academic_level':'undergraduate','department':'architecture','topic':'overview'},am,True)
check('ERICA excludes Seoul curriculum',{'campus':'erica'},am,False)
check('Graduate excludes undergraduate curriculum',{'academic_level':'graduate'},am,False)
check('Topic courses excludes overview',{'topic':'courses'},am,False)
check('Unknown guidebook year: strict excludes',{'academic_year':'2025'},am,False)
check('Unknown guidebook year: permissive includes',{'academic_year':'2025'},am,True,True)
check('Unknown student category: strict excludes',{'student_category':'international'},am,False)
check('Unknown student category: permissive includes',{'student_category':'international'},am,True,True)

_,shared,sm=find(lambda m:m['topic']=='application_process')
check('Shared flow covers undergraduate',{'academic_level':'undergraduate'},sm,True)
check('Shared flow covers graduate',{'academic_level':'graduate'},sm,True)
assert FilterCriteria(campus='ERICA').to_filter(include_unknown=False).matches(sm)
checks.append('Existing campus-wide predicate retains common application flow')
_,gsis,gm=find(lambda m:m['topic']=='scholarships' and m.get('college')=='international-studies' and m['campus']=='SEOUL')
_,industrial,im=find(lambda m:m['topic']=='scholarships' and m.get('college')=='industrial-convergence' and m['campus']=='ERICA')
assert '20% tuition reduction' in gsis.full_text() and '30% tuition reduction' not in gsis.full_text()
assert '30% tuition reduction' in industrial.full_text() and '20% tuition reduction' not in industrial.full_text()
check('Seoul scholarship excludes ERICA unit',{'campus':'seoul'},im,False)
check('ERICA scholarship excludes Seoul unit',{'campus':'erica'},gm,False)
_,hisp,hm=find(lambda m:m['topic']=='scholarships' and 'hisp' in m['title'].lower())
check('Explicit shared department wildcard can retain general HISP',{'academic_level':'graduate','department':['architecture','all'],'topic':'scholarships'},hm,True)
check('Graduate HISP is excluded for undergraduates',{'academic_level':'undergraduate'},hm,False)
_,nursing,nm=find(lambda m:m['record_type']=='program_availability' and m.get('department')=='nursing')
assert metadata_values(nm['available_degree_levels'])==['masters','phd']
assert 'Combined MA–Ph.D.: not available' in nursing.full_text()
check('Unavailable combined degree row is still searchable',{'degree_level':'combined'},nm,True)
check('Availability outcome is distinct from discussed degree',{'available_degree_levels':'combined'},nm,False)
_,voice,vm=find(lambda m:m.get('degree_level')=='phd' and 'Music Voice' in m['title'])
check('PhD requirements match PhD',{'degree_level':'phd'},vm,True)
check('PhD-specific requirements exclude masters',{'degree_level':'masters'},vm,False)

parsed.update(web_parsed)
tokenizer=AutoTokenizer.from_pretrained('BAAI/bge-small-en-v1.5',revision='5c38ec7c405ec4b44b94cc5a9bb96e735b38267a',local_files_only=True)
class TokenCounter:
    def token_offsets(self,text):
        return [(s,e) for s,e in tokenizer(text,add_special_tokens=False,return_offsets_mapping=True,verbose=False)['offset_mapping'] if e>s]
    def count_tokens(self,text):
        return len(self.token_offsets(text))
services.embedder=TokenCounter()
chunk_counts={}
for cls in [SectionTokenChunker,RecursiveChunker]:
    count=0
    for doc,meta in parsed.values():
        cs=cls({'chunk_size':256,'chunk_overlap':32},services).chunk(doc)
        assert cs and all(0<c.token_count<=256 for c in cs)
        assert all(doc.full_text()[c.start:c.end]==c.text for c in cs)
        count+=len(cs)
    chunk_counts[cls.__name__]=count
result={'documents':len(all_files),'base_documents':len(files),'web_extensions':web_reports,'source_documents':manifest['counts']['source_documents'],'historical_source_sections':manifest['counts']['source_sections'],'base_topics':len(vocabulary['topics']),'topics':len({value for _,md in parsed.values() for value in metadata_values(md.get('topic'))}),
    'metadata_extraction':'PASS with current BasicDocumentParser and BasicMetadataExtractor',
    'source_validation':'PASS: current raw and prepared file hashes; historical section references and bounds. Original Markdown coverage was checked before removing intermediates.',
    'filter_data_checks':checks,'chunk_counts':chunk_counts,'max_chunk_tokens':256,
    'backend_filters_changed':False,'database_index_changed':False}
if args.report:
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
