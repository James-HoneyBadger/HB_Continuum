# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Honey Badger Universe
import unittest
from unittest import mock
import local_ai

class Tests(unittest.TestCase):
    def test_requires_question_and_selection(self):
        self.assertRaises(ValueError,local_ai.analyze,'',[{'subject':'s'}])
        self.assertRaises(ValueError,local_ai.analyze,'summarize',[])
    def test_oversize_selection_rejected_before_network(self):
        messages=[{'body':'x'*local_ai.MAX_CHARS}]
        with mock.patch('urllib.request.OpenerDirector.open') as opened:
            self.assertRaises(ValueError,local_ai.analyze,'summarize',messages)
        opened.assert_not_called()
    def test_uses_loopback_only(self):
        self.assertTrue(local_ai.URL.startswith('http://127.0.0.1:'))
    def test_empty_answer_is_an_error(self):
        response=mock.MagicMock()
        response.__enter__.return_value=response
        response.read.return_value=b'{"message":{"content":"  "}}'
        with mock.patch('urllib.request.OpenerDirector.open',return_value=response):
            with mock.patch('json.load',return_value={'message':{'content':' '}}):
                self.assertRaises(ValueError,local_ai.analyze,'summarize',[{'subject':'s','body':'b'}])
if __name__=='__main__': unittest.main()
