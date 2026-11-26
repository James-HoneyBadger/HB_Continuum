# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Versioned, validated local preferences. No account credentials."""
from pathlib import Path
from schedule import read_json,write_json

# key: (section, label, default, allowed values or inclusive integer bounds)
FIELDS={
    'theme':('Appearance','Interface theme','System',('System','Light','Dark')),
    'font_size':('Appearance','Reader font size',13,(9,28)),
    'font_family':('Appearance','Reader font family','System',('System','Monospace','Serif')),
    'wrap':('Appearance','Reader wrapping','word',('word','char','none')),
    'layout':('Appearance','Message pane orientation','vertical',('vertical','horizontal')),
    'window_width':('Appearance','Initial window width',1150,(800,2400)),
    'window_height':('Appearance','Initial window height',760,(500,1600)),
    'subject_width':('Appearance','Subject column width',550,(100,1600)),
    'sender_width':('Appearance','Sender column width',260,(100,1000)),
    'show_hash':('Appearance','Show SHA-256 in reader',True,None),
    'show_message_ids':('Appearance','Show message and reply IDs',True,None),
    'search_limit':('Research','Search result limit',100,(10,5000)),
    'recent_limit':('Research','Recent message limit',100,(10,5000)),
    'timeline_limit':('Research','Timeline result limit',100,(10,5000)),
    'correspondent_limit':('Research','Correspondent result limit',100,(10,5000)),
    'search_mode':('Research','Default search mode','FTS',('FTS','Exact phrase')),
    'startup_view':('Research','Startup view','Recent',('Recent','Saved query')),
    'startup_query':('Research','Startup saved query','',None),
    'export_directory':('Files','Default evidence export directory','',None),
    'import_directory':('Files','Default EML import directory','',None),
    'verify_on_start':('Integrity','Verify hashes on GUI startup',False,None),
    'network_timeout':('Synchronization','IMAP timeout (seconds)',30,(10,300)),
    'batch_limit':('Synchronization','Maximum new messages per folder per run (0 = unlimited)',0,(0,50000)),
    'ai_enabled':('AI','Enable local AI',False,None),
    'ai_backend':('AI','AI backend','none',('none','ollama')),
    'ai_endpoint':('AI','Ollama endpoint','http://localhost:11434',None),
    'ai_model':('AI','Ollama model','llama3.2',None),
    'ai_timeout':('AI','AI timeout (seconds)',120,(10,600)),
    'ai_batch_size':('AI','AI batch size',8,(1,100)),
    'ai_max_input_chars':('AI','Maximum input characters per request',12000,(500,100000)),
    'ai_prompt_version':('AI','Summarization prompt version','1',None),
}
DEFAULTS={k:v[2] for k,v in FIELDS.items()}

def validate(data):
    if not isinstance(data,dict): raise ValueError('Preferences must be an object')
    unknown=set(data)-set(FIELDS)
    if unknown: raise ValueError('Unknown preferences: '+', '.join(sorted(unknown)))
    result=DEFAULTS.copy()
    for k,v in data.items():
        _,label,default,allowed=FIELDS[k]
        if type(v) is not type(default): raise ValueError(label+': incorrect value type')
        if isinstance(default,int) and not isinstance(default,bool):
            if not allowed[0]<=v<=allowed[1]: raise ValueError(label+': out of range')
        elif allowed and v not in allowed: raise ValueError(label+': invalid choice')
        elif isinstance(v,str) and (len(v)>4096 or '\x00' in v):raise ValueError(label+': invalid text')
        result[k]=v
    if result['startup_view']=='Saved query' and not result['startup_query'].strip():raise ValueError('Startup saved query cannot be empty')
    if result['ai_backend']!='none':
        if not result['ai_model'].strip():raise ValueError('AI model cannot be empty')
        if not result['ai_endpoint'].strip().lower().startswith(('http://','https://')):raise ValueError('Ollama endpoint must be an http(s) URL')
    if not result['ai_prompt_version'].strip():raise ValueError('Prompt version cannot be empty')
    return result

def decode(doc):
    if not isinstance(doc,dict) or doc.get('version')!=1 or set(doc)!={'version','preferences'}:raise ValueError('Unsupported preferences file')
    return validate(doc['preferences'])

def load(root):
    return decode(read_json(Path(root)/'preferences.json',{'version':1,'preferences':{}}))

def save(root,values):
    write_json(Path(root)/'preferences.json',{'version':1,'preferences':validate(values)})

def export(path,values):
    # Explicitly selected file; no account profiles, secrets or message data.
    write_json(Path(path),{'version':1,'preferences':validate(values)})
