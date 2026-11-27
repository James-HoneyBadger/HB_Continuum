# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
import io, json, subprocess, sys, tempfile, time, unittest
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
