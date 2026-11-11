import queue
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from main import Worker, find_browser


class BrowserSelectionTests(unittest.TestCase):
    def test_find_edge_from_common_path(self):
        with patch('main.sys.platform', 'win32'), patch.dict('main.os.environ', {'PROGRAMFILES': 'C:/Apps'}, clear=True), \
                patch.object(Path, 'is_file', autospec=True, side_effect=lambda p: str(p).endswith('msedge.exe')), \
                patch('main.shutil.which', return_value=None):
            self.assertTrue(find_browser('edge').endswith('msedge.exe'))
            self.assertIsNone(find_browser('chrome'))

    def test_auto_detect_reports_missing(self):
        with patch('main.sys.platform', 'win32'), patch.dict('main.os.environ', {}, clear=True), \
                patch('main.shutil.which', return_value=None):
            self.assertIsNone(find_browser('chrome'))

    def run_connect(self, path, attach=None):
        events = queue.Queue()
        options = SimpleNamespace(port=9333, profile='profile', attach=attach, browser=None)
        worker = Worker(options, events)
        with patch('main.connect', return_value=(Mock(), Mock())) as connect:
            worker.start()
            worker.request(('connect', path))
            found = []
            while True:
                event = events.get(timeout=3)
                found.append(event)
                if event[0] == 'status':
                    break
            worker.shutdown()
            worker.join(timeout=2)
        return connect, found

    def test_selected_browser_is_passed_to_connect(self):
        browser = Path(__file__).resolve()
        connect, _ = self.run_connect(str(browser))
        connect.assert_called_once_with(9333, 'profile', None, str(browser))

    def test_empty_path_uses_automatic_detection(self):
        connect, _ = self.run_connect('')
        connect.assert_called_once_with(9333, 'profile', None, None)

    def test_missing_file_does_not_launch_browser(self):
        connect, events = self.run_connect('missing-browser.exe')
        connect.assert_not_called()
        self.assertIn('文件不存在', events[-1][1])

    def test_attach_does_not_ignore_selected_path(self):
        browser = Path(__file__).resolve()
        connect, events = self.run_connect(str(browser), '127.0.0.1:9333')
        connect.assert_not_called()
        self.assertIn('不能指定浏览器路径', events[-1][1])


if __name__ == '__main__':
    unittest.main()
