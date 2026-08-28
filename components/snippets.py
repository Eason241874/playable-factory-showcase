# -*- coding: utf-8 -*-
"""组件片段库：基础样式 + 增强组件 HTML/CSS/JS。

v2 升级（量产级）：
- BASE_CSS：安全区感知、横竖屏适配、毛玻璃面板、呼吸按钮
- 引导手：双伪元素脉冲环（替代 emoji）
- 音效引擎：调用 App.sound.*（零音频文件）
- 各组件全部支持横竖屏 + 安全区
"""

# =========================================================================
# BASE_CSS：全局样式骨架（所有产物共享）
# =========================================================================

BASE_CSS = """<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{width:100%;height:100%;height:100dvh;overflow:hidden;
  font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
  user-select:none;-webkit-user-select:none;touch-action:manipulation;
  background:#000;}
body{background:{{theme_bg}}}
#stage{position:fixed;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;
  overflow:hidden}

/* ---- 通用层：开始/倒计时/结算 ---- */
.layer{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}

/* 开始页：品牌 Logo 浮在左上 + 中央毛玻璃卡片 + 呼吸按钮 */
#start-layer{
  background:{{theme_bg}};
  z-index:10;transition:opacity .35s;
  padding-top:env(safe-area-inset-top,0px);
  padding-bottom:env(safe-area-inset-bottom,0px);
  padding-left:env(safe-area-inset-left,0px);
  padding-right:env(safe-area-inset-right,0px);
}
#start-layer::before{content:"";position:absolute;inset:0;
  background:
    radial-gradient(circle at 22% 24%,rgba(96,165,250,.28),transparent 26%),
    radial-gradient(circle at 78% 18%,rgba(251,191,36,.22),transparent 22%),
    linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,0) 44%);
  pointer-events:none}
#start-layer::after{content:"";position:absolute;left:8%;right:8%;bottom:9%;height:32%;
  background:linear-gradient(180deg,rgba(255,255,255,.10),rgba(255,255,255,.02));
  border:1px solid rgba(255,255,255,.10);border-radius:26px;
  transform:perspective(700px) rotateX(58deg);
  box-shadow:0 42px 90px rgba(0,0,0,.35);pointer-events:none}
#start-layer.hide,#end-layer.hide,#count-layer.hide{opacity:0;pointer-events:none}

.brand-shell-top{position:absolute;top:max(12px,env(safe-area-inset-top,12px));left:max(14px,env(safe-area-inset-left,14px));z-index:11}
.brand-logo{font-size:13px;font-weight:800;color:rgba(255,255,255,.72);letter-spacing:1px;
  padding:7px 11px;border:1px solid rgba(255,255,255,.14);border-radius:999px;
  background:rgba(8,12,20,.34);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  text-shadow:0 1px 4px rgba(0,0,0,.4)}

.start-card{
  position:relative;z-index:2;
  background:linear-gradient(180deg,rgba(255,255,255,.16),rgba(255,255,255,.07));
  backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);
  border:1px solid rgba(255,255,255,.20);border-radius:20px;
  padding:34px 30px 30px;max-width:360px;width:82vw;
  box-shadow:0 28px 70px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.18);
}
.start-card::before{content:"LIVE DEMO";position:absolute;top:14px;right:14px;
  font-size:10px;font-weight:900;color:#f8d66d;letter-spacing:1px;
  padding:4px 7px;border-radius:999px;background:rgba(248,214,109,.12);
  border:1px solid rgba(248,214,109,.28)}
.start-icon{display:grid;place-items:center;width:86px;height:86px;margin:0 auto 18px;
  border-radius:22px;background:linear-gradient(145deg,#f8d66d,#f97316 56%,#f43f5e);
  color:#151922;font-size:26px;font-weight:1000;letter-spacing:0;
  box-shadow:0 20px 36px rgba(249,115,22,.28),inset 0 2px 0 rgba(255,255,255,.35);
  animation:iconFloat 3s ease-in-out infinite}
@keyframes iconFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}

.game-title{font-size:clamp(24px,5vw,32px);font-weight:950;color:#fff;
  text-shadow:0 4px 18px rgba(0,0,0,.45);margin-bottom:9px;padding:0 12px}
.game-desc{font-size:14px;color:rgba(235,242,255,.86);margin-bottom:26px;padding:0 10px;line-height:1.7}

.btn-start{display:inline-block;padding:15px 48px;font-size:18px;font-weight:900;color:#101520;
  background:linear-gradient(180deg,#fff1a3,#f59e0b);border:none;border-radius:14px;
  box-shadow:0 8px 0 #9a5a0d,0 18px 32px rgba(0,0,0,.35);cursor:pointer;
  animation:breath 1.2s ease-in-out infinite}
.btn-start:active{transform:translateY(5px);box-shadow:0 3px 0 #9a5a0d}
@keyframes breath{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}

/* ---- 倒计时：大字居中 ---- */
#count-layer{
  background:rgba(8,12,20,.62);
  z-index:15;transition:opacity .2s;
  padding-top:env(safe-area-inset-top,0px);
}
#count-num{font-size:clamp(80px,16vw,120px);font-weight:900;color:#fff;
  text-shadow:0 4px 24px rgba(0,0,0,.45);
  animation:cdPop .45s cubic-bezier(.2,1.4,.4,1) both}
@keyframes cdPop{0%{transform:scale(.3);opacity:0}70%{transform:scale(1.12)}100%{transform:scale(1);opacity:1}}

/* ---- 结算页：毛玻璃面板 + 图片素材按钮 + 弹簧动画 ---- */
#end-layer{
  background:rgba(10,12,30,.88);z-index:60;transition:opacity .35s;
  padding-top:env(safe-area-inset-top,0px);
  padding-bottom:env(safe-area-inset-bottom,0px);
  padding-left:env(safe-area-inset-left,0px);
  padding-right:env(safe-area-inset-right,0px);
}
.end-overlay{position:absolute;inset:0;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.result-pop{position:relative;z-index:2;
  background:rgba(255,255,255,.06);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  border:1px solid rgba(255,255,255,.14);border-radius:28px;
  padding:28px 20px 24px;max-width:380px;width:86vw;
  box-shadow:0 24px 56px rgba(0,0,0,.55);
  animation:popIn .45s cubic-bezier(.2,1.4,.4,1) both}
@keyframes popIn{0%{transform:scale(.7) translateY(40px);opacity:0}100%{transform:scale(1) translateY(0);opacity:1}}
.result-emoji{font-size:52px;margin-bottom:6px}

/* 结算页图片素材按钮（真实图片，非 CSS 按钮） */
.settle-img-banner{width:min(78vw,420px);max-width:100%;object-fit:contain;margin:0 auto 8px;
  filter:drop-shadow(0 8px 24px rgba(0,0,0,.5))}
.settle-img-btn{width:min(60vw,320px);max-width:100%;object-fit:contain;cursor:pointer;
  margin:6px auto;transition:transform .12s ease;display:block}
.settle-img-btn:active{transform:scale(.94)}
.settle-img-btn:hover{filter:brightness(1.1)}

/* 品牌 Logo 图片 */
.brand-logo-img{height:32px;width:auto;object-fit:contain;
  filter:drop-shadow(0 2px 6px rgba(0,0,0,.5))}
#brand-shell-logo-img{height:clamp(24px,4vw,36px);width:auto;object-fit:contain;
  filter:drop-shadow(0 2px 8px rgba(0,0,0,.6))}

.btn-cta{display:inline-block;margin-top:22px;padding:15px 48px;font-size:19px;font-weight:800;color:#fff;
  background:linear-gradient(180deg,#ff5f6d,#ff2d55);border:none;border-radius:999px;
  box-shadow:0 8px 0 #a5122e,0 14px 28px rgba(0,0,0,.4);cursor:pointer;
  animation:breath 1.2s ease-in-out infinite}
.btn-cta:active{transform:translateY(5px);box-shadow:0 3px 0 #a5122e}

.end-btns{display:flex;gap:14px;align-items:center;justify-content:center;flex-wrap:wrap}
.btn-retry{display:inline-block;margin-top:22px;padding:15px 36px;font-size:17px;font-weight:800;color:#fff;
  background:rgba(255,255,255,.10);border:2px solid rgba(255,255,255,.45);border-radius:999px;cursor:pointer;
  transition:background .15s}
.btn-retry:active{background:rgba(255,255,255,.22);transform:translateY(3px)}

/* ---- 常驻品牌条 + CTA 热区（安全区感知）---- */
#brand-shell{position:fixed;top:0;left:0;right:0;z-index:41;display:flex;
  justify-content:space-between;align-items:center;
  padding:max(10px,env(safe-area-inset-top,10px)) max(14px,env(safe-area-inset-right,14px)) 8px max(14px,env(safe-area-inset-left,14px));
  pointer-events:none}
#brand-shell-logo{font-size:clamp(13px,2.5vw,16px);font-weight:950;letter-spacing:.5px;color:#fff;
  padding:7px 11px;border:1px solid rgba(255,255,255,.14);border-radius:999px;
  background:rgba(8,12,20,.38);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  text-shadow:0 2px 10px rgba(0,0,0,.75)}
#brand-cta-shell{pointer-events:auto;font-size:clamp(13px,2.4vw,15px);font-weight:900;letter-spacing:1px;
  color:#101520;background:linear-gradient(180deg,#fff1a3,#f59e0b);border:none;border-radius:12px;
  padding:9px 20px;box-shadow:0 4px 0 #9a5a0d,0 8px 18px rgba(0,0,0,.45);cursor:pointer;
  animation:breath 1.4s ease-in-out infinite}
#brand-cta-shell:active{transform:translateY(3px);box-shadow:0 1px 0 #9a5a0d}

#cta-hotzone{position:fixed;top:0;left:0;right:0;height:max(64px,calc(env(safe-area-inset-top,0px) + 50px));z-index:40;cursor:pointer}

/* ---- 横竖屏适配 ---- */
@media (orientation:landscape){
  .start-card{max-width:340px;padding:26px 22px 22px;border-radius:18px}
  .start-icon{width:66px;height:66px;font-size:22px;margin-bottom:12px}
  .game-title{font-size:clamp(18px,4vw,24px)}
  .game-desc{font-size:13px;margin-bottom:18px}
  .btn-start{padding:12px 38px;font-size:16px}
  .result-pop{max-width:320px;padding:20px 16px 18px}
  .settle-img-banner{width:min(44vw,320px)}
  .settle-img-btn{width:min(32vw,240px)}
  .btn-cta{padding:12px 36px;font-size:16px}
  #brand-shell-logo{font-size:13px}
  #brand-cta-shell{padding:7px 16px;font-size:12px}
  #cta-hotzone{height:50px}
}
</style>"""

# =========================================================================
# 组件 CSS
# =========================================================================

CSS = {
    "countdown": """.countdown{position:fixed;top:max(58px,calc(env(safe-area-inset-top,0px) + 58px));right:max(16px,env(safe-area-inset-right,16px));
  z-index:35;font-size:14px;font-weight:700;color:#ffd76a;
  background:rgba(8,12,20,.58);padding:6px 14px;border-radius:999px;
  border:1px solid rgba(255,215,106,.3);display:none}
.countdown.visible{display:block}
.countdown.urgent{animation:cdShake .5s ease-in-out infinite;color:#ff6b5e}
@keyframes cdShake{0%,100%{transform:translateX(0)}25%{transform:translateX(-2px)}75%{transform:translateX(2px)}}""",

    "progress_bar": """.progress-wrap{position:fixed;top:max(58px,calc(env(safe-area-inset-top,0px) + 58px));left:max(16px,env(safe-area-inset-left,16px));
  z-index:35;width:clamp(120px,28vw,170px)}
.progress-label{font-size:11px;color:rgba(235,242,255,.72);margin-bottom:4px;text-align:left}
.progress{height:12px;background:rgba(8,12,20,.55);border-radius:999px;overflow:hidden;
  border:1px solid rgba(255,255,255,.2)}
.progress-fill{height:100%;width:0%;background:linear-gradient(90deg,#7CFC9A,#2ecc71);border-radius:999px;transition:width .25s}""",

    "hint_hand": """.hint-hand{position:absolute;z-index:25;pointer-events:none}
/* 引导脉冲环（双伪元素，替代 emoji） */
.hint-hand::before{content:"";position:absolute;left:50%;top:50%;
  width:48px;height:48px;border-radius:999px;
  border:3px solid rgba(255,210,90,.85);
  background:radial-gradient(circle,rgba(255,210,90,.12) 0%,rgba(255,210,90,0) 68%);
  transform:translate(-50%,-50%) scale(.6);
  animation:hintRing1 1.5s ease-out infinite}
.hint-hand::after{content:"";position:absolute;left:50%;top:50%;
  width:52px;height:52px;border-radius:999px;
  border:2px solid rgba(255,210,90,.55);
  transform:translate(-50%,-50%) scale(.8);
  animation:hintRing2 1.5s .6s ease-out infinite}
@keyframes hintRing1{0%{transform:translate(-50%,-50%) scale(.6);opacity:1}100%{transform:translate(-50%,-50%) scale(1.8);opacity:0}}
@keyframes hintRing2{0%{transform:translate(-50%,-50%) scale(.8);opacity:.8}100%{transform:translate(-50%,-50%) scale(1.5);opacity:0}}
.hint-hand .hint-icon{position:relative;z-index:2;font-size:38px;text-align:center;
  animation:hintTap 1s ease-in-out infinite}
@keyframes hintTap{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(-8px,6px) scale(.88)}}
.hint-hand.hide{display:none}""",

    "coin_counter": """.coin-wrap{position:fixed;top:max(14px,env(safe-area-inset-top,14px));left:max(16px,env(safe-area-inset-left,16px));
  z-index:35;display:flex;align-items:center;gap:6px;
  background:rgba(0,0,0,.42);padding:5px 14px 5px 6px;border-radius:999px;
  border:1px solid rgba(255,215,106,.4)}
.coin-wrap img{width:22px;height:22px}
.coin-num{font-size:15px;font-weight:800;color:#ffd76a;font-variant-numeric:tabular-nums}
.coin-target{font-size:11px;color:rgba(255,255,255,.5)}
.coin-wrap.bump{animation:coinBump .3s ease-out}
@keyframes coinBump{0%{transform:scale(1)}40%{transform:scale(1.15)}100%{transform:scale(1)}}
.fly-coin{position:fixed;z-index:70;width:28px;height:28px;pointer-events:none;
  transition:all .7s cubic-bezier(.3,.7,.4,1);
  filter:drop-shadow(0 3px 6px rgba(0,0,0,.5))}""",

    "combo_text": """.combo-pop{position:fixed;z-index:45;left:50%;top:20%;
  transform:translateX(-50%);pointer-events:none;
  font-size:clamp(28px,6vw,40px);font-weight:900;color:#ffe259;
  -webkit-text-stroke:1.5px #b0591a;text-shadow:0 4px 14px rgba(0,0,0,.5);
  animation:comboIn .55s cubic-bezier(.2,1.6,.4,1) both}
@keyframes comboIn{0%{transform:translateX(-50%) scale(.3);opacity:0}60%{transform:translateX(-50%) scale(1.2)}100%{transform:translateX(-50%) scale(1);opacity:1}}""",

    "screen_shake": """#stage.shake{animation:shk .2s linear}
@keyframes shk{0%,100%{transform:translate(0,0)}20%{transform:translate(-6px,3px)}40%{transform:translate(5px,-4px)}60%{transform:translate(-4px,-3px)}80%{transform:translate(4px,2px)}}""",

    "task_goal": """.task-goal{position:fixed;top:max(46px,calc(env(safe-area-inset-top,0px) + 46px));left:50%;
  transform:translateX(-50%);z-index:35;display:flex;gap:8px;align-items:center;
  background:rgba(0,0,0,.42);border:1px solid rgba(255,215,106,.35);border-radius:12px;
  padding:6px 14px;backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.task-goal .tg-label{font-size:12px;color:rgba(255,255,255,.7)}
.task-goal .tg-item{font-size:13px;font-weight:800;color:#ffd76a}
.task-goal .tg-item.done{color:#7CFC9A;text-decoration:line-through}""",
}

# =========================================================================
# 组件 HTML
# =========================================================================

HTML = {
    "countdown": """<div class="countdown" id="countdown">⏱ <span id="cd-num">30</span>s</div>""",

    "progress_bar": """<div class="progress-wrap"><div class="progress-label">通关进度</div><div class="progress"><div class="progress-fill" id="pfill"></div></div></div>""",

    "hint_hand": """<div class="hint-hand" id="hint-hand"><div class="hint-icon">👆</div></div>""",

    "coin_counter": """<div class="coin-wrap" id="coin-wrap"><img id="coin-icon" src="" alt=""><span class="coin-num" id="coin-num">0</span><span class="coin-target">/ <span id="coin-target">100</span></span></div>""",

    "combo_text": "",

    "screen_shake": "",

    "task_goal": """<div class="task-goal" id="task-goal"><span class="tg-label">任务</span><span class="tg-item" id="tg-chest">宝箱 0/3</span></div>""",
}

# =========================================================================
# 组件 JS
# =========================================================================

JS = {
    "countdown": """// [component: countdown] 超时倒计时
var cdEl = el('cd-num'), cdWrap = el('countdown'), cdTimer = null;
on('start', function(){
  var cd = App.cfg.countdown_seconds || 30;
  cdEl.textContent = cd;
  cdWrap.classList.add('visible');
  cdTimer = setInterval(function(){
    cd--; cdEl.textContent = cd;
    if (cd <= 5) cdWrap.classList.add('urgent');
    if (cd <= 0) { clearInterval(cdTimer); App.end('fail'); }
  }, 1000);
});
on('end', function(){ clearInterval(cdTimer); });""",

    "progress_bar": """// [component: progress_bar] 进度条
on('cleared', function(){
  var pct = Math.round(App.state.cleared / Math.max(1, App.state.total) * 100);
  var pf = el('pfill'); if (pf) pf.style.width = pct + '%';
});""",

    "hint_hand": """// [component: hint_hand] 引导脉冲环
on('start', function(){
  var hand = el('hint-hand'), gl = el('game-layer');
  if (!hand || !gl) return;
  var r = gl.getBoundingClientRect();
  hand.style.left = (r.width / 2 + 20) + 'px';
  hand.style.top = (r.height / 2 + 30) + 'px';
  hand.style.display = '';
});
on('first_act', function(){ var h = el('hint-hand'); if (h) h.classList.add('hide'); });
// 横竖屏切换时重算位置
on('layout', function(){
  var hand = el('hint-hand'), gl = el('game-layer');
  if (!hand || !gl || hand.classList.contains('hide')) return;
  var r = gl.getBoundingClientRect();
  hand.style.left = (r.width / 2 + 20) + 'px';
  hand.style.top = (r.height / 2 + 30) + 'px';
});""",

    "coin_counter": """// [component: coin_counter] 金币计数 + 滚动动画
(function(){
  var icon = el('coin-icon');
  if (icon && App.cfg.img_coin) icon.src = App.cfg.img_coin;
  var targetEl = el('coin-target');
  if (targetEl && App.cfg.coin_target) targetEl.textContent = App.cfg.coin_target;
  var shown = 0, iv = null;
  on('gold', function(){
    var goal = App.state.gold || 0;
    var wrap = el('coin-wrap');
    if (wrap) { wrap.classList.remove('bump'); void wrap.offsetWidth; wrap.classList.add('bump'); }
    if (iv) clearInterval(iv);
    iv = setInterval(function(){
      var diff = goal - shown;
      if (diff === 0) { clearInterval(iv); iv = null; return; }
      shown += diff > 0 ? Math.max(1, Math.ceil(diff / 4)) : Math.min(-1, Math.floor(diff / 4));
      var num = el('coin-num'); if (num) num.textContent = shown;
    }, 40);
  });
})();""",

    "combo_text": """// [component: combo_text] 连击飘字
(function(){
  var lastT = 0, combo = 0, win = App.cfg.combo_window_ms || 1800;
  function pop(){
    var old = D.querySelector('.combo-pop'); if (old) old.remove();
    if (combo < 2) return;
    var d = D.createElement('div'); d.className = 'combo-pop';
    d.textContent = combo + ' 连击!';
    d.style.fontSize = Math.min(54, 26 + combo * 4) + 'px';
    el('game-layer').appendChild(d);
    setTimeout(function(){ d.remove(); }, 900);
    // 5 连击震动
    if (combo >= 5) { var st = el('stage'); if (st) { st.classList.remove('shake'); void st.offsetWidth; st.classList.add('shake'); } }
  }
  on('cleared', function(){
    var now = Date.now();
    combo = (now - lastT <= win) ? combo + 1 : 1;
    lastT = now;
    pop();
  });
})();""",

    "screen_shake": """// [component: screen_shake] 关键事件震屏
(function(){
  function shake(){
    var st = el('stage'); if (!st) return;
    st.classList.remove('shake'); void st.offsetWidth; st.classList.add('shake');
  }
  on('zombie', shake);
  on('end', function(){ if (App.state.result === 'fail') shake(); });
})();""",

    "task_goal": """// [component: task_goal] 宝箱收集进度
(function(){
  on('start', function(){
    var t = el('tg-chest');
    if (t) t.textContent = '宝箱 0/' + App.state.total;
  });
  on('cleared', function(){
    var t = el('tg-chest'); if (!t) return;
    t.textContent = '宝箱 ' + App.state.cleared + '/' + App.state.total;
    if (App.state.cleared >= App.state.total) t.classList.add('done');
  });
})();""",
}
