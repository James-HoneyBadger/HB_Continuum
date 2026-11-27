# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
import io, json, os, sqlite3, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock
from dispatch import Archive
from ipc import IPCServer, PROTOCOL_VERSION
from preferences import save as save_prefs

def request(method, request_id='1', **params):
    return {'protocol_version': PROTOCOL_VERSION, 'request_id': request_id,
            'method': method, 'params': params}

class IPCServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.a=Archive(self.root)
        self.h=self.a.ingest(b'From: a@example.invalid\r\nSubject: Silver invoice\r\n'
                             b'Message-ID: <test@example.invalid>\r\n\r\nBullion receipt')
        self.server=IPCServer(self.root, out=io.StringIO())
    def tearDown(self):
        self.a.db.close(); self.tmp.cleanup()

    def test_ping(self):
        resp=self.server.handle(request('ping'))
        self.assertEqual(resp['result']['pong'],True)

    def test_stats(self):
        resp=self.server.handle(request('stats'))
        self.assertEqual(resp['result']['archive']['messages'],1)
        self.assertIn('records',resp['result']['catalog'])

    def test_search_pagination(self):
        self.a.ingest(b'From: b@example.invalid\r\nSubject: Another bullion\r\n\r\nMore bullion here')
        resp=self.server.handle(request('search',query='bullion',page=1,page_size=1))
        result=resp['result']
        self.assertEqual(len(result['items']),1)
        self.assertTrue(result['has_more'])
        self.assertEqual(result['total'],2)
        page2=self.server.handle(request('search',query='bullion',page=2,page_size=1))
        self.assertFalse(page2['result']['has_more'])

    def test_unknown_method(self):
        resp=self.server.handle(request('nope'))
        self.assertEqual(resp['error']['code'],'UNKNOWN_METHOD')

    def test_invalid_params(self):
        resp=self.server.handle(request('search',query=''))
        self.assertEqual(resp['error']['code'],'INVALID_PARAMS')

    def test_unsupported_version(self):
        req=request('ping'); req['protocol_version']=999
        self.assertEqual(self.server.handle(req)['error']['code'],'UNSUPPORTED_VERSION')

    def test_archive_not_available(self):
        server=IPCServer(self.root/'missing', out=io.StringIO())
        resp=server.handle(request('stats'))
        self.assertEqual(resp['error']['code'],'ARCHIVE_NOT_AVAILABLE')

    def test_message(self):
        resp=self.server.handle(request('message',hash=self.h))
        self.assertEqual(resp['result']['subject'],'Silver invoice')
        self.assertIn('Bullion receipt',resp['result']['body'])
        self.assertEqual(self.server.handle(request('message',hash='0'*64))['error']['code'],'NOT_FOUND')

    def test_message_includes_attachment_metadata(self):
        from email.message import EmailMessage
        m=EmailMessage(); m['Subject']='Receipt'; m.set_content('body')
        m.add_attachment(b'attachedtext',maintype='text',subtype='plain',filename='note.txt')
        h=self.a.ingest(m.as_bytes())
        resp=self.server.handle(request('message',hash=h))
        self.assertEqual([(a['filename'],a['mime']) for a in resp['result']['attachments']],
                         [('note.txt','text/plain')])
        self.assertEqual(resp['result']['attachments'][0]['characters'],len('attachedtext'))

    def test_message_tolerates_archive_without_attachment_index(self):
        with self.a.db: self.a.db.execute('DROP TABLE attachment_index')
        resp=self.server.handle(request('message',hash=self.h))
        self.assertEqual(resp['result']['attachments'],[])

    def test_thread(self):
        reply=self.a.ingest(b'From: b@example.invalid\r\nSubject: Re: invoice\r\n'
                            b'Message-ID: <reply@example.invalid>\r\nIn-Reply-To: <test@example.invalid>\r\n\r\nReply.\r\n')
        resp=self.server.handle(request('thread',hash=reply))
        self.assertEqual({m['hash'] for m in resp['result']['messages']},{self.h,reply})

    def test_record(self):
        from facebook import import_files
        from catalog import Catalog
        posts=self.root/'posts.json'
        posts.write_text(json.dumps({'your_posts':[
            {'timestamp': 1700000000, 'data': [{'post': 'Hello world'}]},
        ]}))
        import_files([str(posts)], self.root)
        catalog=Catalog(self.root)
        try:
            rid=catalog.db.execute('SELECT record_id FROM records').fetchone()[0]
        finally:
            catalog.close()
        resp=self.server.handle(request('record',record_id=rid))
        self.assertEqual(resp['result']['record_kind'],'post')
        self.assertIn('Hello world',resp['result']['body'])

    def test_verify(self):
        resp=self.server.handle(request('verify'))
        self.assertEqual(resp['result']['checked'],1)
        self.assertEqual(resp['result']['bad'],[])
        (self.root/'raw'/(self.h+'.eml')).write_bytes(b'changed')
        self.assertEqual(self.server.handle(request('verify'))['result']['bad'],[self.h])

    def test_import_eml(self):
        inbox=self.root/'inbox'
        inbox.mkdir()
        (inbox/'one.eml').write_bytes(b'From: c@example.invalid\r\nSubject: Imported\r\n\r\nHello import')
        resp=self.server.handle(request('import_eml',paths=[str(inbox)]))
        first=self.finish_job(resp['result']['job_id'])
        self.assertEqual(first['event'],'job_complete')
        self.assertEqual(first['result']['imported'],1)
        self.assertEqual(len(first['result']['hashes']),1)
        resp=self.server.handle(request('import_eml',paths=[str(inbox)]))
        second=self.finish_job(resp['result']['job_id'])
        self.assertEqual(second['result']['imported'],0)
        self.assertEqual(second['result']['existing'],1)
        self.assertEqual(self.server.handle(request('import_eml',paths='not-a-list'))['error']['code'],'INVALID_PARAMS')

    def test_import_history_records_real_runs(self):
        inbox=self.root/'inbox'; inbox.mkdir()
        (inbox/'one.eml').write_bytes(b'From: c@example.invalid\r\nSubject: History\r\n\r\nbody')
        resp=self.server.handle(request('import_eml',paths=[str(inbox)]))
        self.finish_job(resp['result']['job_id'])
        history=self.server.handle(request('import_history'))['result']
        self.assertTrue(history['available'])
        run=history['runs'][0]
        self.assertEqual(run['source'],'eml')
        self.assertEqual(run['status'],'ok')
        self.assertEqual(run['records_new'],1)
        self.assertEqual(run['records_failed'],0)
        self.assertIsNotNone(run['finished_at'])
        self.assertEqual(self.server.handle(request('import_history',limit=0))['error']['code'],'INVALID_PARAMS')

    def test_source_settings_and_removal_over_ipc(self):
        with self.a.db:
            self.a.db.execute('INSERT INTO origins VALUES(?,?,?,?,?)',
                              ('imap.example|me','INBOX','1','1',self.h))
        disabled=self.server.handle(request(
            'source_set_enabled',source='email',source_key='imap.example|me',
            enabled=False,note='paused'))['result']
        self.assertFalse(disabled['enabled'])
        account=self.server.handle(request('sources'))['result']['email_accounts'][0]
        self.assertTrue(account['disabled'])
        self.assertEqual(account['note'],'paused')
        events=self.server.handle(request('source_events'))['result']['events']
        self.assertEqual(events[0]['action'],'disabled')
        preview=self.server.handle(request(
            'source_removal_preview',source='email',source_key='imap.example|me'))['result']
        self.assertEqual(preview['records_removed'],1)
        unconfirmed=self.server.handle(request(
            'source_remove',source='email',source_key='imap.example|me'))
        self.assertEqual(unconfirmed['error']['code'],'CONFIRMATION_REQUIRED')
        removed=self.server.handle(request(
            'source_remove',source='email',source_key='imap.example|me',confirm=True))['result']
        self.assertTrue(removed['removed'])
        self.assertEqual(self.server.handle(request('sources'))['result']['email_accounts'],[])
        self.assertEqual(self.server.handle(request('message',hash=self.h))['error']['code'],'NOT_FOUND')
        self.assertEqual(self.server.handle(request(
            'source_set_enabled',source='email',source_key='x',enabled='yes'))['error']['code'],
            'INVALID_PARAMS')

    def test_source_verify_job_is_scoped_to_an_account(self):
        with self.a.db:
            self.a.db.execute('INSERT INTO origins VALUES(?,?,?,?,?)',
                              ('imap.example|me','INBOX','1','1',self.h))
        started=self.server.handle(request(
            'source_verify',source='email',source_key='imap.example|me'))
        terminal=self.finish_job(started['result']['job_id'])
        self.assertEqual(terminal['event'],'job_complete')
        self.assertEqual((terminal['result']['checked'],terminal['result']['ok']),(1,1))
        bad=self.server.handle(request('source_verify',source='email',source_key=''))
        self.assertEqual(bad['error']['code'],'INVALID_PARAMS')

    def test_sources_reports_accounts_and_footprint(self):
        with self.a.db:
            self.a.db.execute('INSERT INTO origins VALUES(?,?,?,?,?)',
                              ('imap.example|me','INBOX','1','1',self.h))
        sources=self.server.handle(request('sources'))['result']
        account=sources['email_accounts'][0]
        self.assertEqual(account['account'],'imap.example|me')
        self.assertEqual(account['messages'],1)
        self.assertEqual(account['origins'],1)
        self.assertEqual(account['folders'],1)
        self.assertGreater(sources['storage']['total_bytes'],0)
        self.assertEqual(sources['catalog']['records'],0)

    def test_archive_report_job_writes_outside_the_archive(self):
        import shutil
        outside=tempfile.mkdtemp()
        try:
            destination=Path(outside)/'report.md'
            started=self.server.handle(request(
                'report_archive',destination=str(destination),format='markdown'))
            terminal=self.finish_job(started['result']['job_id'])
            self.assertEqual(terminal['event'],'job_complete')
            self.assertEqual(terminal['result']['format'],'markdown')
            text=destination.read_text()
            self.assertIn('# HB Continuum archive report',text)
            self.assertIn('## Limitations',text)
            again=self.server.handle(request(
                'report_archive',destination=str(destination),format='markdown'))
            self.assertEqual(again['error']['code'],'DESTINATION_EXISTS')
            inside=self.server.handle(request(
                'report_archive',destination=str(self.root/'report.md')))
            self.assertEqual(inside['error']['code'],'INVALID_PARAMS')
            bad=self.server.handle(request(
                'report_archive',destination=str(Path(outside)/'r.pdf'),format='pdf'))
            self.assertEqual(bad['error']['code'],'INVALID_PARAMS')
            wrong_ext=self.server.handle(request(
                'report_archive',destination=str(Path(outside)/'r.md'),format='json'))
            self.assertEqual(wrong_ext['error']['code'],'INVALID_PARAMS')
            missing=self.server.handle(request(
                'report_archive',destination=str(Path(outside)/'nope'/'r.md')))
            self.assertEqual(missing['error']['code'],'INVALID_PARAMS')
        finally:
            shutil.rmtree(outside,ignore_errors=True)

    def test_journal_round_trip_and_revision_history(self):
        created=self.server.handle(request(
            'journal_save',title='Remembered',body='first text',event_date='2015-06-01'))['result']
        self.assertEqual(created['revision'],1)
        updated=self.server.handle(request(
            'journal_save',entry_id=created['id'],title='Remembered',body='revised text',
            event_date='2015-06-01'))['result']
        self.assertEqual(updated['revision'],2)
        self.assertEqual([r['revision'] for r in updated['revisions']],[2,1])
        listed=self.server.handle(request('journal_list'))['result']['entries']
        self.assertEqual([row['id'] for row in listed],[created['id']])
        self.assertEqual(self.server.handle(request('journal_get',entry_id=created['id']))['result']['body'],
                         'revised text')
        deleted=self.server.handle(request('journal_delete',entry_id=created['id']))['result']
        self.assertIsNotNone(deleted['deleted_at'])
        self.assertEqual(self.server.handle(request('journal_list'))['result']['entries'],[])
        self.assertEqual(len(self.server.handle(
            request('journal_list',include_deleted=True))['result']['entries']),1)
        self.assertEqual(self.server.handle(request('journal_save',title=''))['error']['code'],
                         'INVALID_PARAMS')
        self.assertEqual(self.server.handle(request('journal_get',entry_id='x'))['error']['code'],
                         'INVALID_PARAMS')

    def test_preferences_get_set(self):
        resp=self.server.handle(request('preferences'))
        self.assertIn('values',resp['result'])
        self.assertTrue(resp['result']['fields'])
        self.assertFalse(resp['result']['values']['ai_enabled'])
        resp=self.server.handle(request('preferences_set',values={'theme':'Dark'}))
        self.assertEqual(resp['result']['values']['theme'],'Dark')
        self.assertTrue((self.root/'preferences.json').is_file())

    def test_research_list_and_results(self):
        from research import Research
        research=Research(self.a)
        try:
            research.save_search('General','Invoices','invoice')
        finally:
            research.close()
        resp=self.server.handle(request('research_list',table='searches'))
        self.assertTrue(any(row[0]=='General' and row[1]=='Invoices' for row in resp['result']['rows']))
        resp=self.server.handle(request('research_results',workspace='General',name='Invoices'))
        self.assertEqual(resp['result']['count'],1)
        self.assertEqual(resp['result']['results'][0]['hash'],self.h)
        self.assertEqual(self.server.handle(request('research_list',table='evil'))['error']['code'],'INVALID_PARAMS')

    def test_research_workspace_and_search_save(self):
        resp=self.server.handle(request('research_workspace_save',workspace='Metals',description='Bullion'))
        self.assertEqual(resp['result']['workspace'],'Metals')
        resp=self.server.handle(request('research_search_save',workspace='Metals',name='Silver',query='silver',limit=10))
        self.assertEqual(resp['result']['name'],'Silver')
        listed=self.server.handle(request('research_list',table='searches'))['result']['rows']
        self.assertTrue(any(r[0]=='Metals' and r[1]=='Silver' and r[4]==10 for r in listed))
        self.assertEqual(self.server.handle(request('research_search_save',workspace='Nope',name='x'))['error']['code'],'NOT_FOUND')
        self.assertEqual(self.server.handle(request('research_search_save',workspace='Metals',name='x',limit='10'))['error']['code'],'INVALID_PARAMS')

    def test_research_tags_and_rules(self):
        resp=self.server.handle(request('research_tag',hashes=[self.h],tag='invoice'))
        self.assertEqual(resp['result']['tag'],'invoice')
        rows=self.server.handle(request('research_list',table='tags'))['result']['rows']
        self.assertTrue(any(r[0]==self.h and r[1]=='invoice' and r[2]=='manual' for r in rows))
        self.server.handle(request('research_untag',hashes=[self.h],tag='invoice'))
        rows=self.server.handle(request('research_list',table='tags'))['result']['rows']
        self.assertFalse(any(r[1]=='invoice' for r in rows))
        self.assertEqual(self.server.handle(request('research_tag',hashes=['bad'],tag='x'))['error']['code'],'INVALID_PARAMS')
        self.assertEqual(self.server.handle(request('research_tag',hashes=['0'*64],tag='x'))['error']['code'],'INVALID_PARAMS')

    def test_research_fields_and_metadata(self):
        self.server.handle(request('research_field_define',name='State',kind='text'))
        resp=self.server.handle(request('research_metadata_set',hash=self.h,field='State',value='Open'))
        self.assertEqual(resp['result']['value'],'Open')
        rows=self.server.handle(request('research_list',table='fields'))['result']['rows']
        self.assertTrue(any(r[0]=='State' for r in rows))
        self.assertEqual(self.server.handle(request('research_metadata_set',hash=self.h,field='Missing',value='x'))['error']['code'],'INVALID_PARAMS')

    def test_research_reports(self):
        from research import Research
        research=Research(self.a)
        try:
            research.save_search('General','all','')
        finally:
            research.close()
        resp=self.server.handle(request('research_report_save',name='cols',workspace='General',search='all',columns=['subject','hash']))
        self.assertEqual(resp['result']['name'],'cols')
        preview=self.server.handle(request('research_report_preview',name='cols'))['result']
        self.assertEqual(preview['columns'],['subject','hash'])
        self.assertEqual(len(preview['rows']),1)
        target=self.root/'report.csv'
        exported=self.server.handle(request('research_report_export',name='cols',path=str(target)))
        self.assertTrue(target.is_file())
        self.assertEqual(exported['result']['path'],str(target))
        again=self.server.handle(request('research_report_export',name='cols',path=str(target)))
        self.assertEqual(again['error']['code'],'INTERNAL_ERROR')

    def test_export_evidence(self):
        dest=self.root/'evidence-1'
        resp=self.server.handle(request('export_evidence',hashes=[self.h],destination=str(dest)))
        self.assertEqual(resp['result']['messages'],1)
        self.assertTrue((dest/(self.h+'.eml')).is_file())
        self.assertTrue((dest/'manifest.json').is_file())

    def test_schedule_status_and_profile(self):
        resp=self.server.handle(request('schedule_status'))
        self.assertEqual(resp['result']['profiles'],{})
        saved=self.server.handle(request('schedule_profile_save',name='mail',host='imap.example.invalid',
                                         user='u@example.invalid',folders=['INBOX'],minutes=30,enabled=False))
        self.assertEqual(saved['result']['profile']['name'],'mail')
        self.assertEqual(self.server.handle(request('schedule_profile_enabled',name='mail',enabled=True))['result']['enabled'],True)
        self.assertEqual(self.server.handle(request('schedule_profile_enabled',name='nope',enabled=True))['error']['code'],'NOT_FOUND')
        resp=self.server.handle(request('schedule_status'))
        self.assertIn('mail',resp['result']['profiles'])
        self.assertNotIn('password',json.dumps(resp['result']).lower())

    def test_schedule_run_job_reports_error(self):
        self.server.handle(request('schedule_profile_save',name='mail',host='imap.example.invalid',
                                   user='u@example.invalid',folders=['INBOX'],minutes=30,enabled=True))
        resp=self.server.handle(request('schedule_run',name='mail'))
        job_id=resp['result']['job_id']
        deadline=time.time()+5
        while time.time()<deadline and not self.server._jobs[job_id].get('done'):
            time.sleep(0.01)
        self.assertTrue(self.server._jobs[job_id].get('done'))
        lines=[json.loads(x) for x in self.server.out.getvalue().splitlines()]
        terminal=[x for x in lines if x.get('event') in ('job_complete','job_error')]
        self.assertEqual(len(terminal),1)
        self.assertEqual(self.server.handle(request('schedule_run',name='nope'))['error']['code'],'NOT_FOUND')

    def test_summarize_disabled(self):
        resp=self.server.handle(request('summarize',hashes=[self.h]))
        self.assertEqual(resp['error']['code'],'AI_DISABLED')

    def test_summarize_job_progress_and_cancel(self):
        save_prefs(self.root, {'ai_enabled': True, 'ai_backend': 'ollama',
                               'ai_endpoint': 'http://127.0.0.1:1'})
        def fake_batch(self, hashes, summary_type='message', model=None, prompt_version=None,
                       force=False, progress=None, cancel_event=None):
            for i, digest in enumerate(hashes):
                if progress:
                    progress(i + 1, len(hashes), digest, 'summarized')
            return {'total': len(hashes), 'summarized': len(hashes), 'regenerated': 0,
                    'skipped': 0, 'cancelled': 0}
        with mock.patch('summarize.Summarizer.summarize_batch', fake_batch):
            resp=self.server.handle(request('summarize',hashes=[self.h]))
            job_id=resp['result']['job_id']
            deadline=time.time()+3
            while time.time()<deadline and not self.server._jobs[job_id].get('done'):
                time.sleep(0.01)
            self.assertTrue(self.server._jobs[job_id].get('done'))
        lines=[json.loads(x) for x in self.server.out.getvalue().splitlines()]
        events=[x for x in lines if 'event' in x]
        self.assertTrue(any(e['event']=='progress' for e in events))
        complete=next(e for e in events if e['event']=='job_complete')
        self.assertEqual(complete['result']['summarized'],1)
        # cancellation endpoint resolves for a known job
        self.assertEqual(self.server.handle(request('cancel',job_id=job_id))['result']['status'],'cancelling')
        self.assertEqual(self.server.handle(request('cancel',job_id='missing'))['error']['code'],'UNKNOWN_JOB')

    def finish_job(self, job_id):
        deadline=time.time()+5
        while time.time()<deadline and not self.server._jobs[job_id].get('done'):
            time.sleep(0.01)
        self.assertTrue(self.server._jobs[job_id].get('done'))
        events=[json.loads(x) for x in self.server.out.getvalue().splitlines()]
        return next(e for e in events
                    if e.get('event') in ('job_complete','job_error') and e.get('job_id')==job_id)

    def test_health_reports_clean_archive(self):
        resp=self.server.handle(request('health'))
        self.assertTrue(resp['result']['sqlite_ok'])
        self.assertEqual(resp['result']['messages'],1)
        self.assertEqual(resp['result']['index_missing'],[])
        self.assertEqual(resp['result']['raw_invalid'],[])
        self.assertEqual(self.server.handle(request('message',hash='0'*64))['error']['code'],'NOT_FOUND')

    def test_health_reports_missing_index_row(self):
        with self.a.db: self.a.db.execute('DELETE FROM search WHERE hash=?',(self.h,))
        resp=self.server.handle(request('health'))
        self.assertEqual(resp['result']['index_missing'],[self.h])

    def test_health_never_migrates_a_legacy_archive(self):
        from migrations import MIGRATIONS, current_version
        legacy=self.root/'legacy'
        legacy.mkdir()
        db=sqlite3.connect(legacy/'archive.sqlite3')
        try:
            for statement in MIGRATIONS['archive'][1]:
                db.execute(statement)
            db.execute('PRAGMA user_version=1')
            db.commit()
        finally:
            db.close()
        server=IPCServer(legacy,out=io.StringIO())
        resp=server.handle(request('health'))
        self.assertEqual(resp['result']['messages'],0)
        db=sqlite3.connect(legacy/'archive.sqlite3')
        try:
            self.assertEqual(current_version(db),1)
        finally:
            db.close()

    def test_health_requires_an_archive(self):
        server=IPCServer(self.root/'missing', out=io.StringIO())
        self.assertEqual(server.handle(request('health'))['error']['code'],'ARCHIVE_NOT_AVAILABLE')

    def test_health_defers_while_archive_is_busy(self):
        from sync_lock import LOCK_SUPPORTED, sync_lock
        if not LOCK_SUPPORTED: self.skipTest('archive locking is unsupported here')
        with sync_lock(self.root):
            self.assertEqual(self.server.handle(request('health'))['error']['code'],'ARCHIVE_BUSY')

    def test_reindex_job_repairs_missing_index_row(self):
        with self.a.db: self.a.db.execute('DELETE FROM search WHERE hash=?',(self.h,))
        resp=self.server.handle(request('reindex'))
        terminal=self.finish_job(resp['result']['job_id'])
        self.assertEqual(terminal['event'],'job_complete')
        self.assertEqual(terminal['result'],{'action':'reindex','reindexed':1,'cancelled':False})
        self.assertEqual(self.server.handle(request('health'))['result']['index_missing'],[])

    def test_recover_orphans_job_reports_recovered_hashes(self):
        import hashlib
        raw=b'From: orphan@example.invalid\r\nSubject: Orphan\r\n\r\nrecovered body'
        orphan=hashlib.sha256(raw).hexdigest()
        (self.root/'raw'/(orphan+'.eml')).write_bytes(raw)
        resp=self.server.handle(request('recover_orphans'))
        terminal=self.finish_job(resp['result']['job_id'])
        self.assertEqual(terminal['event'],'job_complete')
        self.assertEqual(terminal['result']['recovered'],[orphan])
        self.assertFalse(terminal['result']['cancelled'])
        self.assertEqual(self.server.handle(request('health'))['result']['raw_unindexed'],[])

    def test_migrate_status_reports_versions(self):
        report=self.server.handle(request('migrate_status'))['result']
        self.assertTrue(report['archive']['present'])
        self.assertEqual(report['archive']['version'],report['archive']['target'])
        self.assertEqual(report['archive']['pending'],[])
        self.assertFalse(report['research']['present'])

    def test_backup_verify_and_restore_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); snapshot=base/'snapshot'; restored=base/'restored'
            started=self.server.handle(request('backup',destination=str(snapshot)))
            terminal=self.finish_job(started['result']['job_id'])
            self.assertEqual(terminal['event'],'job_complete')
            self.assertEqual(terminal['result']['verified'],True)
            self.assertTrue((snapshot/'backup-manifest.json').is_file())
            started=self.server.handle(request('verify_backup',snapshot=str(snapshot)))
            self.assertEqual(self.finish_job(started['result']['job_id'])['result']['verified'],True)
            started=self.server.handle(request('restore',snapshot=str(snapshot),destination=str(restored)))
            terminal=self.finish_job(started['result']['job_id'])
            self.assertEqual(terminal['event'],'job_complete')
            self.assertTrue((restored/'archive.sqlite3').is_file())
            self.assertFalse((restored/'backup-manifest.json').exists())

    def test_verify_backup_job_reports_tampering(self):
        from backup import backup
        with tempfile.TemporaryDirectory() as tmp:
            snapshot=Path(tmp)/'snapshot'
            backup(self.root, snapshot)
            next((snapshot/'raw').glob('*.eml')).write_bytes(b'changed')
            started=self.server.handle(request('verify_backup',snapshot=str(snapshot)))
            terminal=self.finish_job(started['result']['job_id'])
            self.assertEqual(terminal['event'],'job_error')
            self.assertEqual(terminal['code'],'BACKUP_INVALID')

    def test_backup_job_reports_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination=Path(tmp)/'snapshot'
            destination.mkdir()
            started=self.server.handle(request('backup',destination=str(destination)))
            terminal=self.finish_job(started['result']['job_id'])
            self.assertEqual(terminal['event'],'job_error')
            self.assertEqual(terminal['code'],'BACKUP_FAILED')

    def test_backup_actions_require_paths(self):
        self.assertEqual(self.server.handle(request('backup'))['error']['code'],'INVALID_PARAMS')
        self.assertEqual(self.server.handle(request('verify_backup'))['error']['code'],'INVALID_PARAMS')
        self.assertEqual(self.server.handle(request('restore',snapshot='x'))['error']['code'],'INVALID_PARAMS')
        self.assertEqual(self.server.handle(request('restore',snapshot='x',destination='y'))['result']['status'],'started')

    def test_facebook_preview_and_import_job(self):
        export=self.root/'posts.json'
        export.write_text(json.dumps({'your_posts':[
            {'timestamp':1700000000,'data':[{'post':'Bullion note'}]},
        ]}))
        preview=self.server.handle(request('facebook_preview',paths=[str(export)]))['result']
        self.assertEqual(preview['files_discovered'],1)
        self.assertEqual(preview['supported_records'],1)
        started=self.server.handle(request('facebook_import',paths=[str(export)]))
        terminal=self.finish_job(started['result']['job_id'])
        self.assertEqual(terminal['event'],'job_complete')
        self.assertEqual(terminal['result']['records_imported'],1)
        self.assertFalse(terminal['result']['cancelled'])
        history=self.server.handle(request('import_history'))['result']['runs']
        self.assertEqual(history[0]['source'],'facebook')
        self.assertEqual(history[0]['status'],'ok')
        self.assertEqual(history[0]['records_new'],1)
        again=self.server.handle(request('facebook_import',paths=[str(export)]))
        self.assertEqual(self.finish_job(again['result']['job_id'])['result']['files_skipped'],1)
        self.assertEqual(self.server.handle(request('facebook_preview'))['error']['code'],'INVALID_PARAMS')
        self.assertEqual(self.server.handle(request('facebook_import',paths=[]))['error']['code'],'INVALID_PARAMS')

    def test_timeline_and_correspondents(self):
        self.a.ingest(b'From: c@example.invalid\r\nSubject: Earlier\r\nDate: Thu, 26 Nov 2026 09:00:00 +0000\r\n\r\none')
        self.a.ingest(b'From: c@example.invalid\r\nSubject: Later\r\nDate: Thu, 26 Nov 2026 11:00:00 +0000\r\n\r\nthree')
        self.a.ingest(b'From: d@example.invalid\r\nSubject: Undated\r\n\r\nnone')
        rows=self.server.handle(request('timeline',limit=10))['result']
        subjects=[r['subject'] for r in rows]
        self.assertEqual(subjects[:2],['Earlier','Later'])
        self.assertGreater(subjects.index('Undated'),subjects.index('Later'))
        filtered=self.server.handle(request('timeline',sender='c@example.invalid'))['result']
        self.assertEqual({r['sender'] for r in filtered},{'c@example.invalid'})
        self.assertEqual(len(filtered),2)
        counts={c['sender']:c['count'] for c in self.server.handle(request('correspondents'))['result']}
        self.assertEqual(counts['c@example.invalid'],2)
        self.assertEqual(counts['a@example.invalid'],1)
        self.assertEqual(self.server.handle(request('timeline',limit=0))['error']['code'],'INVALID_PARAMS')
        self.assertEqual(self.server.handle(request('timeline',sender=5))['error']['code'],'INVALID_PARAMS')
        self.assertEqual(self.server.handle(request('correspondents',limit=0))['error']['code'],'INVALID_PARAMS')

    def test_timeline_pagination_and_reverse_order(self):
        for hour in range(1,5):
            self.a.ingest(f'From: t@example.invalid\r\nSubject: H{hour}\r\n'
                          f'Date: Thu, 26 Nov 2026 0{hour}:00:00 +0000\r\n\r\nx'.encode())
        first=self.server.handle(request('timeline',limit=2))['result']
        second=self.server.handle(request('timeline',limit=2,offset=2))['result']
        self.assertEqual([r['subject'] for r in first],['H1','H2'])
        self.assertEqual([r['subject'] for r in second],['H3','H4'])
        reverse=self.server.handle(request('timeline',limit=2,order='desc'))['result']
        self.assertEqual([r['subject'] for r in reverse],['H4','H3'])
        self.assertEqual(self.server.handle(request('timeline',order='sideways'))['error']['code'],'INVALID_PARAMS')
        self.assertEqual(self.server.handle(request('timeline',offset=-1))['error']['code'],'INVALID_PARAMS')

    def test_storage_footprint_prefers_recorded_sizes(self):
        import ipc as ipc_module
        expected=(self.root/'raw'/(self.h+'.eml')).stat().st_size
        with mock.patch.object(Path,'iterdir',side_effect=AssertionError('scanned raw directory')):
            footprint=ipc_module._storage_footprint(self.root)
        self.assertEqual(footprint['raw_bytes'],expected)

    def test_dashboard_reports_coverage_and_storage(self):
        self.a.ingest(b'Date: Thu, 26 Nov 2026 09:00:00 +0000\r\n\r\ndated')
        result=self.server.handle(request('dashboard'))['result']
        self.assertEqual(result['archive']['messages'],2)
        self.assertEqual(result['archive']['latest'],'2026-11-26')
        self.assertEqual(result['archive']['undated'],1)
        self.assertEqual(result['by_year'],[{'year':2026,'count':1}])
        self.assertGreater(result['storage']['total_bytes'],0)

    def test_serve_subprocess(self):
        proc=subprocess.Popen(
            [sys.executable, 'dispatch.py', '--archive', str(self.root), 'serve'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        messages=(json.dumps(request('ping'))+'\n'
                  + json.dumps(request('stats'))+'\n'
                  + json.dumps(request('shutdown'))+'\n')
        out,_=proc.communicate(messages, timeout=10)
        self.assertEqual(proc.returncode,0)
        lines=[json.loads(x) for x in out.splitlines()]
        self.assertEqual(lines[0]['result']['pong'],True)
        self.assertIn('archive',lines[1]['result'])

if __name__=='__main__':
    unittest.main()
