# -*- coding: utf-8 -*-
"""渲染器 v3：量产级装配引擎。

AssetRegistry：bundle 缓存 + MIME 自动检测 + shared 素材库。
SHELL_JS：结算动画 / 粒子系统 / 音频合成 / 视频转场 / 横竖屏 / 触控去重。
END_HTML：真实图片素材结算页 + 毛玻璃品牌条。
"""

import base64
import hashlib
import importlib
import json
import mimetypes
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from components import snippets
from src.rag import LIB_PATH, load_library

DEFAULT_THEME = {
    "theme_bg": "linear-gradient(160deg,#3a1c71,#d76d77 55%,#ffaf7b)",
    "product_name": "马上来玩",
    "brand": "PlayableAd",
}

TOMB_THEME_BG = "radial-gradient(120% 90% at 50% 30%,#3a2a16 0%,#241708 45%,#0f0903 100%)"
BALLOON_THEME_BG = "linear-gradient(180deg,#7ec8f7 0%,#a8dcf9 38%,#d8f0fc 70%,#fdf6e3 100%)"


# =========================================================================
# AssetRegistry
# =========================================================================

class AssetRegistry:
    """素材注册表：按 bundle 加载 + shared 通用素材合并。

    bundle 专属素材（如 tomb/balloon）+ shared 通用 UI 素材（结算按钮/Logo/螺丝）。
    模板通过 {{img_xxx}} 占位符或 App.assets.get('xxx') 访问。
    """

    _cache: Dict[str, Dict[str, str]] = {}

    @classmethod
    def load(cls, bundle: str) -> Dict[str, str]:
        if bundle in cls._cache:
            return cls._cache[bundle]

        assets: Dict[str, str] = {}

        # 1. bundle 专属素材（构建产物优先）
        try:
            mod = importlib.import_module(f"components.{bundle}_assets")
            assets.update(mod.ASSETS)
        except Exception:
            pass

        # 2. 兜底：从 components/assets/ 读原始文件
        base = os.path.join(os.path.dirname(LIB_PATH), "assets")
        lib_data = load_library()
        for a in lib_data.get("assets", []):
            if a.get("bundle") != bundle:
                continue
            name = a.get("name", "")
            if name in assets and assets[name]:
                continue
            fname = a.get("file", "")
            path = os.path.join(base, fname)
            if fname and os.path.exists(path):
                assets[name] = cls._file_to_uri(path)
            else:
                assets[name] = ""

        # 3. 合并 shared 通用 UI 素材（结算页按钮/Logo/螺丝）
        shared_dir = os.path.join(base, "shared")
        if os.path.isdir(shared_dir):
            manifest_path = os.path.join(shared_dir, "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                for name, info in manifest.items():
                    key = "shared_" + name
                    if key not in assets or not assets.get(key):
                        fp = os.path.join(base, info["file"])
                        if os.path.exists(fp):
                            assets[key] = cls._file_to_uri(fp)

        cls._cache[bundle] = assets
        return assets

    @staticmethod
    def _file_to_uri(path: str) -> str:
        mime, _ = mimetypes.guess_type(path)
        mime = mime or "application/octet-stream"
        with open(path, "rb") as f:
            data = f.read()
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"

    @staticmethod
    def uris_by_mechanic(mechanic: str) -> Dict[str, str]:
        lib = load_library()
        mech = next(
            (m for m in lib.get("mechanics", []) if m.get("name") == mechanic), None
        )
        bundle = (mech or {}).get("asset_bundle")
        if not bundle:
            # 无 bundle 的玩法也加载 shared 素材
            return AssetRegistry.load("__shared__")
        return AssetRegistry.load(bundle)


def _asset_uris(mechanic: str) -> Dict[str, str]:
    return AssetRegistry.uris_by_mechanic(mechanic)


def _physics_js() -> str:
    try:
        from components.physics_lib import MATTER_JS, POLY_DECOMP
        return POLY_DECOMP + "\n" + MATTER_JS
    except Exception:
        return ""


# =========================================================================
# SHELL_JS v3：量产级运行时骨架
# =========================================================================

SHELL_JS = r"""
// ================= 运行时骨架 v3（量产级） =================
(function(){
var D = document, W = window;
var DESIGN_W = 750, DESIGN_H = 1334;

function el(id){ return D.getElementById(id); }
function track(name){
  window.__events = window.__events || [];
  window.__events.push({ e: name, t: Date.now() - (window.__t0 || 0) });
}

// =====================================================================
// 素材注册表
// =====================================================================
var _assetUris = {{asset_uris_json}};
var _assetReady = {};
var App = {
  cfg: {{params_json}},
  state: { cleared: 0, total: 1, result: null, gold: 0 },
  _events: {},
  on: function(ev, fn){ (this._events[ev] = this._events[ev] || []).push(fn); },
  emit: function(ev, data){
    (this._events[ev] || []).forEach(function(f){
      try{ f(data); }catch(e){ console.error('[App]', ev, e); }
    });
  },
  act: function(){
    if (!this.state.firstAct) {
      this.state.firstAct = true;
      this.emit('first_act');
      track('first_interaction');
      if (App._audioCtx && App._audioCtx.state === 'suspended') {
        App._audioCtx.resume().catch(function(){});
      }
    }
  },
  end: function(result){
    if (this.state.result) return;
    this.state.result = result;
    track('game_end_' + result);
    this.emit('end');
    showSettle(result);
  }
};

function on(ev, fn){ App.on(ev, fn); }

App.assets = {
  get: function(name){
    // 优先 bundle 专属，再 fallback shared
    return _assetUris[name] || _assetUris['shared_' + name] || '';
  },
  isReady: function(name){ return !!_assetReady[name]; },
  all: function(){ return _assetUris; }
};

// =====================================================================
// 横竖屏适配
// =====================================================================
App.isLandscape = function(){ return W.innerWidth > W.innerHeight; };
App.viewport = { w: DESIGN_W, h: DESIGN_H, scale: 1 };

function updateViewport(){
  var l = App.isLandscape();
  var vw = W.innerWidth, vh = W.innerHeight;
  var scale = Math.min(vw / DESIGN_W, vh / DESIGN_H);
  if (l) scale = Math.min(vw / DESIGN_H, vh / DESIGN_W);
  App.viewport = { w: DESIGN_W, h: DESIGN_H, scale: scale, landscape: l };
  var root = D.documentElement;
  root.style.setProperty('--design-w', DESIGN_W);
  root.style.setProperty('--design-h', DESIGN_H);
  root.style.setProperty('--scale', scale);
  root.style.setProperty('--vw', vw + 'px');
  root.style.setProperty('--vh', vh + 'px');
  App.emit('layout', App.viewport);
}
W.addEventListener('resize', updateViewport);
W.addEventListener('orientationchange', function(){ setTimeout(updateViewport, 200); });
updateViewport();

// =====================================================================
// 音效引擎（Web Audio API 合成）
// =====================================================================
App._audioCtx = null;
App._audioEnsure = function(){
  if (!App._audioCtx) {
    try { App._audioCtx = new (W.AudioContext || W.webkitAudioContext)(); } catch(e){}
  }
  if (App._audioCtx && App._audioCtx.state === 'suspended') {
    App._audioCtx.resume().catch(function(){});
  }
  return App._audioCtx;
};

App.sound = {
  _play: function(fn){
    var ctx = App._audioEnsure();
    if (!ctx) return;
    try { fn(ctx); } catch(e){}
  },
  beep: function(freq, dur, type, vol){
    vol = vol || 0.06; type = type || 'square'; dur = dur || 0.09;
    App.sound._play(function(ctx){
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.type = type; o.frequency.value = freq;
      g.gain.setValueAtTime(vol, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
      o.connect(g); g.connect(ctx.destination);
      o.start(); o.stop(ctx.currentTime + dur);
    });
  },
  sweep: function(from, to, dur, type){
    dur = dur || 0.15; type = type || 'sine';
    App.sound._play(function(ctx){
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.type = type;
      o.frequency.setValueAtTime(from, ctx.currentTime);
      o.frequency.exponentialRampToValueAtTime(to, ctx.currentTime + dur);
      g.gain.setValueAtTime(0.08, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur);
      o.connect(g); g.connect(ctx.destination);
      o.start(); o.stop(ctx.currentTime + dur);
    });
  },
  pop: function(){ App.sound.sweep(800, 200, 0.08, 'sine'); },
  click: function(){ App.sound.beep(1200, 0.05, 'square', 0.04); },
  thud: function(){ App.sound.sweep(170, 42, 0.22, 'sine'); },
  clink: function(){
    App.sound.beep(1200, 0.04, 'square', 0.08);
    setTimeout(function(){ App.sound.beep(900, 0.06, 'square', 0.5); }, 50);
  },
  victory: function(){
    App.sound.beep(523, 0.12, 'square', 0.07);
    setTimeout(function(){ App.sound.beep(659, 0.12, 'square', 0.07); }, 120);
    setTimeout(function(){ App.sound.beep(784, 0.2, 'square', 0.08); }, 240);
  },
  fail: function(){ App.sound.sweep(300, 80, 0.35, 'sawtooth'); },
  radar: function(dist){
    App.sound.beep(Math.max(800, 1400 - dist * 2.2), 0.06, 'square', 0.035);
  },
  burn: function(){ App.sound.sweep(2000, 80, 0.5, 'sawtooth'); }
};

// =====================================================================
// MRAID 队列 + ExitApi 四级降级 + CTA 去抖
// =====================================================================
var CTA_URL = {{cta_url}};
var _mraidReady = false, _mraidState = 'unknown', _mraidQueue = [];
var _lastCTA = 0, _CTA_COOLDOWN = 200;

try {
  if (typeof mraid !== 'undefined') {
    if (mraid.getState && mraid.getState() === 'loading') {
      _mraidState = 'loading';
      mraid.addEventListener('ready', function(){
        _mraidState = 'ready'; _mraidReady = true;
        _mraidQueue.forEach(function(fn){ try{ fn(); }catch(e){} });
        _mraidQueue = [];
      });
      mraid.addEventListener('error', function(){ _mraidState = 'error'; _mraidReady = false; });
    } else { _mraidState = 'ready'; _mraidReady = true; }
  }
} catch(e){}

window.__openStore = function(){
  var now = Date.now();
  if (now - _lastCTA < _CTA_COOLDOWN) return;
  _lastCTA = now;
  track('click_cta');
  try {
    if (typeof ExitApi !== 'undefined' && ExitApi && typeof ExitApi.exit === 'function') {
      ExitApi.exit(); return;
    }
  } catch(e){}
  try {
    if (_mraidReady && typeof mraid !== 'undefined' && typeof mraid.open === 'function') {
      mraid.open(CTA_URL);
      setTimeout(function(){
        var w = W.open(CTA_URL, '_blank', 'noopener');
        if (!w) { location.href = CTA_URL; }
      }, 300);
      return;
    }
    if (_mraidState === 'loading') { _mraidQueue.push(window.__openStore); return; }
  } catch(e){}
  try { var w = W.open(CTA_URL, '_blank', 'noopener'); if (!w) { location.href = CTA_URL; } } catch(e){}
};

W.addEventListener('pagehide', function(){ _mraidQueue = []; _mraidReady = false; });

// =====================================================================
// 触控去重
// =====================================================================
App.bindTap = function(el, handler){
  var _lastTouch = 0, _lastTouchX = -1, _lastTouchY = -1;
  el.addEventListener('touchend', function(e){
    _lastTouch = Date.now();
    if (e.changedTouches && e.changedTouches.length) {
      _lastTouchX = e.changedTouches[0].clientX;
      _lastTouchY = e.changedTouches[0].clientY;
    }
    handler(e);
  });
  el.addEventListener('click', function(e){
    if (Date.now() - _lastTouch < 300 &&
        Math.abs(e.clientX - _lastTouchX) < 20 &&
        Math.abs(e.clientY - _lastTouchY) < 20) return;
    handler(e);
  });
};

// =====================================================================
// 预加载器
// =====================================================================
App._preloadDone = {};
App.preloader = {
  _idle: function(fn){
    if (W.requestIdleCallback) { W.requestIdleCallback(fn, { timeout: 2500 }); }
    else { setTimeout(fn, 1); }
  },
  preload: function(names, priority){
    var self = this;
    if (priority === 'critical') { names.forEach(function(n){ self._loadOne(n); }); }
    else { self._idle(function(){ names.forEach(function(n){ self._loadOne(n); }); }); }
  },
  _loadOne: function(name){
    if (App._preloadDone[name]) return;
    var uri = App.assets.get(name);
    if (!uri || !uri.startsWith('data:image/')) return;
    var img = new Image();
    img.onload = function(){ _assetReady[name] = true; App._preloadDone[name] = true; };
    img.onerror = function(){ App._preloadDone[name] = true; };
    img.src = uri;
  },
  ensure: function(names){
    return Promise.all(names.map(function(n){
      return new Promise(function(resolve){
        if (App._preloadDone[n]) return resolve();
        var uri = App.assets.get(n);
        if (!uri) { App._preloadDone[n] = true; return resolve(); }
        var img = new Image();
        img.onload = function(){ _assetReady[n] = true; App._preloadDone[n] = true; resolve(); };
        img.onerror = function(){ App._preloadDone[n] = true; resolve(); };
        img.src = uri;
      });
    }));
  }
};

// =====================================================================
// 状态机
// =====================================================================
App.stateMachine = (function(){
  var _state = 'idle';
  var _allowed = {
    idle: ['playing'],
    playing: ['transition', 'end'],
    transition: ['playing', 'end', 'idle'],
    end: ['idle']
  };
  return {
    current: function(){ return _state; },
    is: function(s){ return _state === s; },
    go: function(to){
      var ok = (_allowed[_state] || []).indexOf(to) >= 0;
      if (!ok) { console.warn('[StateMachine] blocked: ' + _state + ' -> ' + to); return false; }
      var from = _state; _state = to;
      App.emit('state_change', { from: from, to: to });
      return true;
    },
    extend: function(transitions){
      for (var k in transitions) {
        if (transitions.hasOwnProperty(k)) {
          _allowed[k] = (_allowed[k] || []).concat(transitions[k]);
        }
      }
    }
  };
})();

// =====================================================================
// 序列号异步取消
// =====================================================================
App._seq = 0;
App.nextSeq = function(){ return ++App._seq; };
App.isLatest = function(seq){ return seq === App._seq; };

// =====================================================================
// 死锁检测
// =====================================================================
App.deadlock = {
  check: function(screws, holes, plates, heldScrew){
    var hasPinned = false;
    screws.forEach(function(s){ if (s.alive && s.constraint) hasPinned = true; });
    if (!hasPinned) return { dead: false, reason: 'no pinned screws' };
    var hasFreeHole = false;
    holes.forEach(function(h){
      if (!h.occupied) {
        var blocked = false;
        plates.forEach(function(p){
          if (!p.alive || p.free) return;
          if (h.x > p.x - p.w/2 && h.x < p.x + p.w/2 && h.y > p.y - p.h/2 && h.y < p.y + p.h/2) blocked = true;
        });
        if (!blocked && !h.park) hasFreeHole = true;
      }
    });
    var hasPark = holes.some(function(h){ return h.park && !h.occupied; });
    if (!hasFreeHole && !hasPark && !heldScrew) {
      return { dead: true, reason: 'no legal moves' };
    }
    return { dead: false };
  }
};

// =====================================================================
// 粒子系统（Canvas 渲染，用于结算页爆发效果）
// =====================================================================
App.particles = {
  _cv: null, _ctx: null, _parts: [], _raf: null,
  _init: function(){
    if (this._cv) return;
    this._cv = D.createElement('canvas');
    this._cv.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:99';
    this._cv.width = W.innerWidth; this._cv.height = W.innerHeight;
    D.body.appendChild(this._cv);
    this._ctx = this._cv.getContext('2d');
  },
  burst: function(x, y, color, count){
    this._init();
    count = count || 50;
    for (var i = 0; i < count; i++) {
      var angle = Math.random() * Math.PI * 2;
      var speed = 2 + Math.random() * 5;
      this._parts.push({
        x: x, y: y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed - 2,
        r: 3 + Math.random() * 5, color: color,
        life: 1, decay: 0.01 + Math.random() * 0.02, grav: 0.15
      });
    }
    if (!this._raf) this._loop();
  },
  _loop: function(){
    var self = App.particles;
    self._ctx.clearRect(0, 0, self._cv.width, self._cv.height);
    var alive = false;
    for (var i = self._parts.length - 1; i >= 0; i--) {
      var p = self._parts[i];
      p.x += p.vx; p.y += p.vy; p.vy += p.grav; p.life -= p.decay;
      if (p.life <= 0) { self._parts.splice(i, 1); continue; }
      alive = true;
      self._ctx.globalAlpha = p.life;
      self._ctx.beginPath();
      self._ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      self._ctx.fillStyle = p.color;
      self._ctx.fill();
    }
    self._ctx.globalAlpha = 1;
    if (alive) { self._raf = requestAnimationFrame(function(){ App.particles._loop(); }); }
    else { self._raf = null; if (self._cv) { self._cv.remove(); self._cv = null; } }
  }
};

// =====================================================================
// 弹簧动画（结算标题/按钮入场效果）
// =====================================================================
App.spring = {
  _anims: [],
  animate: function(target, props, onDone){
    // props: { scale: { from: 0.3, to: 1, stiffness: 0.15, damping: 0.85 }, ... }
    var anim = { target: target, props: {}, done: false, onDone: onDone };
    for (var k in props) {
      var p = props[k];
      anim.props[k] = { val: p.from, vel: 0, target: p.to, stiff: p.stiffness || 0.15, damp: p.damping || 0.85 };
    }
    this._anims.push(anim);
    if (!this._raf) this._loop();
    return anim;
  },
  _raf: null,
  _loop: function(){
    var self = App.spring;
    var anyActive = false;
    self._anims = self._anims.filter(function(a){ return !a.done; });
    self._anims.forEach(function(a){
      var allSettled = true;
      for (var k in a.props) {
        var p = a.props[k];
        var force = (p.target - p.val) * p.stiff;
        p.vel = (p.vel + force) * p.damp;
        p.val += p.vel;
        if (Math.abs(p.vel) > 0.001 || Math.abs(p.target - p.val) > 0.001) allSettled = false;
        a.target.style[k] = p.val;
      }
      if (allSettled) { a.done = true; if (a.onDone) a.onDone(); }
      else anyActive = true;
    });
    if (anyActive) self._raf = requestAnimationFrame(function(){ App.spring._loop(); });
    else self._raf = null;
  }
};

// =====================================================================
// 结算页显示（图片素材 + 弹簧动画 + 粒子爆发）
// =====================================================================
function showSettle(result){
  App.stateMachine.go('end');
  var layer = el('end-layer');
  var emojiEl = el('end-emoji');
  var titleEl = el('end-title');
  var descEl = el('end-desc');
  var retryBtn = el('btn-retry');
  var ctaBtn = el('btn-cta-end');
  var bannerImg = el('settle-banner-img');
  var midBtn = el('settle-mid-btn');
  var bottomBtn = el('settle-bottom-btn');

  // 尝试用 shared 图片素材，fallback 到文字
  var bannerSrc = App.assets.get(result === 'success' ? 'banner_win' : 'banner_fail');
  var midSrc = App.assets.get(result === 'success' ? 'btn_play' : 'btn_retry');
  var bottomSrc = App.assets.get(result === 'success' ? 'btn_next' : 'btn_play_fail');

  var hasImages = bannerSrc && midSrc && bottomSrc;

  if (hasImages && bannerImg && midBtn && bottomBtn) {
    // 图片模式：隐藏文字元素，显示图片
    if (emojiEl) emojiEl.style.display = 'none';
    if (titleEl) titleEl.style.display = 'none';
    if (descEl) descEl.style.display = 'none';
    if (retryBtn) retryBtn.style.display = 'none';
    if (ctaBtn) ctaBtn.style.display = 'none';

    bannerImg.src = bannerSrc;
    bannerImg.style.display = '';
    midBtn.src = midSrc;
    midBtn.style.display = '';
    bottomBtn.src = bottomSrc;
    bottomBtn.style.display = '';

    // 弹簧动画
    var pop = el('result-pop');
    if (pop) {
      App.spring.animate(pop, {
        transform: { from: 'scale(0.7) translateY(40px)', to: 'scale(1) translateY(0px)' },
        opacity: { from: '0', to: '1' }
      });
    }

    // 胜利粒子爆发
    if (result === 'success') {
      var cx = W.innerWidth / 2, cy = W.innerHeight / 2;
      setTimeout(function(){ App.particles.burst(cx, cy, '#ffd76a', 50); }, 200);
    }

    // 按钮绑定
    App.bindTap(midBtn, function(){
      if (result === 'success') window.__openStore();
      else location.reload();
    });
    App.bindTap(bottomBtn, function(){ window.__openStore(); });

  } else {
    // 文字模式：使用文字按钮
    if (bannerImg) bannerImg.style.display = 'none';
    if (midBtn) midBtn.style.display = 'none';
    if (bottomBtn) bottomBtn.style.display = 'none';
    if (emojiEl) { emojiEl.style.display = ''; emojiEl.textContent = result === 'success' ? '🎉' : '😢'; }
    if (titleEl) { titleEl.style.display = ''; titleEl.textContent = result === 'success' ? {{end_success}} : {{end_fail}}; }
    if (descEl) { descEl.style.display = ''; descEl.textContent = result === 'success' ? {{end_success_sub}} : {{end_fail_sub}}; }
    if (retryBtn) { retryBtn.style.display = result === 'success' ? 'none' : ''; }
    if (ctaBtn) ctaBtn.style.display = '';

    // 粒子爆发
    if (result === 'success') {
      var cx2 = W.innerWidth / 2, cy2 = W.innerHeight / 2;
      setTimeout(function(){ App.particles.burst(cx2, cy2, '#ffd76a', 40); }, 300);
    }
  }

  // 音效
  if (result === 'success') App.sound.victory();
  else App.sound.fail();

  layer.classList.remove('hide');
}

// =====================================================================
// 视频转场（参考包模式）
// =====================================================================
App.videoTransition = {
  play: function(src, duration, onEnd){
    var mySeq = App.nextSeq();
    var v = D.createElement('video');
    v.muted = true; v.playsInline = true;
    v.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;object-fit:cover;z-index:45;opacity:0;transition:opacity .15s';
    D.body.appendChild(v);

    var ended = false;
    var timeout = setTimeout(finish, (duration || 3) * 1000 + 800);
    function finish(){
      if (ended || !App.isLatest(mySeq)) return;
      ended = true;
      clearTimeout(timeout);
      v.style.opacity = '0';
      setTimeout(function(){ v.remove(); if (onEnd) onEnd(); }, 200);
    }

    v.onloadeddata = function(){ v.style.opacity = '1'; };
    v.oncanplay = function(){ v.style.opacity = '1'; };
    v.onended = finish;
    v.onerror = finish;

    // 加载失败时白闪 + 直接回调
    setTimeout(function(){
      if (!ended && v.readyState === 0) {
        v.remove();
        // 白闪
        var f = D.createElement('div');
        f.style.cssText = 'position:fixed;inset:0;background:#fff;opacity:0;z-index:46;transition:opacity .1s';
        D.body.appendChild(f);
        requestAnimationFrame(function(){ f.style.opacity = '.9'; });
        setTimeout(function(){ f.style.opacity = '0'; setTimeout(function(){ f.remove(); }, 200); }, 150);
        if (onEnd) onEnd();
      }
    }, 1200);

    v.src = src;
    v.play().catch(function(){ finish(); });
  }
};

// =====================================================================
// 流程控制
// =====================================================================
el('btn-start').addEventListener('click', function(){
  track('click_start');
  App.stateMachine.go('playing');
  el('start-layer').classList.add('hide');
  var n = 3, cl = el('count-layer');
  cl.classList.remove('hide');
  el('count-num').textContent = n;
  var iv = setInterval(function(){
    n--;
    if (n <= 0) { clearInterval(iv); cl.classList.add('hide'); App.emit('start'); track('game_start'); }
    else { el('count-num').textContent = n; }
  }, 700);
});

// CTA 绑定
['btn-cta', 'cta-hotzone', 'brand-cta-shell'].forEach(function(id){
  var b = el(id);
  if (b) App.bindTap(b, function(){ window.__openStore(); });
});

var _retryBtn = el('btn-retry');
if (_retryBtn) _retryBtn.addEventListener('click', function(){
  track('click_retry'); location.reload();
});

// AppLovin modal 守护
(function(){
  function boost(m){
    try {
      m.style.setProperty('z-index', '2147483647', 'important');
      m.style.setProperty('top', '0', 'important');
      m.style.setProperty('left', '0', 'important');
      m.style.setProperty('right', '0', 'important');
    } catch(e){}
  }
  function guard(){
    var m = D.getElementById('modal'); if (m) boost(m);
    try {
      new MutationObserver(function(list){
        list.forEach(function(mu){
          Array.prototype.forEach.call(mu.addedNodes, function(n){
            if (n.id === 'modal' || (n.innerHTML && /successfully clicked/i.test(n.innerHTML))) boost(n);
          });
        });
      }).observe(D.body, { childList: true });
    } catch(e){}
  }
  if (D.body) guard(); else D.addEventListener('DOMContentLoaded', guard);
})();

// iOS 禁止手势缩放
D.addEventListener('gesturestart', function(e){ e.preventDefault(); });

// =====================================================================
// 导出到全局：模板 JS 和组件 JS 在独立的 <script> 块中运行，
// 必须能访问 App / el / on / track。
// =====================================================================
window.App = App;
window.el = el;
window.on = on;
window.track = track;

})();  // ---- SHELL_JS 结束 ----
"""

# =========================================================================
# END_HTML v3：结算页用真实图片素材
# =========================================================================

END_HTML = """
<div class="layer" id="start-layer">
  <div class="brand-shell-top">
    <img class="brand-logo-img" id="brand-logo-start" src="{{shared_logo}}" alt="" onerror="this.style.display='none'">
  </div>
  <div class="start-card">
    <div class="start-icon" id="start-icon">{{cover_emoji}}</div>
    <div class="game-title">{{title}}</div>
    <div class="game-desc">{{desc}}</div>
    <button class="btn-start" id="btn-start">开始挑战</button>
  </div>
</div>

<div class="layer hide" id="count-layer">
  <div id="count-num">3</div>
</div>

<div class="layer" id="game-layer">{{game_html}}{{components_html}}</div>

<div class="layer hide" id="end-layer">
  <div class="end-overlay"></div>
  <div class="result-pop" id="result-pop">
    <!-- 图片模式：优先使用真实图片素材 -->
    <img id="settle-banner-img" class="settle-img-banner" src="" alt="" style="display:none">
    <div class="result-emoji" id="end-emoji"></div>
    <div class="game-title" id="end-title">挑战成功！</div>
    <div class="game-desc" id="end-desc"></div>
    <div class="end-btns">
      <img id="settle-mid-btn" class="settle-img-btn" src="" alt="" style="display:none">
      <img id="settle-bottom-btn" class="settle-img-btn" src="" alt="" style="display:none">
      <button class="btn-retry" id="btn-retry">再试一次</button>
      <button class="btn-cta" id="btn-cta-end">{{cta_text}}</button>
    </div>
  </div>
</div>

<!-- 常驻品牌条：LOGO + PLAY NOW -->
<div id="brand-shell">
  <img id="brand-shell-logo-img" src="{{shared_logo}}" alt="" onerror="this.outerHTML='<span id=\\'brand-shell-logo\\'>{{brand}}</span>'">
  <button id="brand-cta-shell" type="button">{{cta_text}}</button>
</div>

<!-- CTA 隐形热区 -->
<div id="cta-hotzone"></div>

<!-- 浮动 CTA 按钮 -->
<button class="btn-cta" id="btn-cta" style="position:fixed;bottom:max(4%,env(safe-area-inset-bottom,12px));left:50%;transform:translateX(-50%);z-index:42;padding:12px 36px;font-size:16px">{{cta_text}}</button>
"""

# =========================================================================
# TEMPLATE
# =========================================================================

TEMPLATE = """<!DOCTYPE html>
<!-- Generated by playable-ad-factory | mechanic={{mechanic}} | mock={{mock}} -->
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="ad.orientation" content="portrait,landscape">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>{{title}}</title>
<script src="mraid.js"></script>
{{base_css}}
<style>{{game_css}}{{components_css}}</style>
</head>
<body>
<div id="stage">{{body}}</div>
<script>window.__t0 = Date.now();</script>
<script>{{shell_js}}</script>
<script>{{game_js}}</script>
<script>{{components_js}}</script>
</body>
</html>
"""


# =========================================================================
# 渲染主函数
# =========================================================================

def _fill(text: str, mapping: Dict[str, Any]) -> str:
    def rep(m):
        key = m.group(1).strip()
        return str(mapping.get(key, m.group(0)))
    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", rep, text)


def render(state) -> str:
    spec = state["spec"]
    plan = state["plan"]
    params = dict(state.get("params") or {})
    theme = dict(DEFAULT_THEME)
    theme.update(spec.get("theme") or {})
    mechanic = plan["mechanic"]

    asset_uris: Dict[str, str] = AssetRegistry.uris_by_mechanic(mechanic)
    mapping_physics = ""
    if mechanic in ("tomb_explore", "balloon_rescue"):
        if mechanic == "tomb_explore" and not spec.get("theme_bg"):
            theme["theme_bg"] = TOMB_THEME_BG
        elif mechanic == "balloon_rescue" and not spec.get("theme_bg"):
            theme["theme_bg"] = BALLOON_THEME_BG
        mapping_physics = _physics_js()

    if mechanic == "custom":
        game_html = state.get("custom_html", "<div style='color:#fff'>自定义玩法</div>")
        game_css = state.get("custom_css", "")
        game_js = state.get("custom_logic", "")
    else:
        try:
            tpl = importlib.import_module(f"src.templates.{mechanic}")
        except ModuleNotFoundError:
            tpl = None
        if tpl is None:
            game_html = f"<div style='color:#fff;text-align:center;padding-top:40vh'>模板未找到: {mechanic}</div>"
            game_css, game_js = "", ""
        else:
            game_html = getattr(tpl, 'HTML', '')
            game_css = getattr(tpl, 'CSS', '')
            game_js = getattr(tpl, 'JS', '')
            for k, v in params.items():
                if not isinstance(v, (list, dict)):
                    game_html = game_html.replace("{{%s}}" % k, str(v))

    comps = state.get("components", [])
    comps_html = "\n".join(snippets.HTML.get(c["name"], "") for c in comps if c["name"] in snippets.HTML)
    comps_css = "\n".join(snippets.CSS.get(c["name"], "") for c in comps if c["name"] in snippets.CSS)
    comps_js = "\n".join(snippets.JS.get(c["name"], "") for c in comps if c["name"] in snippets.JS)

    cover_emoji = spec.get("cover_emoji", theme.get("cover_emoji", "🎮"))
    for c in comps:
        if c.get("cover_emoji"):
            cover_emoji = c["cover_emoji"]

    mapping = {
        "title": spec.get("title", "试玩一下"),
        "desc": spec.get("desc", "动动手指，挑战一下！"),
        "brand": theme["brand"],
        "theme_bg": theme["theme_bg"],
        "cover_emoji": cover_emoji,
        "cta_text": spec.get("cta_text", "立即下载"),
        "cta_url": json.dumps(spec.get("cta_url", "")),
        "params_json": json.dumps(params, ensure_ascii=False),
        "asset_uris_json": json.dumps(asset_uris, ensure_ascii=False),
        "end_success": json.dumps(spec.get("end_success", "🎉 挑战成功！"), ensure_ascii=False),
        "end_success_sub": json.dumps(spec.get("end_success_sub", "完整版更刺激，马上体验！"), ensure_ascii=False),
        "end_fail": json.dumps(spec.get("end_fail", "就差一点！"), ensure_ascii=False),
        "end_fail_sub": json.dumps(spec.get("end_fail_sub", "完整版再挑战一次！"), ensure_ascii=False),
        "mechanic": mechanic,
        "mock": state.get("mock", False),
        "base_css": snippets.BASE_CSS,
        "game_html": game_html,
        "game_css": game_css,
        "game_js": game_js,
        "components_html": comps_html,
        "components_css": comps_css,
        "components_js": comps_js,
        "shell_js": SHELL_JS,
        "shared_logo": asset_uris.get("shared_logo", ""),
    }

    for k, v in params.items():
        if k in mapping:
            continue
        mapping[k] = json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v

    for k, v in asset_uris.items():
        mapping["img_" + k] = v

    mapping["physics_js"] = mapping_physics

    body = _fill(END_HTML, mapping)
    mapping["body"] = body
    html = _fill(TEMPLATE, mapping)
    for _ in range(3):
        new_html = _fill(html, mapping)
        if new_html == html:
            break
        html = new_html
    return html
