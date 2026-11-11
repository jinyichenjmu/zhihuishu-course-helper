"""Desktop presentation; all browser operations remain in the worker."""
import math
import os
import queue
import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog, font


def run_gui(options, worker_type, find_browser, version):
    root = tk.Tk()
    root.title('课程播放助手 ' + version)
    root.geometry('1020x720')
    root.minsize(900, 650)
    palette = dict(bg='#EEF3F7', paper='#FFFFFF', ink='#183247', muted='#637989',
                   accent='#087F8C', line='#D7E2EA')
    root.configure(bg=palette['bg'])
    family = 'Microsoft YaHei UI' if sys.platform == 'win32' else 'PingFang SC'
    if family not in font.families(root):
        family = font.nametofont('TkDefaultFont').actual('family')
    root.option_add('*Font', (family, 10))
    style = ttk.Style(root); style.theme_use('clam')
    style.configure('TFrame', background=palette['paper'])
    style.configure('TLabel', background=palette['paper'], foreground=palette['ink'])
    style.configure('Muted.TLabel', foreground=palette['muted'])
    style.configure('Title.TLabel', font=(family, 12, 'bold'))
    style.configure('TButton', padding=(14, 8), borderwidth=0, background='#E9F1F5', foreground=palette['ink'])
    style.map('TButton', background=[('active', '#DAE8EF')], foreground=[('disabled', '#8A9BA7')])
    style.configure('Primary.TButton', background=palette['accent'], foreground='white', font=(family, 10, 'bold'))
    style.map('Primary.TButton', background=[('active', '#066975'), ('disabled', '#B3CBCF')], foreground=[('disabled', '#EFF5F6')])
    style.configure('TRadiobutton', background='white', foreground=palette['ink'], padding=(0, 4))
    style.map('TRadiobutton', background=[('active', 'white')])
    style.configure('TCheckbutton', background='white', foreground=palette['ink'], padding=(0, 5))
    style.map('TCheckbutton', background=[('active', 'white')])
    style.configure('TEntry', padding=8, bordercolor=palette['line'], fieldbackground='#F7FAFC')
    style.configure('Study.Horizontal.TProgressbar', background=palette['accent'], troughcolor='#E7EEF3', borderwidth=0)

    events = queue.Queue()
    worker = worker_type(options, events)
    connected = False
    status = tk.StringVar(value='选择浏览器，连接后在课程页登录，再启动观看。')
    browser_path = tk.StringVar(value=options.browser or '')
    browser_kind = tk.StringVar(value='custom' if options.browser else 'chrome')
    limit = tk.StringVar(value='0')
    include_completed = tk.BooleanVar(value=False)
    reduce_motion = tk.BooleanVar(value=False)
    autoscroll = tk.BooleanVar(value=True)

    root.columnconfigure(0, weight=1); root.rowconfigure(1, weight=1)
    header = tk.Frame(root, bg=palette['bg']); header.grid(row=0, column=0, sticky='ew', padx=26, pady=(20, 16))
    tk.Label(header, text='课程播放助手', font=(family, 22, 'bold'), fg=palette['ink'], bg=palette['bg']).pack(side='left')
    tk.Label(header, text='公开版  ' + version, font=(family, 10), fg=palette['muted'], bg=palette['bg']).pack(side='right')
    body = tk.Frame(root, bg=palette['bg']); body.grid(row=1, column=0, sticky='nsew', padx=26, pady=(0, 14))
    body.columnconfigure(0, weight=0, minsize=320); body.columnconfigure(1, weight=1)
    body.rowconfigure(0, weight=1)
    left = ttk.Frame(body, padding=16); left.grid(row=0, column=0, sticky='nsew', padx=(0, 18))
    right = tk.Frame(body, bg=palette['bg']); right.grid(row=0, column=1, sticky='nsew')
    right.columnconfigure(0, weight=1); right.rowconfigure(1, weight=1)

    ttk.Label(left, text='浏览器', style='Title.TLabel').pack(anchor='w')
    ttk.Label(left, text='选择用于打开课程的浏览器', style='Muted.TLabel').pack(anchor='w', pady=(4, 12))
    choices = ttk.Frame(left); choices.pack(fill='x')
    for label, value in [('Chrome', 'chrome'), ('Edge', 'edge'), ('自定义', 'custom')]:
        ttk.Radiobutton(choices, text=label, value=value, variable=browser_kind).pack(side='left', padx=(0, 12))
    path_row = ttk.Frame(left)
    path_entry = ttk.Entry(path_row, textvariable=browser_path, width=22)
    path_entry.pack(fill='x', pady=(8, 6))
    def choose_browser():
        filters = [('可执行文件', '*.exe'), ('所有文件', '*')] if os.name == 'nt' else [('所有文件', '*')]
        selected = filedialog.askopenfilename(parent=root, title='选择 Chromium 浏览器', filetypes=filters)
        if selected:
            browser_path.set(selected)
    ttk.Button(path_row, text='浏览文件…', command=choose_browser).pack(fill='x')
    def show_custom(*args):
        enabled = browser_kind.get() == 'custom'
        if enabled: path_row.pack(fill='x', after=choices)
        else: path_row.pack_forget()
        path_entry.configure(state='normal' if enabled else 'disabled')
        for widget in path_row.winfo_children()[1:]:
            widget.configure(state='normal' if enabled else 'disabled')
    browser_kind.trace_add('write', show_custom); show_custom()
    ttk.Label(left, text='更换前请关闭已打开的课程浏览器。', style='Muted.TLabel', wraplength=275).pack(anchor='w', pady=(10, 12))

    def report(message):
        status.set(message); add_history(message)

    def connect_selected():
        kind = browser_kind.get()
        if options.attach:
            if kind == 'custom':
                report('接管已有浏览器时不能指定路径。'); return
            path = ''
        else:
            path = browser_path.get().strip() if kind == 'custom' else find_browser(kind)
            if not path:
                report('请填写自定义浏览器路径。' if kind == 'custom' else '未找到所选浏览器，请使用自定义路径。'); return
        report('正在连接浏览器…')
        worker.request(('connect', path))
    ttk.Button(left, text='打开 / 连接浏览器', command=connect_selected).pack(fill='x')
    ttk.Separator(left).pack(fill='x', pady=16)
    ttk.Label(left, text='观看计划', style='Title.TLabel').pack(anchor='w')
    ttk.Label(left, text='看完多少个视频后暂停', style='Muted.TLabel').pack(anchor='w', pady=(10, 6))
    count_row = ttk.Frame(left); count_row.pack(fill='x')
    ttk.Entry(count_row, textvariable=limit, width=7).pack(side='left')
    ttk.Label(count_row, text='个    0 表示不限', style='Muted.TLabel').pack(side='left', padx=10)
    ttk.Checkbutton(left, text='包含已完成的视频', variable=include_completed).pack(anchor='w', pady=(10, 0))
    ttk.Label(left, text='设置在点击“启动 / 继续”时生效。', style='Muted.TLabel', wraplength=275).pack(anchor='w', pady=(4, 16))
    def start():
        try:
            value = int(limit.get())
            if value < 0: raise ValueError
        except ValueError:
            report('观看数量请输入非负整数，0 表示不限。'); return
        worker.request(('start', value, include_completed.get()))
    buttons = ttk.Frame(left); buttons.pack(fill='x')
    buttons.columnconfigure(0, weight=1); buttons.columnconfigure(1, weight=1)
    ttk.Button(buttons, text='启动 / 继续', style='Primary.TButton', command=start).grid(row=0, column=0, sticky='ew', padx=(0, 8))
    ttk.Button(buttons, text='暂停', command=lambda: worker.request('pause')).grid(row=0, column=1, sticky='ew')
    ttk.Checkbutton(left, text='减少动效', variable=reduce_motion).pack(side='bottom', anchor='w', pady=(16, 0))

    monitor = ttk.Frame(right, padding=20); monitor.grid(row=0, column=0, sticky='ew', pady=(0, 16))
    monitor.columnconfigure(1, weight=1)
    dot = tk.Canvas(monitor, width=16, height=16, bg='white', highlightthickness=0)
    dot.grid(row=0, column=0, padx=(0, 8)); light = dot.create_oval(3, 3, 13, 13, fill='#90A4B2', outline='')
    phase = tk.StringVar(value='等待连接')
    ttk.Label(monitor, textvariable=phase, style='Title.TLabel').grid(row=0, column=1, sticky='w')
    stats = tk.StringVar(value='已完成 0 个')
    ttk.Label(monitor, textvariable=stats, foreground=palette['accent']).grid(row=0, column=2, sticky='e')
    status_label = ttk.Label(monitor, textvariable=status, wraplength=450)
    status_label.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(14, 14))
    monitor.bind('<Configure>', lambda e: status_label.configure(wraplength=max(220, e.width-40)))
    progress = ttk.Progressbar(monitor, style='Study.Horizontal.TProgressbar', maximum=100)
    progress.grid(row=2, column=0, columnspan=3, sticky='ew')
    ttk.Label(monitor, text='本轮观看进度 · 按完成视频数统计', style='Muted.TLabel').grid(row=3, column=0, columnspan=3, sticky='w', pady=(7, 0))

    log_panel = ttk.Frame(right, padding=16); log_panel.grid(row=1, column=0, sticky='nsew')
    log_panel.columnconfigure(0, weight=1); log_panel.rowconfigure(1, weight=1)
    log_head = ttk.Frame(log_panel); log_head.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 10))
    ttk.Label(log_head, text='操作记录', style='Title.TLabel').pack(side='left')
    ttk.Checkbutton(log_head, text='跟随最新', variable=autoscroll).pack(side='right')
    history = tk.Text(log_panel, height=9, width=40, state='disabled', wrap='word', relief='flat',
                      background='#F5F8FA', foreground=palette['ink'], padx=12, pady=12,
                      font=(family, 10), spacing3=7, selectbackground='#C4E3E7')
    history.grid(row=1, column=0, sticky='nsew')
    scroll = ttk.Scrollbar(log_panel, command=history.yview); scroll.grid(row=1, column=1, sticky='ns')
    history.configure(yscrollcommand=scroll.set)
    history.tag_configure('time', foreground='#7F929F')
    history.tag_configure('notice', foreground='#98611E')
    def add_history(message):
        history.configure(state='normal')
        history.insert('end', time.strftime('%H:%M:%S') + '  ', 'time')
        tag = 'notice' if any(w in str(message) for w in ('失败', '错误', '未找到', '超时', '请手动')) else ''
        history.insert('end', str(message) + '\n', tag)
        if int(history.index('end-1c').split('.')[0]) > 1000:
            history.delete('1.0', '101.0')
        if autoscroll.get(): history.see('end')
        history.configure(state='disabled')
    ttk.Label(log_panel, text='完整记录保存在 course-helper.log', style='Muted.TLabel').grid(row=2, column=0, sticky='w', pady=(10, 0))
    footer = tk.Frame(root, bg=palette['bg']); footer.grid(row=2, column=0, sticky='ew', padx=26, pady=(0, 12))
    tk.Label(footer, text='遇到验证会尝试刷新；未恢复时暂停，等待手动处理。', bg=palette['bg'], fg=palette['muted'], font=(family, 9)).pack(side='left')

    displayed_progress = 0.0
    def animate():
        nonlocal displayed_progress
        controller = worker.controller
        running = controller.running and not worker.cancel.is_set()
        phase.set('正在运行' if running else ('已暂停' if connected else '等待连接'))
        stats.set(f'已完成 {controller.watched} 个' + (f' / {controller.video_limit} 个' if controller.video_limit else ' · 不限'))
        target = min(100, 100*controller.watched/controller.video_limit) if controller.video_limit else 0
        displayed_progress = target if reduce_motion.get() else displayed_progress + (target-displayed_progress)*.22
        progress['value'] = displayed_progress
        if running:
            blend = 0 if reduce_motion.get() else (math.sin(time.monotonic()*3)+1)*.22
            base, pale = (8, 127, 140), (178, 224, 227)
            color = '#' + ''.join(f'{int(a+(b-a)*blend):02x}' for a,b in zip(base,pale))
        else: color = '#90A4B2'
        dot.itemconfigure(light, fill=color)
        if not worker.closing.is_set(): root.after(60 if running or abs(target-displayed_progress)>.1 else 200, animate)

    def pump():
        nonlocal connected
        for _ in range(100):
            try: kind, value = events.get_nowait()
            except queue.Empty: break
            if kind == 'connected': connected = bool(value)
            elif kind == 'status': status.set(value); add_history(value)
            elif kind == 'history': add_history(value)
        if not worker.closing.is_set(): root.after(150, pump)
    def close():
        worker.shutdown(); root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    add_history('助手已准备好。请先连接浏览器。')
    worker.start()
    if options.resume:
        worker.request('connect'); worker.request('start')
    root.after(150, pump); root.after(60, animate)
    root.mainloop()
