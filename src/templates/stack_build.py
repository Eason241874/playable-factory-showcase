# -*- coding: utf-8 -*-
"""点击叠塔 · 量产级 v2（stack_build）。

Canvas 渲染 + 渐变方块 + 完美对齐发光 + 相机抖动 + 音效 + 横竖屏。
"""

HTML = """
<canvas id="stack-canvas"></canvas>
"""

CSS = """
#stack-canvas{display:block;width:100%;height:100%;touch-action:none}
"""

JS = """
// =====================================================================
// 配置
// =====================================================================
var TOTAL = App.cfg.total || 6;
var SPEED = App.cfg.speed || 2.2;
var TOL = App.cfg.tolerance || 26;

App.state.cleared = 0;
App.state.total = TOTAL;

App.stateMachine.extend({
  idle: ['playing'],
  playing: ['end'],
  end: ['playing']
});

// =====================================================================
// Canvas 渲染
// =====================================================================
var cv = el('stack-canvas'), ctx = cv.getContext('2d');
var DW = 750, DH = 1334;

// 调色板：每层不同颜色
var PALETTE = [
  { top: '#ff9a9e', bot: '#fad0c4', glow: '#ff9a9e' },
  { top: '#a18cd1', bot: '#fbc2eb', glow: '#c4a0ff' },
  { top: '#84fab0', bot: '#8fd3f4', glow: '#7CFC9A' },
  { top: '#fccb90', bot: '#d57eeb', glow: '#fccb90' },
  { top: '#ffe259', bot: '#ffa751', glow: '#ffe259' },
  { top: '#ff5f6d', bot: '#ff2d55', glow: '#ff5f6d' },
  { top: '#4facfe', bot: '#00f2fe', glow: '#4facfe' },
  { top: '#a8edea', bot: '#fed6e3', glow: '#a8edea' },
];

var BLOCK_W = 180, BLOCK_H = 42, GAP = 4;
var tower = [];  // [{x, w, perfect}]
var moverX = 0, dir = 1;
var playing = false, fails = 0;
var shakeFrames = 0, shakeDx = 0, shakeDy = 0;
var scorePopText = null, scorePopFrames = 0;

// 塔基位置
function towerBaseY(){ return DH * 0.88; }
function moverY(){ return towerBaseY() - (tower.length * (BLOCK_H + GAP)) - BLOCK_H - GAP; }

function drawBlock(x, y, w, perfect, alpha){
  alpha = alpha || 1;
  ctx.globalAlpha = alpha;

  var idx = tower.length % PALETTE.length;
  var c = PALETTE[idx];

  var r = 8;
  ctx.save();
  if (perfect) {
    ctx.shadowColor = c.glow; ctx.shadowBlur = 22;
  }

  var grad = ctx.createLinearGradient(x, y, x, y + BLOCK_H);
  grad.addColorStop(0, c.top); grad.addColorStop(1, c.bot);
  ctx.fillStyle = grad;

  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + BLOCK_H - r);
  ctx.quadraticCurveTo(x + w, y + BLOCK_H, x + w - r, y + BLOCK_H);
  ctx.lineTo(x + r, y + BLOCK_H);
  ctx.quadraticCurveTo(x, y + BLOCK_H, x, y + BLOCK_H - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = 'rgba(255,255,255,.35)'; ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.restore();
  ctx.globalAlpha = 1;
}

function draw(){
  var dpr = window.devicePixelRatio || 1;
  cv.width = DW * dpr; cv.height = DH * dpr;
  cv.style.width = '100%'; cv.style.height = '100%';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  // 相机抖动
  if (shakeFrames > 0) {
    shakeFrames--;
    shakeDx = (Math.random() - 0.5) * 10 * (shakeFrames / 6);
    shakeDy = (Math.random() - 0.5) * 8 * (shakeFrames / 6);
    ctx.translate(shakeDx, shakeDy);
  }

  ctx.clearRect(0, 0, DW, DH);

  // 背景：渐变天空
  var bgG = ctx.createLinearGradient(0, 0, 0, DH);
  bgG.addColorStop(0, '#1a1a2e'); bgG.addColorStop(0.4, '#16213e'); bgG.addColorStop(1, '#0f3460');
  ctx.fillStyle = bgG; ctx.fillRect(0, 0, DW, DH);

  // 地面线
  ctx.strokeStyle = 'rgba(255,255,255,.15)'; ctx.lineWidth = 1;
  ctx.setLineDash([4, 12]);
  ctx.beginPath();
  ctx.moveTo(50, towerBaseY() + BLOCK_H + 20);
  ctx.lineTo(DW - 50, towerBaseY() + BLOCK_H + 20);
  ctx.stroke();
  ctx.setLineDash([]);

  // 塔身
  tower.forEach(function(b, i){
    var y = towerBaseY() - (i + 1) * (BLOCK_H + GAP);
    drawBlock(b.x, y, b.w, b.perfect);
  });

  // 移动滑块
  if (playing) {
    drawBlock(moverX, moverY(), BLOCK_W, false, 1);
  }

  // 分数
  ctx.fillStyle = '#fff'; ctx.textAlign = 'center';
  ctx.font = '900 28px -apple-system,sans-serif';
  ctx.fillText(tower.length + ' / ' + TOTAL, DW / 2, DH * 0.06);

  // 得分 POP 文字
  if (scorePopFrames > 0) {
    scorePopFrames--;
    var popAlpha = Math.min(1, scorePopFrames / 15);
    var popY = DH * 0.18 - (15 - scorePopFrames) * 3;
    ctx.globalAlpha = popAlpha;
    ctx.fillStyle = '#ffe259';
    ctx.font = '900 24px -apple-system,sans-serif';
    ctx.fillText(scorePopText, DW / 2, popY);
    ctx.globalAlpha = 1;
  }

  if (playing) requestAnimationFrame(draw);
}

// =====================================================================
// 游戏逻辑
// =====================================================================
var lastRefX = 0;

function tick(){
  if (!playing) return;
  var maxX = DW - BLOCK_W;
  moverX += dir * SPEED * 3.8;
  if (moverX <= 0) { moverX = 0; dir = 1; }
  if (moverX >= maxX) { moverX = maxX; dir = -1; }
}

function drop(){
  if (!playing) return;
  App.act();

  var refX = tower.length > 0 ?
    tower[tower.length - 1].x :
    (DW - BLOCK_W) / 2;

  var diff = Math.abs(moverX - refX);

  if (diff <= TOL) {
    var perfect = diff <= TOL / 3;
    tower.push({ x: moverX, w: BLOCK_W, perfect: perfect });
    App.state.cleared = tower.length;
    App.emit('cleared');

    // 音效：完美时高音，普通时中音
    App.sound.beep(perfect ? 1100 : 700, 0.08, 'sine', 0.06);

    // 得分弹窗
    if (perfect) { scorePopText = 'PERFECT!'; scorePopFrames = 20; }
    else if (tower.length >= TOTAL) { scorePopText = '通关!'; scorePopFrames = 20; }

    if (tower.length >= TOTAL) {
      playing = false;
      draw();  // 最后一帧
      setTimeout(function(){ App.sound.victory(); App.end('success'); }, 500);
      return;
    }
  } else {
    fails++;
    // 残块：缩小宽度，体现失误
    tower.push({ x: Math.max(moverX, refX), w: Math.max(30, BLOCK_W - diff), perfect: false, fail: true });
    shakeFrames = 6;
    App.sound.thud();
    scorePopText = 'MISS!'; scorePopFrames = 15;

    if (fails >= 3) {
      playing = false;
      draw();
      App.sound.fail();
      setTimeout(function(){ App.end('fail'); }, 500);
      return;
    }
  }

  lastRefX = refX;
}

// =====================================================================
// 交互
// =====================================================================
cv.addEventListener('pointerdown', function(e){
  if (!App.stateMachine.is('playing')) return;
  drop();
});

// 横竖屏适配：canvas 设计分辨率不变，CSS 缩放
on('layout', function(){
  if (!playing && tower.length === 0) {
    // 空闲时重绘一帧显示静态塔
    drawInitFrame();
  }
});

// =====================================================================
// 游戏循环（双循环：tick 150Hz 平滑移动 + draw rAF）
// =====================================================================
var tickIv = null;

on('start', function(){
  App.stateMachine.go('playing');
  playing = true;
  moverX = (DW - BLOCK_W) / 2;
  dir = Math.random() > 0.5 ? 1 : -1;
  fails = 0;
  tower = [];
  App.state.cleared = 0;
  tickIv = setInterval(tick, 16);  // ~60fps 输入采样
  draw();  // 启动画循环
});

on('end', function(){
  playing = false;
  if (tickIv) clearInterval(tickIv);
});

// 开始前的静态帧
function drawInitFrame(){
  draw();
}
drawInitFrame();
"""
