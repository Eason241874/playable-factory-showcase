# -*- coding: utf-8 -*-
"""拖拽合成 · 量产级 v2（drag_merge）。

Canvas 渲染 + 程序化精灵 + 粒子爆发 + 音效 + 横竖屏适配。
"""

HTML = """
<canvas id="merge-canvas"></canvas>
<div id="merge-particles"></div>
"""

CSS = """
#merge-canvas{display:block;width:100%;height:100%;touch-action:none}
#merge-particles{position:fixed;inset:0;pointer-events:none;z-index:50}
.particle{position:absolute;border-radius:999px;pointer-events:none;
  animation:partFly .7s ease-out both}
@keyframes partFly{0%{transform:translate(0,0) scale(1);opacity:1}
  100%{transform:translate(var(--px),var(--py)) scale(0);opacity:0}}
"""

JS = """
// =====================================================================
// 配置
// =====================================================================
var EMOJIS = {{item_emojis}};
var TARGET_LV = App.cfg.target_level || 4;
var TOTAL = App.cfg.total || 5;
var ITEM_NAME = App.cfg.item_name || '家具';

App.state.cleared = 0;
App.state.total = TOTAL;

App.stateMachine.extend({
  idle: ['playing'],
  playing: ['end'],
  end: ['playing']
});

// =====================================================================
// Canvas + 程序化精灵
// =====================================================================
var cv = el('merge-canvas'), ctx = cv.getContext('2d');
var DW = 750, DH = 1334;  // 设计分辨率

// 程序化精灵着色方案：每级不同渐变色
var LV_COLORS = [
  ['#ff9a9e','#fad0c4'], ['#a18cd1','#fbc2eb'], ['#fbc2eb','#a6c1ee'],
  ['#84fab0','#8fd3f4'], ['#fccb90','#d57eeb'], ['#f093fb','#f5576c'],
  ['#4facfe','#00f2fe'], ['#ffe259','#ffa751']
];

function drawRoundedSprite(x, y, w, h, lv, scale){
  scale = scale || 1;
  var sw = w * scale, sh = h * scale;
  var sx = x + (w - sw) / 2, sy = y + (h - sh) / 2;
  var r = Math.min(sw, sh) * 0.18;

  // 投影
  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,.3)'; ctx.shadowBlur = 10; ctx.shadowOffsetY = 3;

  // 渐变填充
  var gc = LV_COLORS[Math.min(lv, LV_COLORS.length - 1)];
  var grad = ctx.createLinearGradient(sx, sy, sx, sy + sh);
  grad.addColorStop(0, gc[0]); grad.addColorStop(1, gc[1]);
  ctx.fillStyle = grad;

  ctx.beginPath();
  ctx.moveTo(sx + r, sy);
  ctx.lineTo(sx + sw - r, sy);
  ctx.quadraticCurveTo(sx + sw, sy, sx + sw, sy + r);
  ctx.lineTo(sx + sw, sy + sh - r);
  ctx.quadraticCurveTo(sx + sw, sy + sh, sx + sw - r, sy + sh);
  ctx.lineTo(sx + r, sy + sh);
  ctx.quadraticCurveTo(sx, sy + sh, sx, sy + sh - r);
  ctx.lineTo(sx, sy + r);
  ctx.quadraticCurveTo(sx, sy, sx + r, sy);
  ctx.closePath();
  ctx.fill();
  ctx.restore();

  // 白色内边框
  ctx.strokeStyle = 'rgba(255,255,255,.35)'; ctx.lineWidth = 2;
  ctx.stroke();

  // 等级数字
  ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  var fs = Math.max(18, sw * 0.23);
  ctx.font = '800 ' + fs + 'px -apple-system,sans-serif';
  ctx.shadowColor = 'rgba(0,0,0,.4)'; ctx.shadowBlur = 4;
  ctx.fillText('Lv.' + lv, sx + sw / 2, sy + sh / 2 - fs * 0.28);
  ctx.shadowBlur = 0;

  // emoji icon（小）
  ctx.font = Math.max(16, sw * 0.22) + 'px sans-serif';
  ctx.fillText(EMOJIS[Math.min(lv, EMOJIS.length - 1)] || '📦', sx + sw / 2, sy + sh / 2 + fs * 0.36);
}

// =====================================================================
// 物品系统
// =====================================================================
var ITEM_W = 90, ITEM_H = 90;
var items = [];
var dragging = null, dragX = 0, dragY = 0;
var particles = [];

function spawn(lv, n){
  for (var i = 0; i < n; i++) {
    items.push({
      x: DW * 0.15 + Math.random() * DW * 0.7,
      y: DH * 0.55 + Math.random() * DH * 0.28,
      w: ITEM_W, h: ITEM_H,
      lv: lv, scale: 1, scaleTween: 0,
      anim: 1  // 入场动画计时
    });
  }
}

// =====================================================================
// 粒子系统
// =====================================================================
var _particlesEl = el('merge-particles');
function emitParticles(x, y, color){
  for (var i = 0; i < 14; i++) {
    var p = document.createElement('div');
    p.className = 'particle';
    p.style.left = (x * window.innerWidth / DW) + 'px';
    p.style.top = (y * window.innerHeight / DH) + 'px';
    p.style.width = (6 + Math.random() * 8) + 'px';
    p.style.height = p.style.width;
    p.style.background = color[Math.floor(Math.random() * 2)];
    p.style.setProperty('--px', (Math.random() - 0.5) * 80 + 'px');
    p.style.setProperty('--py', -20 - Math.random() * 50 + 'px');
    _particlesEl.appendChild(p);
    setTimeout(function(){ p.remove(); }, 750);
  }
}

// =====================================================================
// 碰撞检测 + 合并
// =====================================================================
function findTarget(x, y, self){
  for (var i = items.length - 1; i >= 0; i--) {
    var o = items[i];
    if (o === self) continue;
    if (o.lv !== self.lv) continue;
    var dx = x - o.x, dy = y - o.y;
    if (Math.abs(dx) < o.w * 0.5 && Math.abs(dy) < o.h * 0.5) return o;
  }
  return null;
}

function merge(a, b){
  var lv = a.lv + 1;
  var cx = (a.x + b.x) / 2, cy = (a.y + b.y) / 2;
  items = items.filter(function(x){ return x !== a && x !== b; });
  App.state.cleared++;
  App.emit('cleared');
  emitParticles(cx, cy, LV_COLORS[Math.min(lv, LV_COLORS.length - 1)]);
  App.sound.pop();

  if (lv >= TARGET_LV || App.state.cleared >= TOTAL) {
    // 生成目标道具并胜利
    var winItem = { x: cx, y: cy, w: ITEM_W * 1.3, h: ITEM_H * 1.3,
                    lv: Math.min(lv, App.cfg.max_level || 5), scale: 1.5, scaleTween: 8, anim: 1 };
    items.push(winItem);
    var mySeq = App.nextSeq();
    setTimeout(function(){
      if (!App.isLatest(mySeq)) return;
      App.sound.victory();
      App.end('success');
    }, 750);
    return;
  }

  // 生成新等级物品（入场动画）
  var ni = { x: cx, y: cy, w: ITEM_W, h: ITEM_H, lv: lv, scale: 1.3, scaleTween: 0.3, anim: 1 };
  items.push(ni);

  // 补货：保证场上始终有可合成对
  var hasPair = items.some(function(x){
    return items.some(function(y){ return x !== y && x.lv === y.lv; });
  });
  if (!hasPair) spawn(Math.max(0, lv - 1), 2);
}

// =====================================================================
// 交互
// =====================================================================
function canvasPos(e){
  var r = cv.getBoundingClientRect();
  return { x: (e.clientX - r.left) * DW / r.width, y: (e.clientY - r.top) * DH / r.height };
}

cv.addEventListener('pointerdown', function(e){
  if (!App.stateMachine.is('playing')) return;
  App.act();
  var p = canvasPos(e);
  // 优先选最上层（后面 index 的）
  for (var i = items.length - 1; i >= 0; i--) {
    var o = items[i];
    if (Math.abs(p.x - o.x) < o.w * 0.5 && Math.abs(p.y - o.y) < o.h * 0.5) {
      dragging = o;
      dragX = p.x - o.x;
      dragY = p.y - o.y;
      o.scaleTween = 0.05;
      App.sound.click();
      break;
    }
  }
});

cv.addEventListener('pointermove', function(e){
  if (!dragging) return;
  var p = canvasPos(e);
  dragging.x = p.x - dragX;
  dragging.y = p.y - dragY;
});

cv.addEventListener('pointerup', function(e){
  if (!dragging) return;
  var p = canvasPos(e);
  var t = findTarget(p.x, p.y, dragging);
  dragging.scaleTween = -0.05;  // 缩放回弹
  if (t) {
    merge(dragging, t);
  }
  dragging = null;
});

// 横竖屏适配
on('layout', function(){ draw(); });

// =====================================================================
// 渲染循环
// =====================================================================
function draw(){
  var dpr = window.devicePixelRatio || 1;
  cv.width = DW * dpr; cv.height = DH * dpr;
  cv.style.width = '100%'; cv.style.height = '100%';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, DW, DH);

  // 背景
  var bgGrad = ctx.createLinearGradient(0, 0, DW, DH);
  bgGrad.addColorStop(0, '#1a1a2e'); bgGrad.addColorStop(0.5, '#16213e'); bgGrad.addColorStop(1, '#0f3460');
  ctx.fillStyle = bgGrad; ctx.fillRect(0, 0, DW, DH);

  // 装饰性网格点
  ctx.fillStyle = 'rgba(255,255,255,.02)';
  for (var gx = 0; gx < DW; gx += 50) {
    for (var gy = 0; gy < DH; gy += 50) {
      ctx.beginPath(); ctx.arc(gx, gy, 1.5, 0, Math.PI * 2); ctx.fill();
    }
  }

  // 目标卡片
  var tcX = DW / 2 - 70, tcY = DH * 0.08, tcW = 140, tcH = 110;
  ctx.fillStyle = 'rgba(255,255,255,.08)';
  ctx.strokeStyle = 'rgba(255,255,255,.3)'; ctx.setLineDash([6, 4]); ctx.lineWidth = 2;
  ctx.beginPath();
  var rr = 16;
  ctx.moveTo(tcX + rr, tcY); ctx.lineTo(tcX + tcW - rr, tcY);
  ctx.quadraticCurveTo(tcX + tcW, tcY, tcX + tcW, tcY + rr);
  ctx.lineTo(tcX + tcW, tcY + tcH - rr);
  ctx.quadraticCurveTo(tcX + tcW, tcY + tcH, tcX + tcW - rr, tcY + tcH);
  ctx.lineTo(tcX + rr, tcY + tcH);
  ctx.quadraticCurveTo(tcX, tcY + tcH, tcX, tcY + tcH - rr);
  ctx.lineTo(tcX, tcY + rr);
  ctx.quadraticCurveTo(tcX, tcY, tcX + rr, tcY);
  ctx.closePath();
  ctx.fill(); ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = 'rgba(255,255,255,.65)'; ctx.font = '12px -apple-system,sans-serif';
  ctx.textAlign = 'center'; ctx.fillText('合成目标', tcX + tcW / 2, tcY + 18);

  // 目标道具预览（缩小版）
  drawRoundedSprite(tcX + tcW / 2 - 24, tcY + 28, 48, 48, TARGET_LV);
  ctx.fillStyle = '#ffd76a'; ctx.font = '700 13px -apple-system,sans-serif';
  ctx.fillText('Lv.' + TARGET_LV + ' ' + ITEM_NAME, tcX + tcW / 2, tcY + tcH - 12);

  // 绘制所有物品
  items.forEach(function(o){
    // 入场/缩放动画
    if (o.anim > 0) { o.anim = Math.max(0, o.anim - 0.06); o.scaleTween = o.anim * 0.4; }
    if (Math.abs(o.scaleTween) > 0.001) {
      o.scale += o.scaleTween;
      o.scaleTween *= 0.82;
      if (Math.abs(o.scaleTween) < 0.002) { o.scale = 1; o.scaleTween = 0; }
    }

    var s = o.scale || 1;
    var alpha = o === dragging ? 0.8 : 1;

    ctx.globalAlpha = alpha;
    drawRoundedSprite(o.x, o.y, o.w, o.h, o.lv, s);

    // 拖拽高亮
    if (o === dragging) {
      ctx.strokeStyle = 'rgba(255,210,90,.7)'; ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(o.x + o.w / 2, o.y + o.h / 2, o.w * s * 0.65, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  });

  requestAnimationFrame(draw);
}

// =====================================================================
// 入口
// =====================================================================
on('start', function(){
  App.stateMachine.go('playing');
  spawn(0, 4); spawn(1, 2);
  draw();
});

// 初始渲染一帧（开始页可见时也能看到背景）
(function initDraw(){
  var dpr = window.devicePixelRatio || 1;
  cv.width = DW * dpr; cv.height = DH * dpr;
  cv.style.width = '100%'; cv.style.height = '100%';
})();
"""
