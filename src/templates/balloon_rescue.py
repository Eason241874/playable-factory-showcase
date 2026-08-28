# -*- coding: utf-8 -*-
"""热气球救援 · 量产级 v3（balloon_rescue）。

复刻攀岩包自研物理引擎（非 Matter.js），真实铁片/螺丝手感。
"""

HTML = """
<div id="balloon-stage">
  <canvas id="balloon-bg-canvas"></canvas>
  <div id="cloud-layer"><i></i><i></i><i></i><i></i><i></i></div>
  <div id="char"><img id="char-img" src="{{img_character}}" alt="" draggable="false"></div>
  <div id="altitude"><div class="alt-track"><div class="alt-fill" id="alt-fill"></div></div><div class="alt-label" id="alt-label">1000m</div></div>
  <div id="stage-tip">点击开始救援</div>
</div>

<div id="choice-layer">
  <div class="choice-title">选择修复道具</div>
  <div class="choice-row">
    <div class="choice-item" data-idx="0"><img id="choice-img-0" alt=""></div>
    <div class="choice-item" data-idx="1"><img id="choice-img-1" alt=""></div>
  </div>
</div>

<canvas id="balloon-screw-canvas" width="750" height="1334"></canvas>
<div id="burn-mask"></div>
"""

CSS = """
/* ---- 高空舞台 ---- */
#balloon-stage{position:absolute;inset:0;overflow:hidden;touch-action:none}
#balloon-bg-canvas{position:absolute;inset:0;width:100%;height:100%;display:block}
#cloud-layer{position:absolute;inset:0;pointer-events:none;overflow:hidden}
#cloud-layer i{position:absolute;width:34vw;height:9vw;left:-40vw;border-radius:999px;
  background:radial-gradient(ellipse at 30% 40%,rgba(255,255,255,.95),rgba(255,255,255,.55) 60%,rgba(255,255,255,0) 75%);
  filter:blur(2px);animation:cloudMove linear infinite}
#cloud-layer i:nth-child(1){top:12%;animation-duration:9s}
#cloud-layer i:nth-child(2){top:30%;animation-duration:13s;animation-delay:-4s;width:26vw;height:7vw}
#cloud-layer i:nth-child(3){top:52%;animation-duration:11s;animation-delay:-7s}
#cloud-layer i:nth-child(4){top:70%;animation-duration:15s;animation-delay:-2s;width:30vw;height:8vw}
#cloud-layer i:nth-child(5){top:86%;animation-duration:10s;animation-delay:-9s}
@keyframes cloudMove{from{transform:translateX(0)}to{transform:translateX(180vw)}}

#char{position:absolute;left:50%;top:34%;width:46vmin;max-width:330px;
  transform:translate(-50%,-50%);z-index:5;pointer-events:none;
  animation:windFloat 3.4s ease-in-out infinite;
  filter:drop-shadow(0 14px 24px rgba(20,60,110,.35));transition:filter .4s}
#char.fixed{filter:drop-shadow(0 0 26px rgba(120,255,160,.9)) drop-shadow(0 14px 24px rgba(20,60,110,.35))}
#char img{width:100%;display:block}
@keyframes windFloat{
  0%,100%{transform:translate(-50%,-50%) translate(0,0) rotate(-2.4deg)}
  25%{transform:translate(-50%,-50%) translate(1.4vmin,-1.6vmin) rotate(1.8deg)}
  50%{transform:translate(-50%,-50%) translate(0.4vmin,1.2vmin) rotate(2.6deg)}
  75%{transform:translate(-50%,-50%) translate(-1.2vmin,-0.6vmin) rotate(-1.6deg)}}

#altitude{position:absolute;right:max(10px,env(safe-area-inset-right,10px));
  top:18%;bottom:18%;width:34px;z-index:8;pointer-events:none;
  display:flex;flex-direction:column;align-items:center;gap:6px}
.alt-track{flex:1;width:10px;background:rgba(0,30,60,.35);border-radius:999px;
  border:1px solid rgba(255,255,255,.5);overflow:hidden;display:flex;flex-direction:column-reverse}
.alt-fill{width:100%;height:100%;background:linear-gradient(0deg,#ff9a56,#ffe259,#7CFC9A);transition:height .5s linear}
.alt-label{font-size:11px;font-weight:800;color:#fff;text-shadow:0 1px 4px rgba(0,40,80,.8)}

#stage-tip{position:absolute;left:0;right:0;bottom:max(5%,env(safe-area-inset-bottom,5%));
  text-align:center;font-size:clamp(14px,2.6vw,16px);font-weight:800;color:#fff;
  text-shadow:0 2px 8px rgba(0,40,80,.85);z-index:8;pointer-events:none;transition:opacity .3s;padding:0 16px}
#stage-tip.pulse{animation:tipPulse 1.2s ease-in-out infinite}
@keyframes tipPulse{0%,100%{transform:scale(1)}50%{transform:scale(1.08)}}

/* ---- 道具选择 ---- */
#choice-layer{position:fixed;inset:0;z-index:30;display:none;flex-direction:column;
  align-items:center;justify-content:flex-end;
  padding-bottom:max(9%,env(safe-area-inset-bottom,9%));
  background:linear-gradient(180deg,rgba(0,20,50,0) 40%,rgba(0,20,50,.55) 100%)}
#choice-layer.show{display:flex}
.choice-title{font-size:clamp(15px,2.8vw,17px);font-weight:900;color:#fff;
  text-shadow:0 2px 8px rgba(0,40,80,.9);margin-bottom:14px}
.choice-row{display:flex;gap:5vmin}
.choice-item{width:26vmin;max-width:150px;aspect-ratio:1;border-radius:18px;
  background:rgba(255,255,255,.92);border:3px solid rgba(255,220,120,.9);
  box-shadow:0 8px 22px rgba(0,30,60,.4);display:flex;align-items:center;
  justify-content:center;cursor:pointer;
  animation:choiceIn .4s cubic-bezier(.2,1.5,.4,1) both}
.choice-item:nth-child(2){animation-delay:.08s}
.choice-item img{width:82%;height:82%;object-fit:contain;pointer-events:none}
.choice-item:active{transform:scale(.93)}
@keyframes choiceIn{0%{transform:translateY(30px) scale(.6);opacity:0}100%{transform:translateY(0) scale(1);opacity:1}}

/* ---- 拆螺丝 Canvas + 燃烧遮罩 ---- */
#balloon-screw-canvas{position:fixed;inset:0;margin:auto;display:none;z-index:20;
  background:#22303e;max-width:100vw;max-height:100vh}
#balloon-screw-canvas.show{display:block}
#burn-mask{position:fixed;inset:0;z-index:15;pointer-events:none;opacity:0;
  background:radial-gradient(circle at 50% 78%,rgba(255,120,30,.85),rgba(255,60,10,.4) 40%,transparent 70%)}
#burn-mask.go{animation:burnFlash 1.7s ease-out}
@keyframes burnFlash{0%{opacity:0}18%{opacity:.9}100%{opacity:0}}

@media (orientation:landscape){
  #char{width:32vmin;max-width:240px;top:30%}
  #altitude{width:26px}
  .choice-item{width:18vmin;max-width:120px}
  #stage-tip{font-size:13px}
}
"""

JS = r"""
// =====================================================================
// 关卡配置：三处破损 = 三次「选择道具 -> 拆螺丝」循环
// 复刻攀岩包自研物理引擎，真实铁片/螺丝手感
// =====================================================================
var STAGES = [
  { choices: ['{{img_feather}}', '{{img_finger}}'],    names: ['羽毛', '指套'],
    plates: [
      { img: 'background1', cx: 375, cy: 560, w: 340, h: 130,
        holes: [{x:260,y:520},{x:490,y:520}] }
    ],
    freeHoles: [{x:375,y:700}]
  },
  { choices: ['{{img_tape}}', '{{img_rag}}'],          names: ['胶带', '破布'],
    plates: [
      { img: 'background2', cx: 300, cy: 520, w: 300, h: 110,
        holes: [{x:190,y:470},{x:410,y:470}] },
      { img: 'background2', cx: 470, cy: 660, w: 300, h: 110,
        holes: [{x:360,y:640},{x:585,y:640}] }
    ],
    freeHoles: [{x:375,y:840}]
  },
  { choices: ['{{img_schoolbag}}', '{{img_sandbag}}'], names: ['书包', '沙袋'],
    plates: [
      { img: 'background3', cx: 375, cy: 470, w: 300, h: 100,
        holes: [{x:280,y:430},{x:470,y:430}] },
      { img: 'background3', cx: 375, cy: 640, w: 260, h: 100,
        holes: [{x:295,y:600},{x:455,y:600}] },
      { img: 'background3', cx: 375, cy: 810, w: 220, h: 100,
        holes: [{x:305,y:770},{x:445,y:770}] }
    ],
    freeHoles: [{x:375,y:950}]
  }
];

var stageIdx = 0, fixedCount = 0, timeLeft = 0, timerIv = null;
App.state.total = STAGES.length;
App.state.cleared = 0;

// 扩展状态机
App.stateMachine.extend({
  idle: ['playing'],
  playing: ['choice','screw','transition','end'],
  choice: ['screw','end'],
  screw: ['transition','end'],
  transition: ['playing','end','choice'],
  end: ['playing']
});

var tip = el('stage-tip'), charBox = el('char');

// ---- Canvas 背景（DPR 感知）----
var bgCV = el('balloon-bg-canvas'), bgCtx = bgCV.getContext('2d');
var _bgImg = null;

function fitBgCanvas(){
  var W = window.innerWidth, H = window.innerHeight, dpr = window.devicePixelRatio || 1;
  bgCV.width = W * dpr; bgCV.height = H * dpr;
  bgCV.style.width = W + 'px'; bgCV.style.height = H + 'px';
  drawBg();
}
function drawBg(){
  var dpr = window.devicePixelRatio || 1, W = window.innerWidth, H = window.innerHeight;
  bgCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  bgCtx.clearRect(0, 0, W, H);
  if (_bgImg && _bgImg.complete) {
    var scale = Math.max(W / _bgImg.naturalWidth, H / _bgImg.naturalHeight);
    var iw = _bgImg.naturalWidth * scale, ih = _bgImg.naturalHeight * scale;
    bgCtx.drawImage(_bgImg, (W - iw) / 2, (H - ih) * 0.2, iw, ih);
  }
}
function setSkyBg(assetName){
  var uri = App.assets.get(assetName) || '';
  if (!uri) return;
  _bgImg = new Image(); _bgImg.decoding = 'async';
  _bgImg.onload = function(){ drawBg(); };
  _bgImg.src = uri;
}
App.preloader.preload(['bg_sky', 'bg_cloudy'], 'critical');
setSkyBg('bg_sky');
drawBg();

// ---- 高度表 + 倒计时 ----
function startTimer(){
  timeLeft = App.cfg.countdown_seconds || 30;
  updateAltitude();
  timerIv = setInterval(function(){
    if (App.stateMachine.is('end')) { clearInterval(timerIv); return; }
    timeLeft--;
    updateAltitude();
    if (timeLeft <= 0) {
      clearInterval(timerIv);
      tip.textContent = '气球坠落……';
      tip.style.opacity = '1';
      App.sound.fail();
      setTimeout(function(){ App.end('fail'); }, 800);
    }
  }, 1000);
}
function updateAltitude(){
  var total = App.cfg.countdown_seconds || 30;
  var ratio = Math.max(0, timeLeft) / total;
  el('alt-fill').style.height = (ratio * 100) + '%';
  el('alt-label').textContent = Math.round(250 + ratio * 750) + 'm';
}

// ---- 道具选择 ----
function openChoice(){
  if (App.stateMachine.is('end')) return;
  var s = STAGES[stageIdx];
  el('choice-img-0').src = s.choices[0];
  el('choice-img-1').src = s.choices[1];
  el('choice-layer').classList.add('show');
  App.stateMachine.go('choice');
  tip.style.opacity = '0';
}

var _choiceSeq = 0;
Array.prototype.forEach.call(document.querySelectorAll('.choice-item'), function(item){
  item.addEventListener('pointerdown', function(e){
    e.preventDefault();
    if (!App.stateMachine.is('choice')) return;
    App.act();
    App.sound.click();
    _choiceSeq = App.nextSeq();
    el('choice-layer').classList.remove('show');
    App.stateMachine.go('screw');
    startScrew(stageIdx, _choiceSeq);
  });
});

// =====================================================================
// 拆螺丝物理引擎（复刻攀岩包自研引擎，非 Matter.js）
// =====================================================================

var ScrewGame = (function(){
  // ---- 常量 ----
  var HOLE_R = 52;
  var SCREW_R = 70;
  var GRAVITY = 0.7;
  var MAX_VY = 30;
  var ROT_GRAV = 0.00012;
  var ROT_DAMP = 0.06;
  var MAX_OMEGA = 0.22;
  var ROT_RESTITUTION = 0.35;
  var SCREW_HIT_R = SCREW_R;

  // ---- 状态 ----
  var canvas = el('balloon-screw-canvas'), ctx = canvas.getContext('2d');
  var DESIGN_W = 750, DESIGN_H = 1334;
  var curLevel = 0, dpr = 1, scale = 1, offsetX = 0, offsetY = 0;
  var holes = [], boards = [], selected = null;
  var rafId = null, running = false, finished = false;
  var _imgs = {};

  // ---- 工具 ----
  function toX(v){ return v / 100 * DESIGN_W; }
  function toY(v){ return v / 100 * DESIGN_H; }
  function toScreen(p){ return { x: offsetX + p.x * scale, y: offsetY + p.y * scale }; }
  function toDesign(sx, sy){ return { x: (sx - offsetX) / scale, y: (sy - offsetY) / scale }; }

  // ---- 图片缓存 ----
  function getImg(key){
    if (_imgs[key]) return _imgs[key];
    var img = new Image();
    img.decoding = 'async';
    var uri = App.assets.get(key) || '';
    if (uri) img.src = uri;
    _imgs[key] = img;
    return img;
  }

  // ---- 物理变换 ----
  function rotateAround(p, pivot, angle){
    var dx = p.x - pivot.x, dy = p.y - pivot.y;
    var cos = Math.cos(angle), sin = Math.sin(angle);
    return { x: pivot.x + dx * cos - dy * sin, y: pivot.y + dx * sin + dy * cos };
  }
  function transformPoint(b, p){
    var c = { x: b.cx, y: b.cy };
    if (b.state === 'hanging' || b.state === 'falling') {
      c = rotateAround(c, b.pivot || { x: b.cx, y: b.cy }, b.angle || 0);
    }
    if (b.state === 'falling') c.y += b.dy || 0;
    return c;
  }

  // ---- 碰撞检测 ----
  function pointInPoly(px, py, poly){
    var ins = false;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      var xi = poly[i].x, yi = poly[i].y, xj = poly[j].x, yj = poly[j].y;
      if (((yi > py) !== (yj > py)) && (px < (xj - xi) * (py - yi) / (yj - yi) + xi)) ins = !ins;
    }
    return ins;
  }
  function segCircle(ax, ay, bx, by, cx, cy, r){
    var dx = bx - ax, dy = by - ay, len2 = dx * dx + dy * dy || 1;
    var t = Math.max(0, Math.min(1, ((cx - ax) * dx + (cy - ay) * dy) / len2));
    var qx = ax + t * dx, qy = ay + t * dy, ex = cx - qx, ey = cy - qy;
    return ex * ex + ey * ey <= r * r;
  }
  function polyCircle(poly, cx, cy, r){
    if (pointInPoly(cx, cy, poly)) return true;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      if (segCircle(poly[j].x, poly[j].y, poly[i].x, poly[i].y, cx, cy, r)) return true;
    }
    return false;
  }

  function boardPolyLocal(b){
    var hx = b.rectW / 2, hy = b.rectH / 2;
    return [[-hx, -hy], [hx, -hy], [hx, hy], [-hx, hy]];
  }
  function boardPolyWorld(b){
    return boardPolyLocal(b).map(function(pt){
      return transformPoint(b, { x: b.cx + pt[0], y: b.cy + pt[1] });
    });
  }
  function boardOverlapsCircle(b, sx, sy, r){
    return polyCircle(boardPolyWorld(b), sx, sy, r);
  }

  // ---- 板子状态 ----
  function remaining(b){
    return b.holeIdxs.filter(function(i){ return holes[i].screw; }).length;
  }
  function afterChange(b){
    if (b.state === 'gone' || b.state === 'falling') return;
    var rem = remaining(b);
    if (rem === 0) setFalling(b);
    else if (rem === 1 && b.holeIdxs.length > 1) {
      if (b.state !== 'hanging') setHanging(b);
    } else {
      if (b.state !== 'fixed') { b.state = 'fixed'; b.angle = 0; b.omega = 0; b.pivot = null; }
    }
  }

  function setHanging(b){
    var idx = b.holeIdxs.find(function(i){ return holes[i].screw; });
    if (idx === undefined) return;
    var h = holes[idx];
    b.pivot = { x: h.x, y: h.y };
    b.holeIdxs.forEach(function(i){
      if (i !== idx) holes[i].boards = holes[i].boards.filter(function(x){ return x !== b; });
    });
    b.holeIdxs = [idx];
    b.state = 'hanging'; b.angle = 0; b.omega = 0;
    playThud();
  }

  function setFalling(b){
    if (!b.pivot) b.pivot = { x: b.cx, y: b.cy };
    b.state = 'falling'; b.vy = 0; b.dy = 0;
    b._ignoreScrews = new Set();
    b._ignoreBoards = new Set();
    var bi = boards.indexOf(b);
    for (var i = 0; i < holes.length; i++) {
      var h = holes[i];
      if (!h.screw || h.boards.includes(b)) continue;
      if (boardOverlapsCircle(b, h.x, h.y, SCREW_HIT_R)) b._ignoreScrews.add(i);
    }
    for (var gi = 0; gi < boards.length; gi++) {
      var g = boards[gi];
      if (g === b || g.state === 'falling' || g.state === 'gone') continue;
      if (boardsOverlap(b, g)) b._ignoreBoards.add(gi);
    }
    playThud();
  }

  function boardsOverlap(a, b){
    var A = boardPolyWorld(a), B = boardPolyWorld(b);
    for (var i = 0; i < A.length; i++) {
      var a1 = A[i], a2 = A[(i + 1) % A.length];
      for (var j = 0; j < B.length; j++) {
        var b1 = B[j], b2 = B[(j + 1) % B.length];
        if (segSeg(a1, a2, b1, b2)) return true;
      }
    }
    return pointInPoly(A[0].x, A[0].y, B) || pointInPoly(B[0].x, B[0].y, A);
  }
  function cross3(o, a, b){ return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x); }
  function segSeg(a, b, c, d){
    var d1 = cross3(c, d, a), d2 = cross3(c, d, b), d3 = cross3(a, b, c), d4 = cross3(a, b, d);
    return ((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0));
  }

  // ---- 物理步进 ----
  function step(){
    for (var bi = 0; bi < boards.length; bi++) {
      var b = boards[bi];
      if (b.state === 'hanging') {
        var c = rotateAround({ x: b.cx, y: b.cy }, b.pivot, b.angle);
        var al = ROT_GRAV * (c.x - b.pivot.x) - ROT_DAMP * b.omega;
        b.omega += al;
        if (b.omega > MAX_OMEGA) b.omega = MAX_OMEGA;
        if (b.omega < -MAX_OMEGA) b.omega = -MAX_OMEGA;
        var pa = b.angle;
        b.angle += b.omega;
        if (boardHitsAnyScrew(b) || boardHitsAnyBoard(b)) {
          b.angle = pa;
          b.omega = -b.omega * ROT_RESTITUTION;
        }
      } else if (b.state === 'falling') {
        b.vy = Math.min(b.vy + GRAVITY, MAX_VY);
        b.dy += b.vy;
        var cc = transformPoint(b, { x: b.cx, y: b.cy });
        if (cc.y - b.rectH / 2 > DESIGN_H + 250) {
          b.state = 'gone';
          b.holeIdxs.forEach(function(i){
            holes[i].boards = holes[i].boards.filter(function(x){ return x !== b; });
            holes[i].screw = false;
          });
          checkWin();
        }
      }
    }
    checkDeadlock();
  }

  function boardHitsAnyScrew(b){
    var bi = boards.indexOf(b), ig = b._ignoreScrews;
    for (var i = 0; i < holes.length; i++) {
      var h = holes[i];
      if (!h.screw || h.boards.includes(b)) continue;
      if (ig && ig.has(i)) continue;
      if (boardOverlapsCircle(b, h.x, h.y, SCREW_HIT_R)) return true;
    }
    return false;
  }
  function boardHitsAnyBoard(b){
    var ig = b._ignoreBoards;
    for (var gi = 0; gi < boards.length; gi++) {
      var g = boards[gi];
      if (g === b || g.state === 'falling' || g.state === 'gone') continue;
      if (ig && ig.has(gi)) continue;
      if (boardsOverlap(b, g)) return true;
    }
    return false;
  }

  // ---- 死锁检测 ----
  function isPlaceable(idx){
    var h = holes[idx];
    if (h.screw) return false;
    for (var bi = 0; bi < h.boards.length; bi++) {
      var ob = h.boards[bi];
      if (!ob || ob.state === 'falling' || ob.state === 'gone') return false;
    }
    return !isCoveredByOther(idx);
  }
  function isCoveredByOther(idx){
    var h = holes[idx];
    for (var bi = 0; bi < boards.length; bi++) {
      if (h.boards.includes(boards[bi])) continue;
      var b = boards[bi];
      if (b.state === 'gone') continue;
      var c = transformPoint(b, { x: b.cx, y: b.cy });
      if (Math.abs(h.x - c.x) <= b.rectW / 2 && Math.abs(h.y - c.y) <= b.rectH / 2) return true;
    }
    return false;
  }
  function checkDeadlock(){
    if (!running || curLevel === 0) return;
    for (var bi = 0; bi < boards.length; bi++) {
      if (boards[bi].state === 'falling') return;
    }
    if (boards.every(function(b){ return b.state === 'gone'; })) return;
    for (var i = 0; i < holes.length; i++) {
      if (isPlaceable(i)) return;
    }
    finish(false);
  }

  function checkWin(){
    if (boards.every(function(b){ return b.state === 'gone'; })) finish(true);
  }

  // ---- 音效 ----
  var audioCtx = null;
  function playThud(){
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      var o = audioCtx.createOscillator(), g = audioCtx.createGain();
      o.type = 'sine';
      o.frequency.setValueAtTime(170, audioCtx.currentTime);
      o.frequency.exponentialRampToValueAtTime(42, audioCtx.currentTime + 0.25);
      g.gain.setValueAtTime(0.4, audioCtx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.3);
      o.connect(g); g.connect(audioCtx.destination);
      o.start(); o.stop(audioCtx.currentTime + 0.3);
    } catch(e){}
  }

  // ---- 构建关卡 ----
  function buildLevel(level){
    var cfg = STAGES[level];
    holes = []; boards = []; selected = null;

    // 收集所有孔位（板子上的 + 备用孔）
    var holeMap = {};
    function addHole(x, y, isFree){
      var key = Math.round(x) + ',' + Math.round(y);
      if (holeMap[key] !== undefined) return holeMap[key];
      var h = { x: x, y: y, screw: !isFree, boards: [] };
      holes.push(h);
      holeMap[key] = holes.length - 1;
      return holes.length - 1;
    }

    // 板子上的孔
    cfg.plates.forEach(function(p, pi){
      p.holes.forEach(function(hh){
        var idx = addHole(hh.x, hh.y, false);
        holes[idx].boards.push(pi);
      });
    });

    // 备用孔
    (cfg.freeHoles || []).forEach(function(fh){
      addHole(fh.x, fh.y, true);
    });

    // 构建板子
    cfg.plates.forEach(function(p, pi){
      var board = {
        cx: p.cx, cy: p.cy, rectW: p.w, rectH: p.h,
        angle: 0, omega: 0, vy: 0, dy: 0, pivot: null,
        state: 'fixed', img: p.img,
        holeIdxs: []
      };
      // 找属于这个板子的孔
      holes.forEach(function(h, hi){
        if (h.boards.includes(pi)) board.holeIdxs.push(hi);
      });
      boards.push(board);
    });
  }

  // ---- 渲染 ----
  function computeView(){
    var W = canvas.clientWidth, H = canvas.clientHeight;
    scale = Math.min(W / DESIGN_W, H / DESIGN_H);
    offsetX = (W - DESIGN_W * scale) / 2;
    offsetY = (H - DESIGN_H * scale) / 2;
    dpr = window.devicePixelRatio || 1;
  }

  function drawBoard(b){
    if (b.state === 'gone') return;
    var im = getImg(b.img);
    if (!im || !im.complete || !im.naturalWidth) return;
    var c = transformPoint(b, { x: b.cx, y: b.cy });
    var s = toScreen(c);
    var w = b.rectW * scale, h = b.rectH * scale;
    ctx.save();
    ctx.translate(s.x, s.y);
    if (b.angle) ctx.rotate(b.angle);
    ctx.drawImage(im, -w / 2, -h / 2, w, h);
    ctx.restore();
  }

  function drawScrew(h, idx){
    if (!h.screw) return;
    var sel = (idx === selected);
    var im = getImg(sel ? 'screwflow' : 'screw');
    if (!im || !im.complete || !im.naturalWidth) return;
    var p = holePos(idx);
    var s = toScreen(p);
    var d = SCREW_R * scale;
    ctx.drawImage(im, s.x - d, s.y - d, d * 2, d * 2);
  }

  function holePos(idx){
    var h = holes[idx];
    return { x: h.x, y: h.y };
  }

  function render(){
    if (!running) return;
    computeView();
    step();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var W = canvas.clientWidth, H = canvas.clientHeight;
    ctx.clearRect(0, 0, W, H);

    // 背景
    var bg = getImg('background' + (curLevel + 1));
    if (bg && bg.complete && bg.naturalWidth) {
      ctx.drawImage(bg, offsetX, offsetY, DESIGN_W * scale, DESIGN_H * scale);
    }

    // 孔位（空孔）
    holes.forEach(function(h, idx){
      if (h.screw) return;
      var p = toScreen(h);
      var r = HOLE_R * scale * 0.4;
      ctx.beginPath();
      ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0,0,0,.5)';
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = 'rgba(255,255,255,.6)';
      ctx.stroke();
    });

    // 板子
    boards.forEach(drawBoard);

    // 螺丝
    holes.forEach(function(h, idx){ drawScrew(h, idx); });

    // 选中提示
    if (selected !== null) {
      var p = toScreen(holePos(selected));
      ctx.beginPath();
      ctx.arc(p.x, p.y - 30 * scale, SCREW_R * scale * 0.5, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,210,90,.35)';
      ctx.fill();
    }

    rafId = requestAnimationFrame(render);
  }

  // ---- 输入 ----
  function pointFromEvent(e){
    var r = canvas.getBoundingClientRect();
    var cx = (e.changedTouches && e.changedTouches[0]) ? e.changedTouches[0].clientX : e.clientX;
    var cy = (e.changedTouches && e.changedTouches[0]) ? e.changedTouches[0].clientY : e.clientY;
    return toDesign(cx - r.left, cy - r.top);
  }
  function hitScrew(p){
    for (var i = holes.length - 1; i >= 0; i--) {
      var h = holes[i];
      if (!h.screw) continue;
      var pt = holePos(i);
      if (Math.hypot(p.x - pt.x, p.y - pt.y) <= SCREW_R + 10) return i;
    }
    return -1;
  }
  function hitEmptyHole(p){
    for (var i = holes.length - 1; i >= 0; i--) {
      if (holes[i].screw) continue;
      var h = holes[i];
      if (Math.hypot(p.x - h.x, p.y - h.y) <= HOLE_R + 8) return i;
    }
    return -1;
  }

  function onTap(e){
    if (!running || finished) return;
    e.preventDefault();
    App.act();
    var p = pointFromEvent(e);

    if (selected !== null) {
      var sH = hitScrew(p);
      if (sH === selected) { selected = null; App.sound.click(); return; }
      var hH = hitEmptyHole(p);
      if (hH >= 0 && isPlaceable(hH)) {
        var fromB = holes[selected].boards.slice();
        var toB = holes[hH].boards.slice();
        holes[selected].screw = false;
        holes[hH].screw = true;
        selected = null;
        App.sound.click();
        fromB.forEach(function(bi){ if (boards[bi]) afterChange(boards[bi]); });
        toB.forEach(function(bi){ if (boards[bi]) afterChange(boards[bi]); });
      }
      return;
    }

    var sH2 = hitScrew(p);
    if (sH2 >= 0) { selected = sH2; App.sound.click(); }
  }

  // 触控去重
  var ct = false;
  canvas.addEventListener('touchstart', function(){ ct = true; }, { passive: true });
  canvas.addEventListener('touchend', function(e){ if (ct) { ct = false; onTap(e); } }, { passive: false });
  canvas.addEventListener('click', function(e){ if (!ct) onTap(e); });

  // ---- 生命周期 ----
  function start(level){
    curLevel = level;
    finished = false; selected = null;
    canvas.classList.add('show');

    var bg = getImg('background' + (level + 1));
    function begin(){
      if (finished) return;
      resize();
      buildLevel(level);
      running = true;
      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(render);
    }

    if (bg.complete && bg.naturalWidth) requestAnimationFrame(begin);
    else {
      bg.onload = function(){ requestAnimationFrame(begin); };
      setTimeout(function(){ if (!running && !finished) requestAnimationFrame(begin); }, 600);
    }
  }

  function finish(win){
    if (finished) return;
    finished = true; running = false; selected = null;
    if (rafId) { cancelAnimationFrame(rafId); rafId = null; }

    setTimeout(function(){
      if (win) { onScrewWin(); }
      else { onScrewFail(); }
    }, 1000);
  }

  function resize(){
    computeView();
  }

  function cleanup(){
    running = false; finished = false; selected = null;
    if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
    canvas.classList.remove('show');
  }

  return { start: start, finish: finish, cleanup: cleanup };
})();

// ---- 螺丝游戏回调 ----
function onScrewWin(){
  var mySeq = App.nextSeq();
  track('balloon_screw_win_' + (fixedCount + 1));
  burnFix(mySeq);
}

function onScrewFail(){
  tip.textContent = '螺丝卡死了……';
  tip.style.opacity = '1';
  App.sound.fail();
  setTimeout(function(){ App.end('fail'); }, 800);
}

// ---- 燃烧溶解转场 ----
function burnFix(seq){
  App.sound.burn();
  var bm = el('burn-mask');
  bm.classList.remove('go');
  void bm.offsetWidth;
  bm.classList.add('go');
  charBox.classList.add('fixed');
  fixedCount++;
  App.state.cleared = fixedCount;
  App.emit('cleared');
  App.stateMachine.go('transition');
  track('balloon_stage_fixed_' + fixedCount);

  setTimeout(function(){
    if (!App.isLatest(seq)) return;
    charBox.classList.remove('fixed');
    setSkyBg('bg_cloudy');
    drawBg();

    if (fixedCount >= STAGES.length) {
      clearInterval(timerIv);
      tip.textContent = '救援成功！';
      tip.style.opacity = '1';
      App.sound.victory();
      setTimeout(function(){ App.end('success'); }, 900);
    } else {
      stageIdx++;
      App.stateMachine.go('playing');
      openChoice();
    }
  }, 1700);
}

// ---- 入口 ----
on('start', function(){
  App.stateMachine.go('playing');
  tip.textContent = '点击气球，开始救援！';
  tip.classList.add('pulse');
  startTimer();
  fitBgCanvas();

  el('balloon-stage').addEventListener('pointerdown', function once(){
    el('balloon-stage').removeEventListener('pointerdown', once);
    tip.classList.remove('pulse');
    _choiceSeq = App.nextSeq();
    openChoice();
  });
});

on('end', function(){
  clearInterval(timerIv);
  App.stateMachine.go('end');
});

on('layout', function(){
  fitBgCanvas();
  drawBg();
});

App.preloader.preload(['background1','background2','background3'], 'normal');
"""
