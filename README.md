# 课程播放助手 1.0.0

在“选择浏览器”中选择 Chrome、Edge 或自定义，默认选中 Chrome。选择自定义时，点击“浏览…”选择 Chromium 内核浏览器的可执行文件；然后点击“打开/连接浏览器”。Chrome 和 Edge 在连接时从常见安装路径查找，找不到时可选择自定义路径。若课程浏览器已经在本机端口 9333 运行，程序会连接已有窗口；需要更换浏览器时，先关闭此前由助手打开的课程浏览器，再连接。该功能不支持 Firefox 或 Safari，其他浏览器兼容性取决于实际环境。

“看完视频数量后暂停”填写本轮数量，0 表示不限；当前视频从播放中到结束算 1 个，已结束时才启动的当前视频不重复计数。达到数量后再次点击“启动/继续”开始新一轮计数。勾选“包含已完成视频”后，向后切换时也会选择标记为已完成的视频；不勾选则跳过。设置在点击“启动/继续”时生效。

运行期间检测到验证会刷新一次页面，页面恢复后继续；如果验证仍在或页面未恢复，程序会暂停，请手动处理。刷新可能造成播放进度变化，实际结果取决于网站。

窗口右侧显示本次操作记录，程序目录的 course-helper.log 保存历史记录。浏览器登录数据保存在 browser-profile 文件夹，不要将该文件夹或日志一同分享。

程序默认暂停；关闭程序不会关闭浏览器。遇到异常脚本提示、未知弹窗或播放器错误会停止。

## 源码运行与构建

需要 Python 3.10 或更新版本（含 Tkinter）。Windows 成品为 64 位，macOS 尚未实测，需要自行从源码运行或打包。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

运行测试：`python -m unittest -v test_video_settings test_browser_selection`。构建 Windows 成品：安装 `requirements-build.txt` 后运行 `build.bat`，产物位于 `dist/CourseHelper-Public`。

## 验证情况

Windows 打包依赖自检通过。真实课程网站的兼容性可能随页面变化，尚未完成各课程的端到端验证。
