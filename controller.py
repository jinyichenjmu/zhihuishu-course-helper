"""Course decisions independent of DrissionPage; all clicks wait for observed results."""
from dataclasses import dataclass
from urllib.parse import urlsplit
import random
import time


def course_url(url):
    try:
        p = urlsplit(url)
        return p.scheme == 'https' and p.hostname == 'studyvideoh5.zhihuishu.com' and p.path == '/stuStudy' and p.port in (None, 443) and not p.username
    except ValueError:
        return False


def video_finished(player):
    if not player:
        return False
    if player.get('ended'):
        return True
    duration, position = player.get('duration', 0), player.get('time', 0)
    return bool(player.get('paused') and duration > 1 and 0 <= duration - position <= .6)


@dataclass(frozen=True)
class Action:
    kind: str
    index: int = -1
    key: str = ''
    source: str = ''
    allow_complete: bool = False
    source_time: float = 0
    origin_key: str = ''


class Controller:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.running = False
        self.pending = None
        self.status = '已暂停'
        self.url = None
        self.last_time = 0
        self.last_progress = clock()
        self.video_limit = 0
        self.include_completed = False
        self.watched = 0
        self.armed_video = None
        self.target_progress_base = None
        self.video_retries = 0

    def stop(self, message='已暂停'):
        self.running = False
        self.pending = None
        self.status = message

    def start(self, state):
        if not course_url(state.get('url', '')):
            self.stop('请先在浏览器中登录并打开课程视频页')
            return
        self.url = state['url']
        self.pending = None
        self.last_time = 0
        self.last_progress = self.clock()
        self.running = True
        self.status = '已启动'

    def issue(self, action, message):
        self.pending = (action, self.clock())
        self.target_progress_base = None
        self.video_retries = 0
        self.status = message
        return action

    def _complete(self, action, state):
        quiz, player = state.get('quiz'), state.get('player')
        if action.kind in ('option', 'submit', 'next', 'close'):
            if not quiz or quiz['key'] != action.key:
                return True
            if action.kind == 'option':
                return quiz['result'] or any(e['index'] == action.index and e['selected'] for e in quiz['options'])
            if action.kind == 'submit':
                return quiz['result']
            return False
        if action.kind == 'video':
            if not (state.get('current') and state['current']['key'] == action.key and player and player['ready'] >= 1 and not player['ended']):
                self.target_progress_base = None
                return False
            current_time = player.get('time', 0)
            if player.get('src') and player['src'] != action.source:
                return True
            if action.source_time > 1 and current_time < action.source_time - 1:
                return True
            if self.target_progress_base is None:
                self.target_progress_base = current_time
            elif current_time > self.target_progress_base + .5:
                return True
            return False
        if action.kind == 'play':
            return bool(player and (not player['paused'] or player['ended']))
        return False

    def step(self, state):
        now = self.clock()
        if state.get('captcha'):
            self.stop('检测到安全验证，已暂停，请手动处理')
            return
        if not self.running:
            return
        if not course_url(state.get('url', '')) or state['url'] != self.url:
            self.stop('课程页面或登录状态已变化，请检查后重新启动')
            return
        if state.get('blocked'):
            self.stop('网站提示异常脚本，请返回学堂重新进入课程')
            return
        if state.get('unknownDialog') or state.get('legacy'):
            self.stop('出现未知弹窗或另一份助手正在操作，请检查后重新启动')
            return
        if self.pending:
            action, since = self.pending
            # A quiz interrupting the end of a video takes precedence over navigation.
            if action.kind in ('video', 'play') and state.get('quiz'):
                self.pending = None
            elif self._complete(action, state):
                self.pending = None
                self.last_progress = now
                self.last_time = 0
            elif now - since > 30:
                if action.kind == 'video':
                    target = bool(state.get('current') and state['current']['key'] == action.key)
                    self.stop('视频目录已切换，但播放器未确认加载，请手动检查' if target else '视频切换未得到目录确认，请手动检查')
                else:
                    self.stop('操作未得到页面确认，已停止，请手动检查')
                return
            elif action.kind == 'video' and self.video_retries < 2 and now - since >= 8 * (self.video_retries + 1):
                current, player = state.get('current'), state.get('player')
                target = next((v for v in state.get('videos', []) if v['index'] == action.index and v['key'] == action.key), None)
                if (current and current['key'] == action.origin_key and target
                        and (action.allow_complete or not target['complete']) and player
                        and not player.get('error') and video_finished(player)
                        and player.get('src') == action.source):
                    self.video_retries += 1
                    self.status = f'目录尚未切换，正在重试（{self.video_retries}/2）：' + target['title']
                    return action
                return
            else:
                return
        quiz = state.get('quiz')
        if quiz:
            kind = quiz['type']
            if not any(t in kind for t in ('单选题', '判断题', '多选题')) or not quiz['options']:
                self.stop('无法识别此弹题类型或选项，请手动处理')
                return
            multi = '多选题' in kind
            available = [e for e in quiz['options'] if not e['selected']]
            if not quiz['result'] and available and (multi or not any(e['selected'] for e in quiz['options'])):
                option = available[0] if multi else random.choice(available)
                return self.issue(Action('option', option['index'], quiz['key']), '正在勾选多选题选项' if multi else '正在选择弹题选项')
            if multi and not quiz['result'] and quiz.get('submit'):
                if quiz['submit']['disabled']:
                    self.stop('多选题提交按钮不可用，请手动处理')
                    return
                return self.issue(Action('submit', quiz['submit']['index'], quiz['key']), '正在提交多选题')
            if quiz['next']:
                return self.issue(Action('next', key=quiz['key']), '正在打开下一道弹题')
            if quiz['close']:
                return self.issue(Action('close', key=quiz['key']), '正在关闭弹题')
            self.stop('找不到弹题关闭按钮')
            return
        player = state.get('player')
        if not player or player['error']:
            self.stop('课程播放器不存在或加载出错，请检查后重新启动')
            return
        if video_finished(player):
            items = state['videos']
            position = next((i for i, e in enumerate(items) if e['current']), -1)
            if position < 0:
                self.stop('无法识别当前视频')
                return
            current_key = items[position]['key']
            if self.armed_video == current_key:
                self.watched += 1
                self.armed_video = None
                if self.video_limit and self.watched >= self.video_limit:
                    self.stop(f'本轮已看完 {self.watched} 个视频，达到设定数量，已暂停')
                    return
            following = next((e for e in items[position+1:] if self.include_completed or not e['complete']), None)
            if not following:
                self.stop('本课程后续没有符合条件的视频，已停止')
                return
            return self.issue(Action('video', following['index'], following['key'], player['src'], self.include_completed, player.get('time', 0), current_key), f'已看完 {self.watched} 个视频，切换到：' + following['title'])
        if state.get('current'):
            self.armed_video = state['current']['key']
        if abs(player['time'] - self.last_time) > .2:
            self.last_time = player['time']
            self.last_progress = now
        elif now - self.last_progress > 45:
            self.stop('视频长时间没有播放进度，已停止')
            return
        if player['paused'] and player['ready'] >= 2:
            return self.issue(Action('play'), '正在恢复视频播放')
        limit_text = str(self.video_limit) if self.video_limit else '不限'
        self.status = f'已看完 {self.watched}/{limit_text} 个视频；正在播放：' + (state.get('current') or {}).get('title', '当前视频')
