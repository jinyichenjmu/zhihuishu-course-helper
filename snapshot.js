return (() => {
  const visible = e => e && e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
  const rect = e => {
    if (!visible(e)) return null;
    const r = e.getBoundingClientRect();
    let l = Math.max(0, r.left), t = Math.max(0, r.top), b = Math.min(innerHeight, r.bottom), right = Math.min(innerWidth, r.right);
    for (let n = e; n; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.display === 'none' || /hidden|collapse/.test(s.visibility) || s.opacity === '0' || n.getAttribute('aria-hidden') === 'true') return null;
      if (n !== e && /hidden|clip|scroll|auto/.test(s.overflowX + s.overflowY)) {
        const p = n.getBoundingClientRect(); l = Math.max(l, p.left); t = Math.max(t, p.top); right = Math.min(right, p.right); b = Math.min(b, p.bottom);
      }
    }
    return right-l >= 24 && b-t >= 20 ? {x:l+scrollX, y:t+scrollY, width:right-l, height:b-t} : null;
  };
  const selected = e => e.getAttribute('aria-checked') === 'true' || e.classList.contains('is-checked')
    || !!e.querySelector('.topic-option-item.active,.item-topic.active,input:checked,[aria-checked="true"],.el-checkbox.is-checked')
    || [...e.querySelectorAll('use')].some(u => /xuanzhong/.test(u.getAttribute('href') || u.getAttribute('xlink:href') || ''));
  const frameSelector = 'iframe[src*="captcha"],iframe[src*="turing"],iframe[id*="tcaptcha"],#captcha,.tcaptcha-transform,[role="dialog"][aria-label*="安全验证"],[role="dialog"][aria-label="验证码"]';
  const nodes = [...document.querySelectorAll(frameSelector)];
  let captcha = null;
  for (let i=0;i<nodes.length;i++) {
    const r=rect(nodes[i]); if (!r) continue;
    captcha={index:i,rect:r,key:JSON.stringify([location.href,i,nodes[i].id,nodes[i].getAttribute('src'),r])}; break;
  }
  const allDialogs=[...document.querySelectorAll('[role="dialog"][aria-label="弹题测验"]')];
  const dialog=allDialogs.find(visible);
  let quiz=null;
  if(dialog) {
    const title=dialog.querySelector('.title-tit');
    const allOptions=[...dialog.querySelectorAll('.topic-item')];
    const buttons=[...dialog.querySelectorAll('button,[role="button"],.btn')];
    const submit=buttons.find(e=>visible(e)&&/^(提交|提交答案|确认提交|确定|确认答案)$/.test(e.textContent.trim()));
    const next=dialog.querySelector('.btn-next');
    quiz={
      dialogIndex:allDialogs.indexOf(dialog),type:title?.textContent||'',
      key:(dialog.querySelector('.el-pager .active')?.textContent||'1')+'|'+(title?.nextElementSibling?.innerHTML||title?.textContent||''),
      result:!!dialog.querySelector('.answer,.topic-title .error,.topic-title .correct'),
      options:allOptions.map((e,index)=>({index,selected:selected(e),visible:!!visible(e)})).filter(e=>e.visible),
      next:!!next&&!next.disabled,
      close:!!dialog.querySelector('.el-dialog__footer .btn,.el-dialog__headerbtn'),
      submit:submit?{index:buttons.indexOf(submit),disabled:!!submit.disabled||submit.getAttribute('aria-disabled')==='true'||submit.classList.contains('is-disabled')}:null
    };
  }
  const videos=[...document.querySelectorAll('li.video')].map((e,index)=>{
    const time=e.querySelector('.time')?.textContent?.trim()||'';
    const title=e.querySelector('.catalogue_title')?.textContent?.trim()||'';
    const number=e.querySelector('.hour')?.textContent?.trim()||'';
    return {index,time,title,key:[number,title,time].join('|'),complete:!!e.querySelector('.time_icofinish'),current:e.classList.contains('current_play')};
  }).filter(e=>/^(?:\d{1,2}:)?\d{2}:\d{2}$/.test(e.time));
  const current=videos.find(e=>e.current);
  const v=document.querySelector('#vjs_container video');
  const other=[...document.querySelectorAll('[role="dialog"],.el-message-box__wrapper')].filter(visible);
  return {url:location.href,captcha,quiz,videos,current:current||null,
    blocked:other.some(e=>/检测到异常脚本/.test(e.textContent)),
    unknownDialog:other.some(e=>e!==dialog && !e.contains(dialog) && !/安全验证|验证码/.test(e.getAttribute('aria-label')||'')),
    player:v?{time:v.currentTime,duration:Number.isFinite(v.duration)?v.duration:0,src:v.getAttribute('src'),paused:v.paused,ended:v.ended,ready:v.readyState,error:!!v.error}:null,
    legacy:!!document.querySelector('[aria-label^="课程助手切换目标-"],[aria-label^="课程助手验证请求-"]')
  };
})();
