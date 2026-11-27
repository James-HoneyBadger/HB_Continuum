# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
"""Independently understandable exports of archive state.

A report is assembled from data the caller already collected and then
rendered to Markdown, JSON or standalone HTML. Rendering is pure, so the
same report can be checked in tests without a database. Reports are written
exclusively: an existing file is never overwritten.
"""
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path

EXTENSIONS = {'markdown': '.md', 'json': '.json', 'html': '.html'}

LIMITATIONS = (
    'Counts describe what is stored in this archive, not what exists on any '
    'remote service or in any source export.',
    'Importing folders or files does not prove that a source was captured completely.',
    'Hash verification detects changes in stored bytes. It is not proof of '
    'authenticity, legal admissibility or chain of custody.',
    'Records without a normalized date are excluded from the date range and '
    'from records-by-year counts.',
    'The report contains no credentials. It does contain record metadata the '
    'user chose to export and should be stored accordingly.',
)

def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def _health_summary(health):
    if not isinstance(health, dict):
        return {'available': False}
    summary = {
        'available': True,
        'sqlite_ok': bool(health.get('sqlite_ok')),
        'foreign_key_errors': health.get('foreign_key_errors', 0),
        'messages': health.get('messages', 0),
        'undated': health.get('undated'),
        'index_missing': len(health.get('index_missing') or []),
        'index_extra': len(health.get('index_extra') or []),
        'index_duplicate_rows': health.get('index_duplicate_rows', 0),
        'raw_missing': len(health.get('raw_missing') or []),
        'raw_unindexed': len(health.get('raw_unindexed') or []),
        'raw_invalid': len(health.get('raw_invalid') or []),
    }
    summary['consistent'] = (summary['sqlite_ok']
                             and not any(summary[key] for key in (
                                 'foreign_key_errors', 'index_missing', 'index_extra',
                                 'index_duplicate_rows', 'raw_missing',
                                 'raw_unindexed', 'raw_invalid')))
    return summary

def build_archive_report(sources, dashboard, health, history, title=None):
    """Assemble a report dict from inventory, summary, health and history data."""
    archive = dashboard.get('archive', {}) if isinstance(dashboard, dict) else {}
    storage = dashboard.get('storage', {}) if isinstance(dashboard, dict) else {}
    imports = (history or {}).get('runs', [])[:20] if isinstance(history, dict) else []
    return {
        'title': title or 'HB Continuum archive report',
        'generated_at': _now(),
        'date_range': {'earliest': archive.get('earliest'), 'latest': archive.get('latest')},
        'summary': {
            'messages': archive.get('messages', 0),
            'origins': archive.get('origins', 0),
            'undated': archive.get('undated', 0),
            'catalog_records': (dashboard.get('catalog') or {}).get('records', 0)
            if isinstance(dashboard, dict) else 0,
            'catalog_files': (dashboard.get('catalog') or {}).get('files', 0)
            if isinstance(dashboard, dict) else 0,
            'storage_bytes': storage.get('total_bytes', 0),
        },
        'email_accounts': list((sources or {}).get('email_accounts', [])),
        'catalog_sources': list((sources or {}).get('catalog_sources', [])),
        'by_year': list((dashboard or {}).get('by_year', [])),
        'health': _health_summary(health),
        'imports': imports,
        'history_available': bool((sources or {}).get('history_available', False)),
        'limitations': list(LIMITATIONS),
    }

def _value(value):
    if value is None or value == '':
        return '—'
    return str(value)

def _markdown_table(headers, rows):
    lines = ['| ' + ' | '.join(headers) + ' |',
             '|' + '|'.join('---' for _ in headers) + '|']
    for row in rows:
        lines.append('| ' + ' | '.join(_value(cell).replace('|', '\\|') for cell in row) + ' |')
    return lines

def render_markdown(report):
    lines = [f"# {report['title']}", '',
             f"Generated: {report['generated_at']}", '']
    span = report.get('date_range') or {}
    lines += [f"Date range: {_value(span.get('earliest'))} to {_value(span.get('latest'))}", '']

    summary = report.get('summary') or {}
    lines += ['## Summary', ''] + _markdown_table(
        ('Measure', 'Value'),
        [('Unique messages', summary.get('messages', 0)),
         ('Mailbox origins', summary.get('origins', 0)),
         ('Undated records', summary.get('undated', 0)),
         ('Catalog records', summary.get('catalog_records', 0)),
         ('Catalog source files', summary.get('catalog_files', 0)),
         ('Storage footprint (bytes)', summary.get('storage_bytes', 0))]) + ['']

    years = report.get('by_year') or []
    lines += ['## Records by year', '']
    lines += (_markdown_table(('Year', 'Records'), [(row['year'], row['count']) for row in years])
              if years else ['None recorded.']) + ['']

    lines += ['## Email accounts', '']
    accounts = report.get('email_accounts') or []
    lines += (_markdown_table(
        ('Account', 'Messages', 'Origins', 'Folders', 'Earliest', 'Latest', 'Last import'),
        [(a.get('account'), a.get('messages'), a.get('origins'), a.get('folders'),
          a.get('earliest'), a.get('latest'),
          (a.get('last_import') or {}).get('status')) for a in accounts])
        if accounts else ['No mailbox origins recorded.']) + ['']

    lines += ['## Catalog sources', '']
    catalogs = report.get('catalog_sources') or []
    lines += (_markdown_table(
        ('Source', 'Records', 'Files', 'Bytes', 'Earliest', 'Latest'),
        [(c.get('source_type'), c.get('records'), c.get('files'), c.get('bytes'),
          c.get('earliest'), c.get('latest')) for c in catalogs])
        if catalogs else ['No catalog sources recorded.']) + ['']

    health = report.get('health') or {}
    lines += ['## Consistency', '']
    if health.get('available'):
        lines += _markdown_table(
            ('Check', 'Result'),
            [('SQLite quick check', 'ok' if health.get('sqlite_ok') else 'failed'),
             ('Foreign key errors', health.get('foreign_key_errors')),
             ('Missing search rows', health.get('index_missing')),
             ('Search rows without a message', health.get('index_extra')),
             ('Duplicate search rows', health.get('index_duplicate_rows')),
             ('Missing originals', health.get('raw_missing')),
             ('Unindexed originals', health.get('raw_unindexed')),
             ('Altered or unsafe originals', health.get('raw_invalid')),
             ('Records without a normalized date', health.get('undated'))]) + ['']
    else:
        lines += ['Consistency data was unavailable.', '']

    lines += ['## Recent imports', '']
    imports = report.get('imports') or []
    lines += (_markdown_table(
        ('Finished', 'Source', 'Target', 'Status', 'New', 'Existing', 'Failed'),
        [(i.get('finished_at') or i.get('started_at'), i.get('source'),
          i.get('source_key'), i.get('status'), i.get('records_new'),
          i.get('records_existing'), i.get('records_failed')) for i in imports])
        if imports else ['No import runs recorded.']) + ['']

    lines += ['## Limitations', '']
    lines += [f"- {item}" for item in report.get('limitations') or []]
    return '\n'.join(lines).rstrip() + '\n'

def _html_table(headers, rows):
    parts = ['<table><thead><tr>']
    parts += [f'<th>{html.escape(str(header))}</th>' for header in headers]
    parts.append('</tr></thead><tbody>')
    for row in rows:
        parts.append('<tr>')
        parts += [f'<td>{html.escape(_value(cell))}</td>' for cell in row]
        parts.append('</tr>')
    parts.append('</tbody></table>')
    return ''.join(parts)

def render_html(report):
    esc = html.escape
    span = report.get('date_range') or {}
    summary = report.get('summary') or {}
    health = report.get('health') or {}
    body = [f"<h1>{esc(report['title'])}</h1>",
            f"<p class=\"meta\">Generated {esc(report['generated_at'])} · "
            f"date range {esc(_value(span.get('earliest')))} to "
            f"{esc(_value(span.get('latest')))}</p>",
            '<h2>Summary</h2>',
            _html_table(('Measure', 'Value'), [
                ('Unique messages', summary.get('messages', 0)),
                ('Mailbox origins', summary.get('origins', 0)),
                ('Undated records', summary.get('undated', 0)),
                ('Catalog records', summary.get('catalog_records', 0)),
                ('Catalog source files', summary.get('catalog_files', 0)),
                ('Storage footprint (bytes)', summary.get('storage_bytes', 0))])]
    years = report.get('by_year') or []
    body += ['<h2>Records by year</h2>',
             _html_table(('Year', 'Records'), [(r['year'], r['count']) for r in years])
             if years else '<p class="meta">None recorded.</p>']
    accounts = report.get('email_accounts') or []
    body += ['<h2>Email accounts</h2>',
             _html_table(('Account', 'Messages', 'Origins', 'Folders', 'Earliest', 'Latest'),
                         [(a.get('account'), a.get('messages'), a.get('origins'),
                           a.get('folders'), a.get('earliest'), a.get('latest'))
                          for a in accounts])
             if accounts else '<p class="meta">No mailbox origins recorded.</p>']
    catalogs = report.get('catalog_sources') or []
    body += ['<h2>Catalog sources</h2>',
             _html_table(('Source', 'Records', 'Files', 'Bytes', 'Earliest', 'Latest'),
                         [(c.get('source_type'), c.get('records'), c.get('files'),
                           c.get('bytes'), c.get('earliest'), c.get('latest'))
                          for c in catalogs])
             if catalogs else '<p class="meta">No catalog sources recorded.</p>']
    body += ['<h2>Consistency</h2>']
    if health.get('available'):
        body.append(_html_table(('Check', 'Result'), [
            ('SQLite quick check', 'ok' if health.get('sqlite_ok') else 'failed'),
            ('Foreign key errors', health.get('foreign_key_errors')),
            ('Missing search rows', health.get('index_missing')),
            ('Search rows without a message', health.get('index_extra')),
            ('Duplicate search rows', health.get('index_duplicate_rows')),
            ('Missing originals', health.get('raw_missing')),
            ('Unindexed originals', health.get('raw_unindexed')),
            ('Altered or unsafe originals', health.get('raw_invalid')),
            ('Records without a normalized date', health.get('undated'))]))
    else:
        body.append('<p class="meta">Consistency data was unavailable.</p>')
    imports = report.get('imports') or []
    body += ['<h2>Recent imports</h2>',
             _html_table(('Finished', 'Source', 'Target', 'Status', 'New', 'Existing', 'Failed'),
                         [(i.get('finished_at') or i.get('started_at'), i.get('source'),
                           i.get('source_key'), i.get('status'), i.get('records_new'),
                           i.get('records_existing'), i.get('records_failed'))
                          for i in imports])
             if imports else '<p class="meta">No import runs recorded.</p>']
    body += ['<h2>Limitations</h2><ul>']
    body += [f'<li>{esc(item)}</li>' for item in report.get('limitations') or []]
    body.append('</ul>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<title>{esc(report["title"])}</title><style>'
        'body{background:#f5f3eb;color:#354650;font:13px/1.5 -apple-system,'
        'BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;margin:24px;max-width:980px}'
        'h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:22px 0 8px;'
        'color:#536b79;border-bottom:1px solid #b6bcb8;padding-bottom:3px}'
        'table{border-collapse:collapse;width:100%;font-size:12px;'
        'font-variant-numeric:tabular-nums}'
        'th,td{text-align:left;padding:5px 7px;border-bottom:1px solid #b6bcb8}'
        'th{background:#e1e3de;color:#59656a}.meta{color:#59656a;font-size:12px}'
        'li{margin:3px 0}'
        '</style></head><body>' + ''.join(body) + '</body></html>\n')

COLLECTION_EXTENSIONS = {'markdown': '.md', 'json': '.json'}

COLLECTION_LIMITATIONS = (
    'This manifest references records held locally. It is not a copy of their contents.',
    'Email identifiers are SHA-256 content hashes; catalog identifiers are record ids of the '
    'imported export.',
    'Content hashes detect changed bytes. They are not proof of authenticity, legal '
    'admissibility or chain of custody.',
    'Items marked missing were not found when the manifest was generated and are not silently '
    'dropped.',
)

def build_collection_manifest(collection):
    items = []
    for item in collection.get('items', []):
        items.append({key: item.get(key) for key in (
            'item_type', 'item_id', 'kind', 'title', 'actor', 'date',
            'note', 'added_at', 'exists')})
    return {
        'title': f"Evidence manifest: {collection.get('name', 'collection')}",
        'generated_at': _now(),
        'workspace': collection.get('workspace', ''),
        'description': collection.get('description', ''),
        'item_count': collection.get('item_count', len(items)),
        'items': items,
        'limitations': list(COLLECTION_LIMITATIONS),
    }

def render_collection_markdown(manifest):
    lines = [f"# {manifest['title']}", '',
             f"Generated: {manifest['generated_at']}", '',
             f"Workspace: {_value(manifest.get('workspace'))}", '',
             f"Items: {manifest.get('item_count', 0)}", '']
    if manifest.get('description'):
        lines += [manifest['description'], '']
    lines += _markdown_table(
        ('Type', 'Identifier', 'Title', 'Actor', 'Date', 'Note'),
        [(item.get('item_type'), item.get('item_id') + ('' if item.get('exists') else ' (missing)'),
          item.get('title'), item.get('actor'), item.get('date'), item.get('note'))
         for item in manifest.get('items', [])]) + ['']
    lines += ['## Limitations', '']
    lines += [f"- {item}" for item in manifest.get('limitations', [])]
    return '\n'.join(lines).rstrip() + '\n'

def render_collection(manifest, fmt):
    if fmt == 'markdown':
        return render_collection_markdown(manifest)
    if fmt == 'json':
        return json.dumps(manifest, indent=2, ensure_ascii=False) + '\n'
    raise ValueError(f'Unsupported manifest format {fmt!r}')

def write_collection_manifest(manifest, fmt, destination):
    """Write a manifest, refusing to replace an existing file."""
    text = render_collection(manifest, fmt)
    path = Path(destination)
    if path.suffix.lower() != COLLECTION_EXTENSIONS[fmt]:
        raise ValueError(f'{fmt} manifests use the {COLLECTION_EXTENSIONS[fmt]} extension')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                   'w', encoding='utf-8') as handle:
        handle.write(text)
    return {'path': str(path), 'format': fmt, 'bytes': len(text.encode('utf-8'))}

RENDERERS = {'markdown': render_markdown,
             'json': lambda report: json.dumps(report, indent=2, ensure_ascii=False) + '\n',
             'html': render_html}

def render(report, fmt):
    try:
        renderer = RENDERERS[fmt]
    except KeyError:
        raise ValueError(f'Unsupported report format {fmt!r}') from None
    return renderer(report)

def write_report(report, fmt, destination):
    """Write a rendered report, refusing to replace an existing file."""
    text = render(report, fmt)
    path = Path(destination)
    if path.suffix.lower() != EXTENSIONS[fmt]:
        raise ValueError(f'{fmt} reports use the {EXTENSIONS[fmt]} extension')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                   'w', encoding='utf-8') as handle:
        handle.write(text)
    return {'path': str(path), 'format': fmt, 'bytes': len(text.encode('utf-8'))}
