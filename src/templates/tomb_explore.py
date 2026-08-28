# -*- coding: utf-8 -*-
"""古墓探测寻宝 · 量产级 v2（tomb_explore）。

双阶段：扫描（Dom→Canvas 升级）/ 拆螺丝物理（Matter.js + DPR 感知）。
集成 App.stateMachine / App.sound / App.bindTap / App.deadlock / App.nextSeq。
"""

HTML = """
<div id="scan-stage">
  <canvas id="scan-canvas"></canvas>
  <div id="flash"></div>
  <div id="scan-tip">拖动探测仪扫描，点击石板挖掘</div>
</div>

<canvas id="screw-canvas" width="750" height="1334"></canvas>

<div id="zombie-layer">
  <div class="z-overlay"></div>
  <img src="{{img_zombie}}" alt="">
  <div class="z-text">ZOMBIE ATTACK!</div>
</div>
"""

CSS = """
/* ---- 扫描阶段 ---- */
#scan-stage{position:absolute;inset:0;overflow:hidden;touch-action:none}
#scan-canvas{display:block;width:100%;height:100%;touch-action:none}
#scan-tip{position:absolute;left:0;right:0;bottom:max(4.5%,env(safe-area-inset-bottom,4.5%));
  text-align:center;font-size:clamp(13px,2.6vw,15px);font-weight:800;
  color:#ffe9b8;text-shadow:0 2px 6px #000;z-index:7;pointer-events:none;
  transition:opacity .4s;padding:0 16px}
#flash{position:fixed;inset:0;background:#fff;opacity:0;pointer-events:none;z-index:50}
#flash.go{animation:flashA .35s ease-out}
@keyframes flashA{0%{opacity:0}25%{opacity:.92}100%{opacity:0}}

/* ---- 拆螺丝 Canvas ---- */
#screw-canvas{position:fixed;inset:0;margin:auto;display:none;z-index:20;background:#171009;
  max-width:100vw;max-height:100vh}
#screw-canvas.show{display:block}

/* ---- 僵尸扑屏 ---- */
#zombie-layer{position:fixed;inset:0;z-index:55;display:none;flex-direction:column;
  align-items:center;justify-content:center}
.z-overlay{position:absolute;inset:0;background:rgba(30,0,0,.6);backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}
#zombie-layer.show{display:flex}
#zombie-layer img{position:relative;z-index:2;width:72%;max-width:420px;
  animation:zjump .6s cubic-bezier(.2,1.6,.4,1) both;
  filter:drop-shadow(0 12px 30px rgba(0,0,0,.85))}
.z-text{position:relative;z-index:2;font-size:clamp(28px,6vw,34px);font-weight:900;
  color:#ff5148;text-shadow:0 0 24px rgba(255,40,30,.8);margin-top:12px;
  animation:zjump .7s .1s both}
@keyframes zjump{0%{transform:scale(.2);opacity:0}70%{transform:scale(1.14)}100%{transform:scale(1);opacity:1}}

/* ---- 金币飞行 ---- */
.coin-fly{position:fixed;z-index:70;width:30px;height:30px;pointer-events:none;
  transition:all .8s cubic-bezier(.3,.7,.4,1);
  filter:drop-shadow(0 3px 6px rgba(0,0,0,.5))}
.gold-pop{position:fixed;z-index:70;font-size:22px;font-weight:900;color:#ffd76a;
  text-shadow:0 2px 6px #000;pointer-events:none;
  animation:goldUp 1s ease-out both}
@keyframes goldUp{0%{transform:translateY(0) scale(.6);opacity:0}25%{opacity:1}
  100%{transform:translateY(-90px) scale(1.3);opacity:0}}

/* 横竖屏适配 */
@media (orientation:landscape){
  #scan-tip{font-size:12px;bottom:3%}
  #zombie-layer img{width:50%;max-width:340px}
}
"""

JS = r"""
{{physics_js}}

// =====================================================================
// 数值表 + 布局
// =====================================================================
var TYPES = {
  shoe:   { img: App.assets.get('junk_shoe')   || '{{img_junk_shoe}}',   value: -1,    kind: 'coin',   name: '臭鞋',   coins: 1 },
  jewel:  { img: App.assets.get('relic_jewel')  || '{{img_relic_jewel}}',  value: 1111,  kind: 'coin',   name: '珠宝',   coins: 5 },
  vase:   { img: App.assets.get('relic_vase')   || '{{img_relic_vase}}',   value: 10000, kind: 'coin',   name: '青花瓷', coins: 8 },
  chestW: { img: App.assets.get('chest_wood')   || '{{img_chest_wood}}',   value: 11111, kind: 'chest',  name: '木宝箱', coins: 10, lvl: 0 },
  chestI: { img: App.assets.get('chest_iron')   || '{{img_chest_iron}}',   value: 22222, kind: 'chest',  name: '铁宝箱', coins: 12, lvl: 1 },
  chestG: { img: App.assets.get('chest_gold')   || '{{img_chest_gold}}',   value: 33333, kind: 'chest',  name: '金宝箱', coins: 14, lvl: 2 },
  zombie: { img: App.assets.get('zombie')       || '{{img_zombie}}',       value: 0,     kind: 'zombie', name: '僵尸',   coins: 0 }
};
var GOAL = 99999;
var LAYOUT = [
  'zombie','chestI','vase',  'jewel',
  'jewel', 'shoe',  'zombie','shoe',
  'zombie','vase',  'jewel', 'chestG',
  'chestW','shoe',  'vase',  'zombie'
];

// 归一化网格（竖屏/横屏各自一套，参考投放包双坐标策略）
var GRID_V = {
  cols: [0.1354, 0.3269, 0.5184, 0.7099], rows: [0.1787, 0.3293, 0.4800, 0.6307],
  cw: 0.1644, ch: 0.1133
};
var GRID_H = {
  cols: [0.3231, 0.4419, 0.5606, 0.6794], rows: [0.1424, 0.2624, 0.3823, 0.5023],
  cw: 0.1022, ch: 0.0903
};

var cells = [], gold = 0, chestsDone = 0, steppedShoe = false;
var dugCells = [];  // 已挖格子的 Canvas 坐标，供重绘遮罩

App.state.total = 3; App.state.cleared = 0; App.state.gold = 0;

// 扩展状态机：新增玩法专属状态
App.stateMachine.extend({
  idle: ['scan'],
  playing: ['scan','screw','zombie','end'],
  scan: ['screw','zombie','end'],
  screw: ['scan','end'],
  zombie: ['end'],
  transition: ['scan','screw','end']
});

function curGrid(){ return App.isLandscape() ? GRID_H : GRID_V; }

// =====================================================================
// Canvas 扫描阶段渲染
// =====================================================================
var scanCV = el('scan-canvas'), sctx = scanCV.getContext('2d');
var scanW = 750, scanH = 1334;  // 设计分辨率

// 预加载所有素材图片对象（加载完成后自动重绘）
var _imgs = {};
(function preloadAll(){
  var names = ['bg_tomb','cover_tomb','detector','junk_shoe','relic_jewel','relic_vase',
               'chest_wood','chest_iron','chest_gold','zombie','coin'];
  names.forEach(function(k){
    _imgs[k] = new Image();
    var uri = App.assets.get(k) || '';
    if (uri) {
      _imgs[k].src = uri;
      _imgs[k].decoding = 'async';
      _imgs[k].onload = function(){
        if (App.stateMachine.is('scan')) drawScan();
      };
    }
  });
})();

// 探测仪位置（百分比）
var sx = 0.5, sy = 0.62, dragging = false, lastBeep = 0, tip = el('scan-tip');

function nearestUndug(px, py){
  var best = 1e9, g = curGrid(), W = scanW, H = scanH;
  cells.forEach(function(c){
    if (c.dug) return;
    var cx = (g.cols[c.col] + g.cw / 2) * W, cy = (g.rows[c.row] + g.ch / 2) * H;
    var d = Math.hypot(cx - px, cy - py);
    if (d < best) best = d;
  });
  return best;
}

function fitScanCanvas(){
  var W = window.innerWidth, H = window.innerHeight;
  // DPR 感知
  scanCV.width = scanW * (window.devicePixelRatio || 1);
  scanCV.height = scanH * (window.devicePixelRatio || 1);
  scanCV.style.width = W + 'px';
  scanCV.style.height = H + 'px';
}

function drawScan(){
  var W = scanW, H = scanH, dpr = window.devicePixelRatio || 1;
  sctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  sctx.clearRect(0, 0, W, H);

  // 1. 墓墙底图
  if (_imgs.bg_tomb && _imgs.bg_tomb.complete) {
    sctx.drawImage(_imgs.bg_tomb, 0, 0, W, H);
  } else {
    var g0 = sctx.createLinearGradient(0, 0, 0, H);
    g0.addColorStop(0, '#3a2a16'); g0.addColorStop(1, '#0f0903');
    sctx.fillStyle = g0; sctx.fillRect(0, 0, W, H);
  }

  var gw = curGrid();

  // 2. 宝藏精灵（在遮挡层下面，挖开后在遮罩孔中透出）
  cells.forEach(function(c){
    if (!c.dug) return;
    var cx = (gw.cols[c.col] + gw.cw / 2) * W, cy = (gw.rows[c.row] + gw.ch / 2) * H;
    var img = _imgs[c.key];
    if (img && img.complete) {
      var iw = gw.cw * W * 0.85, ih = gw.ch * H * 0.85;
      sctx.drawImage(img, cx - iw / 2, cy - ih / 2, iw, ih);
    }
  });

  // 3. 石板遮挡层 + mask 挖洞
  if (_imgs.cover_tomb && _imgs.cover_tomb.complete) {
    // 先把已挖洞区域从遮挡层 clip 掉
    sctx.save();
    sctx.beginPath();
    // 全屏 rect，然后 subtract 挖洞 circle
    sctx.rect(0, 0, W, H);
    dugCells.forEach(function(h){
      sctx.arc(h.cx, h.cy, h.rx, 0, Math.PI * 2, true);
    });
    // 探测仪透视圈
    var px = sx * W, py = sy * H;
    var rx = Math.max(70, W * 0.13), ry = Math.max(70, H * 0.075);
    sctx.arc(px, py, Math.max(rx, ry), 0, Math.PI * 2, true);
    sctx.clip();
    sctx.drawImage(_imgs.cover_tomb, 0, 0, W, H);
    sctx.restore();

    // 透视圈边缘发光
    sctx.beginPath();
    sctx.arc(px, py, Math.max(rx, ry), 0, Math.PI * 2);
    sctx.lineWidth = 3;
    sctx.strokeStyle = 'rgba(255,233,184,.45)';
    sctx.stroke();
  }

  // 4. 探测仪
  if (_imgs.detector && _imgs.detector.complete) {
    var iw2 = W * 0.16, ih2 = iw2 * (_imgs.detector.naturalHeight / _imgs.detector.naturalWidth || 1.3);
    sctx.drawImage(_imgs.detector, sx * W - iw2 / 2, sy * H - ih2 * 0.8, iw2, ih2);
  }
}

function moveScanner(px, py){
  var W = scanW, H = scanH;
  sx = Math.max(0, Math.min(1, px / W)); sy = Math.max(0, Math.min(1, py / H));
  var rx = Math.max(70, W * 0.13), ry = Math.max(70, H * 0.075);
  tip.style.opacity = '0';

  var d = nearestUndug(px, py);
  var hot = d < Math.max(rx, ry) * 1.5;
  var now = Date.now();
  if (hot && now - lastBeep > Math.max(130, d * 2.4)) {
    lastBeep = now;
    App.sound.radar(d);  // 共享音效引擎
  }

  drawScan();
}

// 初始化格子坐标
(function buildCells(){
  LAYOUT.forEach(function(key, i){
    cells.push({ key: key, type: TYPES[key], dug: false, col: i % 4, row: Math.floor(i / 4) });
  });
})();

function cellAt(px, py){
  var g = curGrid(), W = scanW, H = scanH;
  for (var i = 0; i < cells.length; i++) {
    var c = cells[i];
    var x = g.cols[c.col] * W, y = g.rows[c.row] * H, w = g.cw * W, h = g.ch * H;
    if (px >= x && px <= x + w && py >= y && py <= y + h) return c;
  }
  return null;
}

// 转换屏幕坐标到设计分辨率
function screenToCanvas(ex, ey){
  var r = scanCV.getBoundingClientRect();
  return { x: (ex - r.left) * (scanW / r.width), y: (ey - r.top) * (scanH / r.height) };
}

// =====================================================================
// 交互：扫描阶段
// =====================================================================
var flash = el('flash');
function doFlash(){
  flash.classList.remove('go'); void flash.offsetWidth; flash.classList.add('go');
}
function goldPop(text, x, y){
  var d = document.createElement('div'); d.className = 'gold-pop';
  d.textContent = text;
  d.style.left = (x * window.innerWidth / scanW) + 'px';
  d.style.top = (y * window.innerHeight / scanH) + 'px';
  document.body.appendChild(d);
  setTimeout(function(){ d.remove(); }, 1000);
}
function flyCoins(n, x, y){
  for (var i = 0; i < Math.min(n, 8); i++) {
    (function(i){
      var c = document.createElement('img');
      c.src = App.assets.get('coin') || '{{img_coin}}';
      c.className = 'coin-fly';
      c.style.left = (x * window.innerWidth / scanW) + 'px';
      c.style.top = (y * window.innerHeight / scanH) + 'px';
      document.body.appendChild(c);
      setTimeout(function(){
        c.style.left = (window.innerWidth - 70) + 'px';
        c.style.top = Math.max(18, parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--safe-top') || '18')) + 'px';
        c.style.opacity = '0.2';
      }, 40 + i * 90);
      setTimeout(function(){ c.remove(); }, 1000 + i * 90);
    })(i);
  }
}
function addGold(v, x, y){
  gold += v;
  App.state.gold = gold;
  App.emit('gold');
  goldPop(v > 0 ? '+' + v : '' + v, x, y);
  if (v > 0) flyCoins(Math.min(8, 2 + Math.floor(v / 3000)), x, y);
}

function dig(c, canvasX, canvasY){
  if (c.dug) return;
  c.dug = true;
  var cx = canvasX || 0, cy = canvasY || 0;
  dugCells.push({ cx: cx, cy: cy, rx: scanW * curGrid().cw * 0.52, ry: scanH * curGrid().ch * 0.52 });
  doFlash();
  track('dig_' + c.key);
  drawScan();

  var t = c.type;
  if (t.kind === 'zombie') { zombieAttack(); return; }
  if (t.kind === 'chest') {
    // 宝箱 → 拆螺丝阶段，使用序列号防止过时回调
    var mySeq = App.nextSeq();
    setTimeout(function(){
      if (!App.isLatest(mySeq)) return;
      startScrew(t.lvl, t, cx, cy, c);
    }, 500);
    return;
  }
  // 直接结算
  if (t.value < 0) steppedShoe = true;
  setTimeout(function(){ addGold(t.value, cx, cy); }, 450);
}

function zombieAttack(){
  App.stateMachine.go('zombie');
  doFlash();
  App.emit('zombie');
  track('zombie_hit');
  el('zombie-layer').classList.add('show');
  App.sound.fail();
  setTimeout(function(){
    el('zombie-layer').classList.remove('show');
    App.end('fail');
  }, 1500);
}

function checkFinalClear(){
  if (App.stateMachine.is('end')) return;
  if (gold >= GOAL && chestsDone >= 3) {
    App.stateMachine.go('end');
    track('final_clear');
    App.sound.victory();
    setTimeout(function(){ App.end('success'); }, 900);
  } else if (cells.every(function(c){ return c.dug; }) && gold < GOAL) {
    App.stateMachine.go('end');
    setTimeout(function(){ App.end('fail'); }, 900);
  }
}

// 扫描阶段指针事件
scanCV.addEventListener('pointerdown', function(e){
  if (!App.stateMachine.is('scan')) return;
  App.act();
  dragging = true;
  var pos = screenToCanvas(e.clientX, e.clientY);
  moveScanner(pos.x, pos.y);
});
scanCV.addEventListener('pointermove', function(e){
  if (!dragging || !App.stateMachine.is('scan')) return;
  var pos = screenToCanvas(e.clientX, e.clientY);
  moveScanner(pos.x, pos.y);
});
scanCV.addEventListener('pointerup', function(e){
  dragging = false;
  if (!App.stateMachine.is('scan')) return;
  var pos = screenToCanvas(e.clientX, e.clientY);
  var c = cellAt(pos.x, pos.y);
  if (c) dig(c, pos.x, pos.y);
});

// =====================================================================
// 阶段二：拆螺丝物理解谜（Matter.js + DPR 感知 + 死锁检测）
// =====================================================================
var LEVELS = [
  { gravity: 15,
    holes: [ {x: 275, y: 640}, {x: 475, y: 640} ],
    parkHoles: [ {x: 375, y: 900} ],
    plates: [ { x: 375, y: 560, w: 300, h: 130, bind: [0, 1] } ]
  },
  { gravity: 8,
    holes: [ {x: 235, y: 560}, {x: 515, y: 560}, {x: 375, y: 700} ],
    parkHoles: [ {x: 180, y: 920}, {x: 570, y: 920} ],
    plates: [ { x: 375, y: 560, w: 360, h: 130, bind: [0, 1, 2] } ]
  },
  { gravity: 11,
    holes: [ {x: 235, y: 480}, {x: 515, y: 480}, {x: 235, y: 720}, {x: 515, y: 720} ],
    parkHoles: [ {x: 160, y: 980}, {x: 375, y: 1050}, {x: 590, y: 980} ],
    plates: [ { x: 375, y: 600, w: 400, h: 300, bind: [0, 1, 2, 3] } ]
  }
];

var screwCV = el('screw-canvas'), scrctx = screwCV.getContext('2d');
var sEngine = null, sWorld = null, sLevel = null;
var sPlates = [], sScrews = [], sHoles = [];
var sRunning = false, sSelected = null, sPendingChest = null;
var SW = 750, SH = 1334;

function fitScrewCanvas(){
  var W = window.innerWidth, H = window.innerHeight;
  var scale = Math.min(W / SW, H / SH);
  if (W > H) scale = (H / SH) * 1.5;
  var dpr = window.devicePixelRatio || 1;
  screwCV.width = SW * dpr;
  screwCV.height = SH * dpr;
  screwCV.style.width = (SW * scale) + 'px';
  screwCV.style.height = (SH * scale) + 'px';
  // 同步 CSS max 约束
  screwCV.style.maxWidth = (100 * W / window.innerWidth) + 'vw';
  screwCV.style.maxHeight = (100 * H / window.innerHeight) + 'vh';
}

function startScrew(lvl, chestType, cx, cy, cell){
  sPendingChest = { type: chestType, cx: cx, cy: cy, cell: cell };
  App.stateMachine.go('screw');
  el('scan-stage').style.display = 'none';
  screwCV.classList.add('show');
  fitScrewCanvas();
  loadScrewLevel(lvl);
  track('screw_start_' + lvl);
}

function loadScrewLevel(lvl){
  sLevel = LEVELS[lvl]; sLevel.idx = lvl;
  sEngine = Matter.Engine.create();
  sEngine.gravity.x = 0; sEngine.gravity.y = sLevel.gravity;
  sEngine.positionIterations = 20; sEngine.velocityIterations = 12;
  sEngine.timing.timeScale = 0.9;
  sWorld = sEngine.world;
  sPlates = []; sScrews = []; sHoles = []; sSelected = null;

  sLevel.holes.forEach(function(h, i){
    sHoles.push({ id: 'h' + i, x: h.x, y: h.y, r: 26, occupied: true, park: false });
  });
  sLevel.parkHoles.forEach(function(h, i){
    sHoles.push({ id: 'p' + i, x: h.x, y: h.y, r: 26, occupied: false, park: true });
  });

  sLevel.plates.forEach(function(p, pi){
    var body = Matter.Bodies.rectangle(p.x, p.y, p.w, p.h, {
      isStatic: true, friction: 0.5, restitution: 0, label: 'plate'
    });
    Matter.World.add(sWorld, body);
    sPlates.push({ id: 'pl' + pi, x: p.x, y: p.y, w: p.w, h: p.h,
                   body: body, alive: true, free: false, bind: p.bind, stuckFrames: 0 });
  });

  sLevel.plates.forEach(function(p, pi){
    p.bind.forEach(function(hi){
      var h = sHoles[hi];
      var body = Matter.Bodies.circle(h.x, h.y, 14, { isStatic: true, isSensor: true, label: 'screw' });
      Matter.World.add(sWorld, body);
      var cons = Matter.Constraint.create({
        pointA: { x: h.x, y: h.y }, bodyB: sPlates[pi].body, length: 0, stiffness: 1
      });
      Matter.World.add(sWorld, cons);
      sScrews.push({ holeId: h.id, x: h.x, y: h.y, plateId: sPlates[pi].id,
                     body: body, constraint: cons, alive: true });
    });
  });

  sRunning = true;
  requestAnimationFrame(screwLoop);
}

function holeFree(h){
  if (h.occupied) return false;
  for (var i = 0; i < sPlates.length; i++) {
    var p = sPlates[i];
    if (!p.alive || p.free) continue;
    if (h.x > p.x - p.w/2 && h.x < p.x + p.w/2 && h.y > p.y - p.h/2 && h.y < p.y + p.h/2) return false;
  }
  return true;
}

function screwPos(e){
  var r = screwCV.getBoundingClientRect();
  return { x: (e.clientX - r.left) * (SW / r.width), y: (e.clientY - r.top) * (SH / r.height) };
}

function pullScrew(s){
  var h = sHoles.find(function(x){ return x.id === s.holeId; });
  if (h) h.occupied = false;
  if (s.body) { Matter.World.remove(sWorld, s.body); s.body = null; }
  if (s.constraint) { Matter.World.remove(sWorld, s.constraint); s.constraint = null; }
  s.alive = false;
  sSelected = s;
  App.sound.click();
  track('screw_pull');
  var owner = sPlates.find(function(p){ return p.id === s.plateId; });
  if (owner) checkPlateRelease(owner);
}

function placeScrew(h){
  var s = sSelected;
  h.occupied = true;
  s.holeId = h.id; s.x = h.x; s.y = h.y; s.alive = true;
  sSelected = null;
  var inPlate = !h.park;
  s.body = Matter.Bodies.circle(h.x, h.y, 14, {
    isStatic: true, isSensor: inPlate, label: 'screw',
    collisionFilter: { category: 0x0002, mask: inPlate ? 0x0000 : 0x0001 }
  });
  Matter.World.add(sWorld, s.body);
  if (inPlate) {
    var plate = sPlates.find(function(p){ return p.id === s.plateId; });
    if (plate && plate.alive && !plate.free) {
      s.constraint = Matter.Constraint.create({
        pointA: { x: h.x, y: h.y }, bodyB: plate.body, length: 0, stiffness: 1
      });
      Matter.World.add(sWorld, s.constraint);
    }
  }
  App.sound.click();
  var owner = sPlates.find(function(p){ return p.id === s.plateId; });
  if (owner) checkPlateRelease(owner);
  track('screw_place');
}

function checkPlateRelease(plate){
  if (!plate.alive || plate.free) return;
  var left = sScrews.filter(function(s){ return s.plateId === plate.id && s.alive && s.constraint; });
  if (left.length === 0) {
    plate.free = true;
    Matter.Body.setStatic(plate.body, false);
    Matter.Body.setVelocity(plate.body, { x: 0, y: 2 });
    App.sound.thud();
    track('plate_fall');
  }
}

// ---- 触控：使用 App.bindTap 去重 ----
App.bindTap(screwCV, function(e){
  if (!sRunning) return;
  App.act();
  var pos = screwPos(e);
  // 优先点中螺丝
  for (var i = 0; i < sScrews.length; i++) {
    var s = sScrews[i];
    if (!s.alive) continue;
    if (Math.hypot(s.x - pos.x, s.y - pos.y) < 46) { pullScrew(s); return; }
  }
  // 手中螺丝 → 放空孔
  if (sSelected) {
    for (var j = 0; j < sHoles.length; j++) {
      var h = sHoles[j];
      if (Math.hypot(h.x - pos.x, h.y - pos.y) < 46 && holeFree(h)) { placeScrew(h); return; }
    }
  }
});

// ---- 渲染 + 物理推进 ----
function screwLoop(){
  if (!sRunning) return;
  try {
    var sub = 2;
    sPlates.forEach(function(p){
      if (p.free && p.alive) {
        var w2 = Math.abs(p.body.angularVelocity) * Math.max(p.w, p.h) / 2;
        sub = Math.max(sub, Math.min(8, Math.ceil(w2 / 6)));
        if (Math.abs(p.body.angularVelocity) > 0.12)
          Matter.Body.setAngularVelocity(p.body, 0.12 * Math.sign(p.body.angularVelocity));
      }
    });
    for (var i = 0; i < sub; i++) Matter.Engine.update(sEngine, 1000 / 60 / sub);

    sPlates.forEach(function(p){
      if (p.free && p.alive) {
        var settled = Math.abs(p.body.velocity.y) < 0.6 && Math.abs(p.body.angularVelocity) < 0.02;
        p.stuckFrames = settled ? (p.stuckFrames || 0) + 1 : 0;
        if (p.body.position.y > SH + 160 || p.stuckFrames > 60) {
          p.alive = false;
          Matter.World.remove(sWorld, p.body);
          track('plate_gone');
        }
      }
    });

    drawScrew();
    checkScrewEnd();
  } catch(e){}
  if (sRunning) requestAnimationFrame(screwLoop);
}

function drawScrew(){
  var dpr = window.devicePixelRatio || 1;
  scrctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  scrctx.clearRect(0, 0, SW, SH);

  var grad = scrctx.createLinearGradient(0, 0, 0, SH);
  grad.addColorStop(0, '#2a1d0e'); grad.addColorStop(1, '#120a04');
  scrctx.fillStyle = grad; scrctx.fillRect(0, 0, SW, SH);

  // 孔位
  sHoles.forEach(function(h){
    scrctx.beginPath(); scrctx.arc(h.x, h.y, h.r, 0, Math.PI * 2);
    scrctx.fillStyle = h.occupied ? 'rgba(0,0,0,.25)' :
      (holeFree(h) ? 'rgba(124,252,154,.28)' : 'rgba(0,0,0,.45)');
    scrctx.fill();
    scrctx.lineWidth = 3; scrctx.strokeStyle = 'rgba(255,233,184,.5)'; scrctx.stroke();
  });

  // 铁板
  sPlates.forEach(function(p){
    if (!p.alive) return;
    var bp = p.body.position, ang = p.body.angle;
    scrctx.save(); scrctx.translate(bp.x, bp.y); scrctx.rotate(ang);
    var g2 = scrctx.createLinearGradient(0, -p.h/2, 0, p.h/2);
    g2.addColorStop(0, '#9aa3ad'); g2.addColorStop(0.5, '#6f7883'); g2.addColorStop(1, '#4a515a');
    scrctx.fillStyle = g2;
    scrctx.beginPath();
    if (scrctx.roundRect) scrctx.roundRect(-p.w/2, -p.h/2, p.w, p.h, 14);
    else scrctx.rect(-p.w/2, -p.h/2, p.w, p.h);
    scrctx.fill();
    scrctx.lineWidth = 4; scrctx.strokeStyle = '#30353c'; scrctx.stroke();
    scrctx.restore();
  });

  // 螺丝
  sScrews.forEach(function(s){
    if (!s.alive) return;
    scrctx.beginPath(); scrctx.arc(s.x, s.y, 16, 0, Math.PI * 2);
    var g3 = scrctx.createRadialGradient(s.x-4, s.y-4, 2, s.x, s.y, 16);
    g3.addColorStop(0, '#e8edf2'); g3.addColorStop(1, '#8a939e');
    scrctx.fillStyle = g3; scrctx.fill();
    scrctx.lineWidth = 2.5; scrctx.strokeStyle = '#3a4048'; scrctx.stroke();
    // 十字槽
    scrctx.beginPath();
    scrctx.moveTo(s.x-8, s.y); scrctx.lineTo(s.x+8, s.y);
    scrctx.moveTo(s.x, s.y-8); scrctx.lineTo(s.x, s.y+8);
    scrctx.lineWidth = 3; scrctx.stroke();
  });

  // 选中螺丝提示
  if (sSelected) {
    scrctx.beginPath(); scrctx.arc(SW/2, 120, 20, 0, Math.PI*2);
    scrctx.fillStyle = 'rgba(255,215,106,.35)'; scrctx.fill();
    scrctx.font = '700 26px sans-serif'; scrctx.fillStyle = '#ffe9b8';
    scrctx.textAlign = 'center';
    scrctx.fillText('点一个绿色空孔放置螺丝', SW/2, 175);
  }

  scrctx.font = '900 34px sans-serif'; scrctx.fillStyle = '#ffe9b8'; scrctx.textAlign = 'center';
  scrctx.fillText('拆开铁板 取出' + (sPendingChest ? sPendingChest.type.name : '宝箱'), SW/2, 300);
}

var _deadlockFrames = 0;
function checkScrewEnd(){
  var alivePlates = sPlates.filter(function(p){ return p.alive; });
  if (alivePlates.length === 0) {
    sRunning = false;
    screwWin();
    return;
  }

  // 使用共享死锁检测器（2Hz 采样）
  if (Math.floor(Date.now() / 500) !== Math.floor((Date.now() - 16) / 500)) {
    var dl = App.deadlock.check(
      sScrews.map(function(s){ return { alive: s.alive, constraint: s.constraint }; }),
      sHoles.map(function(h){
        return {
          occupied: h.occupied, park: h.park,
          x: h.x, y: h.y,
          // holeFree 需要铁板几何信息，适配 deadlock checker 的 x/y/w/h 格式
        };
      }),
      sPlates.map(function(p){ return { alive: p.alive, free: p.free, x: p.x, y: p.y, w: p.w, h: p.h }; }),
      !!sSelected
    );

    // 补充 holeFree 检查的适配 —— deadlock.check 里的 holes 需要 block 逻辑
    // 这里直接用模板自己的 holeFree 做补充检查
    var pinnedLeft = sScrews.some(function(s){ return s.alive && s.constraint; });
    var freeHoles = sHoles.filter(function(h){ return holeFree(h); });
    var moving = sPlates.some(function(p){
      return p.alive && p.free && (Math.abs(p.body.velocity.y) > 4 || Math.abs(p.body.angularVelocity) > 0.05);
    });

    if (pinnedLeft && freeHoles.length === 0 && !sSelected && !moving) {
      _deadlockFrames++;
    } else {
      _deadlockFrames = 0;
    }

    if (_deadlockFrames > 6) {  // ~3 秒确认
      sRunning = false;
      screwFail();
    }
  }
}

function screwWin(){
  var pc = sPendingChest;
  track('screw_win');
  App.sound.pop();
  doFlash();
  var mySeq = App.nextSeq();
  setTimeout(function(){
    if (!App.isLatest(mySeq)) return;
    screwCV.classList.remove('show');
    el('scan-stage').style.display = '';
    App.stateMachine.go('scan');
    if (pc) {
      chestsDone++;
      App.state.cleared = chestsDone;
      App.emit('cleared');
      doFlash();
      addGold(pc.type.value, pc.cx, pc.cy);
      track('chest_open_' + pc.type.lvl);
      sPendingChest = null;
      setTimeout(function(){ if (App.isLatest(mySeq)) checkFinalClear(); }, 1000);
    }
  }, 600);
}

function screwFail(){
  track('screw_fail');
  App.end('fail');
}

// =====================================================================
// 生命周期 + 横竖屏适配
// =====================================================================
on('start', function(){
  App.stateMachine.go('scan');
  fitScanCanvas();
  drawScan();
  tip.style.opacity = '1';
});

on('layout', function(){
  fitScanCanvas();
  drawScan();
  if (sRunning) fitScrewCanvas();
});

on('end', function(){
  sRunning = false;
  if (sEngine) { Matter.Engine.clear(sEngine); sEngine = null; }
});

// 定时检查通关
setInterval(function(){
  if (App.stateMachine.is('scan')) checkFinalClear();
}, 1200);

// =====================================================================
// QA 调试钩子
// =====================================================================
window.__qa = {
  cells: function(){ return cells.map(function(c){ return { key: c.key, dug: c.dug }; }); },
  gold: function(){ return gold; },
  chests: function(){ return chestsDone; },
  screws: function(){ return sScrews.filter(function(s){ return s.alive; }).map(function(s){ return { x: s.x, y: s.y, plateId: s.plateId, pinned: !!s.constraint }; }); },
  holes: function(){ return sHoles.filter(function(h){ return holeFree(h); }).map(function(h){ return { x: h.x, y: h.y, park: !!h.park }; }); },
  selected: function(){ return !!sSelected; },
  plates: function(){ return sPlates.filter(function(p){ return p.alive; }).length; },
  plateLeft: function(){
    var m = {};
    sScrews.forEach(function(s){ if (s.alive && s.constraint) m[s.plateId] = (m[s.plateId]||0)+1; });
    return m;
  },
  screwRunning: function(){ return sRunning; },
  result: function(){ return App.state.result; },
  goal: GOAL,
  stateMachine: function(){ return App.stateMachine.current(); }
};
"""
