"""DrissionPage course helper: a paused-by-default desktop app."""
import argparse
import json
import logging
import os
from pathlib import Path
import queue
import shutil
import sys
import threading
import time
import traceback

from controller import Controller
from browser import connect

APP_VERSION = '1.0.0'


def app_directory():
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent


def find_browser(kind):
    if kind not in ('chrome', 'edge'):
        raise ValueError('未知浏览器类型')
    candidates = []
    if sys.platform == 'win32':
        suffix = 'Google/Chrome/Application/chrome.exe' if kind == 'chrome' else 'Microsoft/Edge/Application/msedge.exe'
        for name in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA'):
            base = os.environ.get(name)
            if base:
                candidates.append(Path(base) / suffix)
    elif sys.platform == 'darwin':
        path = ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if kind == 'chrome'
                else '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge')
        candidates.append(Path(path))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    names = ('chrome', 'google-chrome') if kind == 'chrome' else ('msedge', 'microsoft-edge', 'microsoft-edge-stable')
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


class Worker(threading.Thread):
    def __init__(self, options, events):
        super().__init__(daemon=True)
        self.options, self.events = options, events
        self.commands = queue.Queue()
        self.cancel = threading.Event()
        self.closing = threading.Event()
        self.controller = Controller()
        self.browser = self.adapter = None
        self.verification_seen = False
        self.last_refresh = 0.0

    def send(self, kind, value):
        self.events.put((kind, value))

    def request(self, command):
        if command in ('pause', 'connect') or (isinstance(command, tuple) and command[0] == 'connect'):
            self.cancel.set()
        self.commands.put(command)

    def shutdown(self):
        self.closing.set(); self.cancel.set()

    def run(self):
        last_status = None
        while not self.closing.is_set():
            try:
                self.action_taken = False
                command = self.commands.get(timeout=.35)
            except queue.Empty:
                command = None
            try:
                if isinstance(command, tuple) and command[0] == 'connect':
                    _, browser_path = command
                    if browser_path and not Path(browser_path).is_file():
                        raise ValueError('所选浏览器文件不存在，请重新选择')
                    if browser_path and self.options.attach:
                        raise ValueError('接管已有浏览器时不能指定浏览器路径')
                    self.options.browser = browser_path or None
                    command = 'connect'
                if isinstance(command, tuple) and command[0] == 'start':
                    _, limit, include_completed = command
                    self.controller.video_limit = limit
                    self.controller.include_completed = include_completed
                    if limit and self.controller.watched >= limit:
                        self.controller.watched = 0
                    command = 'start'
                if command == 'connect':
                    self.controller.stop('正在连接课程浏览器')
                    self.browser, self.adapter = connect(self.options.port, self.options.profile,
                                                        self.options.attach, self.options.browser)
                    self.send('connected', True)
                    self.verification_seen = False
                    self.controller.stop('已连接。请在新浏览器中登录、进入课程，然后点击启动')
                elif command == 'start':
                    self.cancel.clear()
                    if not self.adapter:
                        raise RuntimeError('请先点击“打开/连接浏览器”')
                    self.verification_seen = False
                    self.controller.start(self.adapter.snapshot())
                elif command == 'pause':
                    self.controller.stop()
                if self.adapter and not self.cancel.is_set():
                    self.handle_state(self.adapter.snapshot())
                if self.controller.status != last_status:
                    last_status = self.controller.status
                    self.send('status', last_status)
                    logging.info(last_status)
                elif self.action_taken:
                    self.send('history', self.controller.status)
                    logging.info(self.controller.status)
            except Exception as exc:
                self.cancel.set()
                self.controller.stop(str(exc))
                self.send('status', str(exc))
                logging.warning('%s: %s', type(exc).__name__, exc)

    def handle_state(self, state):
        if state.get('captcha') and self.controller.running:
            if self.last_refresh and time.monotonic() - self.last_refresh < 60:
                self.controller.stop('验证再次出现，请手动处理后继续')
                return
            self.last_refresh = time.monotonic()
            expected_url = self.controller.url
            self.controller.stop('检测到验证，正在刷新课程页面')
            self.send('status', self.controller.status)
            logging.info(self.controller.status)
            self.adapter.tab.refresh()
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and not self.cancel.is_set() and not self.closing.is_set():
                current = self.adapter.snapshot()
                if current['url'] != expected_url:
                    raise RuntimeError('刷新后课程地址已变化，请检查并手动继续')
                if current.get('captcha'):
                    self.cancel.wait(.5)
                    continue
                if current.get('blocked') or current.get('unknownDialog') or current.get('legacy'):
                    raise RuntimeError('刷新后页面出现阻断提示，请手动检查')
                player = current.get('player')
                if player and not player['error'] and player['ready'] >= 1:
                    self.controller.start(current)
                    self.controller.status = '页面已恢复，继续课程操作'
                    return
                self.cancel.wait(.5)
            self.controller.stop('刷新后验证或播放器未恢复，请手动处理')
            return
        action = self.controller.step(state)
        if action and not self.cancel.is_set():
            self.adapter.perform(action, self.controller.url)
            self.action_taken = True


def run_gui(options):
    from ui import run_gui as launch
    launch(options, Worker, find_browser, APP_VERSION)


def cli():
    parser = argparse.ArgumentParser(description='智慧树 DrissionPage 课程助手')
    parser.add_argument('--port', type=int, default=9333, help='独立课程浏览器的本地端口')
    parser.add_argument('--profile', default=str(app_directory()/'browser-profile'))
    parser.add_argument('--attach', help='仅接管已开启调试端口的本机浏览器，例如127.0.0.1:9333')
    parser.add_argument('--resume', action='store_true', help='连接指定的已有浏览器后恢复操作，仅可与--attach同时使用')
    parser.add_argument('--browser', help='Chrome 或 Edge 可执行文件路径')
    parser.add_argument('--check', action='store_true', help='只检查依赖，不启动浏览器')
    options = parser.parse_args()
    if options.resume and not options.attach:
        parser.error('--resume 只可与 --attach 同时使用')
    if not 1024 <= options.port <= 65535:
        parser.error('端口必须在1024到65535之间')
    if options.check:
        import tkinter
        from importlib.metadata import version
        report = {'app': APP_VERSION, 'DrissionPage': version('DrissionPage'), 'Tk': tkinter.TkVersion, 'snapshot': True}
        (app_directory()/'dependency-check.json').write_text(json.dumps(report), encoding='utf-8')
        if sys.stdout:
            print(report)
        return
    logging.basicConfig(filename=app_directory()/'course-helper.log', encoding='utf-8', level=logging.INFO,
                        format='%(asctime)s %(message)s')
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
        kernel.CreateMutexW.restype = ctypes.c_void_p
        ctypes.set_last_error(0)
        handle = kernel.CreateMutexW(None, False, 'Local\\ZhihuishuDrissionHelper-' + str(options.port))
        if not handle:
            raise RuntimeError('无法创建程序实例锁')
        duplicate = ctypes.get_last_error() == 183
        kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        try:
            if duplicate:
                import tkinter.messagebox
                tkinter.messagebox.showinfo('课程助手已运行', '此端口已有课程助手，请使用已打开的窗口。')
                return
            run_gui(options)
        finally:
            kernel.CloseHandle(handle)
    else:
        run_gui(options)


if __name__ == '__main__':
    try:
        cli()
    except Exception:
        report = app_directory()/'startup-error.log'
        report.write_text(traceback.format_exc(), encoding='utf-8')
        if '--check' in sys.argv:
            sys.exit(1)
        try:
            import tkinter.messagebox
            tkinter.messagebox.showerror('课程助手启动失败', '请查看：' + str(report))
        except Exception:
            raise
