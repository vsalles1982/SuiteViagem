import signal
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from suiteviagem.web.server import Jobs,command

class VirtualTests(unittest.TestCase):
    def test_command_isolated_and_modes(self):
        d=dict(module='hotels',destination='Petrópolis',start='2026-09-13',end='2026-09-14')
        c=command(d,Path('/tmp/test.sqlite3'))
        self.assertEqual(c[:4],['xvfb-run','-a','-s','-screen 0 1920x1080x24 -nolisten tcp'])
        self.assertIn('suiteviagem.hoteis_virtual',c);self.assertIn('--rapido',c)
        self.assertNotIn('--oculto',c)
        d['details_mode']='full';self.assertNotIn('--rapido',command(d,Path('/tmp/test.sqlite3')))
    def test_missing_dependency_does_not_start(self):
        j=Jobs(Path('/tmp/test.sqlite3'))
        with patch('suiteviagem.web.server.shutil.which',return_value=None),patch('suiteviagem.web.server.subprocess.Popen') as popen:
            with self.assertRaisesRegex(ValueError,'Display virtual'):
                j.start(dict(module='hotels',destination='Petrópolis',start='2026-09-13',end='2026-09-14'))
            popen.assert_not_called();self.assertIsNone(j.state())
    def test_cancel_escalates_stuck_worker(self):
        code='import signal,time;signal.signal(signal.SIGINT,signal.SIG_IGN);signal.signal(signal.SIGTERM,signal.SIG_IGN);print("ready",flush=True);time.sleep(60)'
        p=subprocess.Popen([sys.executable,'-u','-c',code],stdout=subprocess.PIPE,text=True,start_new_session=True)
        try:
            self.assertEqual(p.stdout.readline().strip(),'ready')
            Jobs._signal(p,signal.SIGINT)
            Jobs._finish_cancel(p,grace=.05,terminate_grace=.05)
            self.assertEqual(p.returncode,-signal.SIGKILL)
        finally:
            if p.poll() is None:Jobs._signal(p,signal.SIGKILL);p.wait()
            p.stdout.close()
