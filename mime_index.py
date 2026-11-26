"""Bounded, offline MIME extraction. Never render HTML or execute attachments."""
from html.parser import HTMLParser
from email import policy
from email.parser import BytesParser
from pathlib import Path

TEXT_LIMIT=2_000_000
ATTACHMENT_LIMIT=2_000_000
PART_LIMIT=1000
TEXT_EXT={'.txt','.csv','.tsv','.md','.json','.xml','.log','.ics','.vcf'}

class HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden=0
        self.chunks=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','head','template'):self.hidden+=1
        elif not self.hidden and tag in ('p','br','div','li','tr','td','h1','h2','h3','blockquote'):self.chunks.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','head','template'):self.hidden=max(0,self.hidden-1)
        elif not self.hidden and tag in ('p','div','li','tr'):self.chunks.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.chunks.append(data)

def html_text(value):
    p=HTMLText()
    p.feed(value[:TEXT_LIMIT]);p.close()
    return ''.join(p.chunks)[:TEXT_LIMIT]

def part_text(part,limit=TEXT_LIMIT):
    try:payload=part.get_payload(decode=True)
    except (ValueError,TypeError,UnicodeError):return ''
    if not isinstance(payload,bytes):return ''
    charset=part.get_content_charset() or 'utf-8'
    try:return payload[:limit].decode(charset,'replace')[:limit]
    except (LookupError,UnicodeError):return payload[:limit].decode('utf-8','replace')

def body_parts(part):
    """Prefer one alternative, retain inline mixed parts, skip attachments."""
    if part.get_filename() or part.get_content_disposition()=='attachment':
        return
    kind=part.get_content_type()
    if kind=='multipart/alternative':
        preferred=part.get_body(preferencelist=('plain','html'))
        if preferred is not None:
            value=part_text(preferred)
            if preferred.get_content_type()=='text/html':value=html_text(value)
            if not value.strip():
                alternative=part.get_body(preferencelist=('html',))
                if alternative is not None:value=html_text(part_text(alternative))
            if value.strip():yield value
    elif kind=='multipart/related':
        preferred=part.get_body(preferencelist=('plain','html'))
        if preferred is not None:yield from body_parts(preferred)
    elif kind.startswith('multipart/'):
        for child in part.iter_parts():yield from body_parts(child)
    elif kind in ('text/plain','text/html'):
        value=part_text(part)
        yield html_text(value) if kind=='text/html' else value

def extract(raw):
    msg=BytesParser(policy=policy.default).parsebytes(raw)
    chunks=[];remaining_body=TEXT_LIMIT
    for i,value in enumerate(body_parts(msg)):
        if i>=PART_LIMIT or remaining_body<=0:break
        value=value[:remaining_body]
        chunks.append(value)
        remaining_body-=len(value)+1
    body='\n'.join(chunks)[:TEXT_LIMIT]
    attachments=[];remaining=ATTACHMENT_LIMIT
    for i,part in enumerate(msg.walk()):
        if i>=PART_LIMIT:break
        filename=part.get_filename()
        if not filename and part.get_content_disposition()!='attachment':continue
        filename=str(filename or '(unnamed)')[:1024]
        kind=part.get_content_type()
        content=''
        if remaining and not part.is_multipart():
            if kind=='text/html':content=html_text(part_text(part,remaining))[:remaining]
            elif kind.startswith('text/') or Path(filename).suffix.lower() in TEXT_EXT:
                content=part_text(part,remaining)
        remaining-=len(content)
        attachments.append((i,filename,kind,content))
    return msg,body,attachments

def index_text(body,attachments):
    return (body+'\n'+'\n'.join(name+'\n'+kind+'\n'+content for _,name,kind,content in attachments))[:TEXT_LIMIT+ATTACHMENT_LIMIT+1_100_000]
