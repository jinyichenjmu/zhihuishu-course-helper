import unittest
from unittest.mock import Mock
from controller import Controller, video_finished
from browser import BrowserAdapter


def state():
    videos = [dict(index=0, key='a', title='当前', current=True, complete=False),
              dict(index=1, key='b', title='已完成', current=False, complete=True),
              dict(index=2, key='c', title='未完成', current=False, complete=False)]
    return dict(url='https://studyvideoh5.zhihuishu.com/stuStudy?test=1', captcha=None,
                blocked=False, unknownDialog=False, legacy=False, quiz=None,
                videos=videos, current=videos[0],
                player=dict(src='a.mp4', ready=4, error=False, paused=False, ended=False, time=1))


class SettingsTests(unittest.TestCase):
    def test_switch_retries_twice_then_stops_without_double_count(self):
        s = state(); now = [0]; c = Controller(clock=lambda: now[0]); c.start(s); c.step(s)
        s['player'].update(ended=True, time=100); action = c.step(s)
        self.assertEqual(c.watched, 1)
        for t, expected in [(7, None), (8, action), (9, None), (16, action), (24, None)]:
            now[0] = t; self.assertEqual(c.step(s), expected)
        self.assertEqual(c.watched, 1)
        now[0] = 31; self.assertIsNone(c.step(s)); self.assertFalse(c.running)

    def test_retry_requires_original_course_and_video_state(self):
        for mutation in ('directory', 'source', 'target_complete', 'captcha', 'quiz'):
            with self.subTest(mutation=mutation):
                s = state(); now = [0]; c = Controller(clock=lambda: now[0]); c.start(s); c.step(s)
                s['player'].update(ended=True, time=100); c.step(s); now[0] = 8
                if mutation == 'directory': s['current'] = s['videos'][1]
                if mutation == 'source': s['player']['src'] = 'different.mp4'
                if mutation == 'target_complete': s['videos'][2]['complete'] = True
                if mutation == 'captcha': s['captcha'] = {'key': 'test'}
                if mutation == 'quiz':
                    s['quiz'] = dict(type='unknown', key='q', result=False, options=[], next=False, close=False, submit=None)
                self.assertIsNone(c.step(s))

    def test_paused_near_end_is_treated_as_finished(self):
        s = state(); c = Controller(); c.start(s); c.step(s)
        s['player'].update(ended=False, paused=True, time=412, duration=412.416009)
        action = c.step(s)
        self.assertEqual(action.kind, 'video')
        tab = Mock(); tab.eles.return_value = [Mock(), Mock(), Mock()]
        adapter = BrowserAdapter(tab); adapter.snapshot = Mock(return_value=s); adapter._mouse_click = Mock()
        adapter.perform(action, s['url'])
        adapter._mouse_click.assert_called_once()

    def test_video_not_finished_when_paused_early_or_still_playing(self):
        self.assertFalse(video_finished(dict(ended=False, paused=True, time=410, duration=412.4)))
        self.assertFalse(video_finished(dict(ended=False, paused=False, time=412, duration=412.4)))

    def test_stale_target_fails_immediately(self):
        s = state(); c = Controller(); c.start(s); c.step(s)
        s['player']['ended'] = True; action = c.step(s)
        s['videos'][2]['complete'] = True
        adapter = BrowserAdapter(Mock()); adapter.snapshot = Mock(return_value=s)
        with self.assertRaisesRegex(RuntimeError, '目标视频已变化或已完成'):
            adapter.perform(action, s['url'])

    def test_switch_same_source_with_new_time_confirms(self):
        s = state(); c = Controller(); c.start(s); c.step(s)
        s['player'].update(ended=True, time=100)
        action = c.step(s); self.assertEqual(action.key, 'c')
        s['videos'][0]['current'] = False; s['videos'][2]['current'] = True
        s['current'] = s['videos'][2]
        self.assertIsNone(c.step(s)); self.assertIsNotNone(c.pending)
        s['player'].update(ended=False, time=0, paused=True)
        self.assertEqual(c.step(s).kind, 'play')

    def test_same_source_progress_confirms_without_time_reset(self):
        s = state(); c = Controller(); c.start(s); c.step(s)
        s['player'].update(ended=True, time=1); c.step(s)
        s['videos'][0]['current'] = False; s['videos'][2]['current'] = True; s['current'] = s['videos'][2]
        s['player'].update(ended=False, time=1)
        c.step(s); self.assertIsNotNone(c.pending)
        s['player']['time'] = 1.8; c.step(s)
        self.assertIsNone(c.pending)

    def test_directory_change_alone_does_not_confirm(self):
        s = state(); now = [0]; c = Controller(clock=lambda: now[0]); c.start(s); c.step(s)
        s['player'].update(ended=True, time=100); c.step(s)
        s['videos'][0]['current'] = False; s['videos'][2]['current'] = True; s['current'] = s['videos'][2]
        s['player']['ended'] = False
        c.step(s); self.assertIsNotNone(c.pending)
        now[0] = 31; c.step(s)
        self.assertFalse(c.running); self.assertIn('播放器未确认加载', c.status)

    def test_limit_stops_after_end_without_double_count(self):
        s = state(); c = Controller(); c.video_limit = 1; c.start(s)
        c.step(s); s['player']['ended'] = True
        self.assertIsNone(c.step(s)); self.assertEqual(c.watched, 1)
        self.assertFalse(c.running); self.assertIn('达到设定数量', c.status)
        c.watched = 0; c.start(s)
        self.assertEqual(c.step(s).key, 'c')
        self.assertEqual(c.watched, 0)

    def test_completed_option_controls_selection_and_click_guard(self):
        for include, target in [(False, 'c'), (True, 'b')]:
            with self.subTest(include=include):
                s = state(); c = Controller(); c.include_completed = include; c.start(s)
                c.step(s); s['player']['ended'] = True
                action = c.step(s)
                self.assertEqual(action.key, target)
                tab = Mock(); tab.eles.return_value = [Mock(), Mock(), Mock()]
                adapter = BrowserAdapter(tab)
                adapter.snapshot = Mock(return_value=s)
                adapter._mouse_click = Mock()
                adapter.perform(action, s['url'])
                adapter._mouse_click.assert_called_once()

    def test_refresh_does_not_reset_count(self):
        s = state(); c = Controller(); c.watched = 2; c.start(s)
        c.step(s); c.stop(); c.start(s)
        s['player']['ended'] = True; c.step(s)
        self.assertEqual(c.watched, 3)


if __name__ == '__main__':
    unittest.main()
