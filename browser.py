"""DrissionPage adapter. Decisions use DOM reads; input uses browser action chains."""
import json
from pathlib import Path
import time
from controller import course_url, video_finished

ROOT = Path(__file__).resolve().parent
SNAPSHOT = (ROOT / 'snapshot.js').read_text(encoding='utf-8')
QUIZ = '[role="dialog"][aria-label="弹题测验"]'

# Compute an actually exposed point inside the target, accounting for nested
# scroll containers. A DOM overlay is never dismissed or clicked through.
CLICK_POINT = '''
const r=this.getBoundingClientRect();
let l=Math.max(0,r.left),t=Math.max(0,r.top),right=Math.min(innerWidth,r.right),b=Math.min(innerHeight,r.bottom);
if(this.disabled||this.getAttribute('aria-disabled')==='true')return null;
for(let n=this;n;n=n.parentElement){
 const s=getComputedStyle(n);
 if(s.display==='none'||s.visibility==='hidden'||s.visibility==='collapse'||Number(s.opacity)===0)return null;
 if(n!==this&&/hidden|clip|scroll|auto/.test(s.overflowX+s.overflowY)){
  const p=n.getBoundingClientRect();l=Math.max(l,p.left);t=Math.max(t,p.top);right=Math.min(right,p.right);b=Math.min(b,p.bottom);
 }
}
if(right-l<2||b-t<2)return null;
for(const [fx,fy] of [[.5,.5],[.25,.5],[.75,.5],[.5,.25],[.5,.75],[.25,.25],[.75,.75]]){
 const x=l+(right-l)*fx,y=t+(b-t)*fy,e=document.elementFromPoint(x,y);
 if(e&&(e===this||this.contains(e)))return {x:x+scrollX,y:y+scrollY};
}
return null;
'''


class BrowserAdapter:
    def __init__(self, tab, test_mode=False):
        self.tab = tab
        self.test_mode = test_mode

    def snapshot(self):
        return self.tab.run_js(SNAPSHOT)

    def guard(self, state, captcha=False):
        if not (course_url(state['url']) or (self.test_mode and state['url'].startswith('http://127.0.0.1:'))):
            raise RuntimeError('当前标签页不是指定的课程页面')
        if state['blocked'] or state['legacy'] or state['unknownDialog']:
            raise RuntimeError('页面出现阻断提示或其他助手正在操作')
        if state['captcha'] and not captcha:
            raise RuntimeError('检测到安全验证，已取消普通点击')

    def _mouse_click(self, element):
        if not element:
            raise RuntimeError('目标元素已消失')
        element.scroll.to_see(center=False)
        point = element.run_js(CLICK_POINT)
        if not point:
            raise RuntimeError('目标不可见、不可用或被遮挡，已取消点击')
        # Actions sends browser mouse events. Never use JS click or its fallback.
        self.tab.actions.move_to((point['x'], point['y']), duration=.15)
        # Hover may reveal a different layer; validate the exact point again.
        allowed = element.run_js('''const e=document.elementFromPoint(arguments[0]-scrollX,arguments[1]-scrollY);
            return e&&(e===this||this.contains(e));''', point['x'], point['y'])
        if not allowed:
            raise RuntimeError('鼠标移入后目标被遮挡，已取消点击')
        self.tab.actions.click()

    def _resume_video(self):
        container = self.tab.ele('css:#vjs_container', timeout=0)
        if not container:
            raise RuntimeError('课程播放器已消失')
        # The website hides its own controls until mousemove. Its videoArea is
        # deliberately above <video>; clicking the underlying video is wrong.
        self.tab.actions.move_to(container, duration=.15)
        time.sleep(.2)
        selectors = ('#playButton .bigPlayButton', '#playButton', '.controlsBar .playButton',
                     '.vjs-play-control', '.vjs-big-play-button', '.videoArea', 'video')
        for selector in selectors:
            element = container.ele('css:' + selector, timeout=0)
            if not element or not element.run_js(CLICK_POINT):
                continue
            state = self.snapshot()
            self.guard(state)
            if state['quiz'] or not state['player'] or not state['player']['paused'] or state['player']['ended']:
                return
            self._mouse_click(element)
            return
        raise RuntimeError('没有找到可点击的播放按钮，请检查播放器是否被页面弹窗遮挡')

    def perform(self, action, expected_url=None):
        state = self.snapshot()
        self.guard(state)
        if expected_url and state['url'] != expected_url:
            raise RuntimeError('课程地址已变化，已取消本次操作')
        if action.kind in ('option', 'submit', 'next', 'close'):
            quiz = state['quiz']
            if not quiz or quiz['key'] != action.key:
                return  # Page changed; let the controller observe the new state.
            dialog = self.tab.eles('css:' + QUIZ)[quiz['dialogIndex']]
            if action.kind == 'option':
                option = next((e for e in quiz['options'] if e['index'] == action.index), None)
                if not option or option['selected'] or quiz['result']:
                    return
                element = dialog.eles('css:.topic-item')[action.index]
            elif action.kind == 'submit':
                if not quiz.get('submit') or quiz['submit']['disabled'] or quiz['result']:
                    return
                element = dialog.eles('css:button,[role="button"],.btn')[action.index]
            else:
                if action.kind == 'next':
                    element = dialog.ele('css:.btn-next', timeout=0)
                else:
                    element = dialog.ele('css:.el-dialog__footer .btn', timeout=0) or dialog.ele('css:.el-dialog__headerbtn', timeout=0)
            self._mouse_click(element)
        elif action.kind == 'video':
            target = next((e for e in state['videos'] if e['key'] == action.key and e['index'] == action.index and (action.allow_complete or not e['complete'])), None)
            if state.get('current') and state['current']['key'] == action.key:
                return
            if not target:
                raise RuntimeError('目标视频已变化或已完成，未执行切换')
            if action.origin_key and (not state.get('current') or state['current']['key'] != action.origin_key):
                raise RuntimeError('当前目录已变化，未执行切换，请手动检查')
            if not video_finished(state['player']) or state['player']['src'] != action.source:
                raise RuntimeError('当前视频状态已变化，未执行切换，请检查播放状态')
            row = self.tab.eles('css:li.video')[target['index']]
            self._mouse_click(row.ele('css:.catalogue_title', timeout=0) or row)
        elif action.kind == 'play':
            if state['quiz'] or not state['player'] or not state['player']['paused']:
                return
            self._resume_video()



def connect(port, profile, address=None, browser_path=None):
    from DrissionPage import Chromium, ChromiumOptions
    options = ChromiumOptions(read_file=False)
    if address:
        # Only loopback attachment is supported; never connect a remote debugging service.
        host, sep, value = address.rpartition(':')
        if not sep or host not in ('127.0.0.1', 'localhost') or not value.isdigit() or not 1 <= int(value) <= 65535:
            raise ValueError('接管地址必须是 127.0.0.1:端口 或 localhost:端口')
        options.set_address(address).existing_only()
    else:
        options.set_address('127.0.0.1:' + str(port)).set_user_data_path(str(Path(profile).resolve()))
        if browser_path:
            options.set_browser_path(browser_path)
    browser = Chromium(options)
    tabs = [t for t in browser.get_tabs(url='studyvideoh5.zhihuishu.com/stuStudy') if course_url(t.url)]
    if len(tabs) > 1:
        raise RuntimeError('发现多个课程标签页，请关闭多余的课程页后重新连接')
    tab = tabs[0] if tabs else browser.latest_tab
    if not address and not tabs:
        tab.get('https://onlineweb.zhihuishu.com/')
    return browser, BrowserAdapter(tab)
