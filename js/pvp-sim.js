/* PvP 對戰模擬器（/pvp-sim/）：畫面與互動。
 * 計算全部在 js/pvp-sim-core.js（PvPoke 引擎），這裡只負責設定、繪製、沙盒操作與網址同步。
 *
 * 兩種模式：1 對 1、3 對 3 隊伍。兩者都用 core 的 match()：AI 依 PvPoke 邏輯對打，
 * 使用者可以在重播圖上點任一發特殊招式，改「開盾／不開盾、延後放招、改放另一招、換人擋招（切角）」，
 * 也可以設定對手的開盾習慣；每個選項都會先算好結果讓使用者比較。
 *
 * 網址參數（可分享）：
 *   共同：l=1500|2500|10000、cap=40、oh=對手開盾習慣、e=沙盒修改（~ 分隔）
 *   1 對 1：a=<一方>&b=<另一方>
 *     一方 = speciesId.一般招式.特殊招式1.特殊招式2(或 -).IV.護盾.起始能量.起始HP%.騙盾(1/0).最佳夥伴(1/0)
 *   3 對 3：m=3&ta=<隊伍>&tb=<隊伍>&ts=我方盾-對手盾&o=b|f&p=s|f
 *     隊伍 = 三隻用 ~ 分隔，每隻 = speciesId.一般招式.特殊招式1.特殊招式2.IV.最佳夥伴
 *   IV = d | b | h | c攻-防-HP-等級；沙盒修改 = s|h|u|w + 方.第幾發.值（例：s0.2.0 = 我方第 2 次被打不開盾）
 * 只用英數、底線、點、減號與 ~，history.replaceState 前不經過 URLSearchParams（見 CLAUDE.md §4）。
 */
(function () {
  "use strict";
  var C = window.PvPSimCore, E = window.PvPokeEngine;
  var IMG = "../trade-list/assets/thumb/";
  var TYPE_COLOR = {
    normal: "#8a8a6e", fire: "#e2662a", water: "#3d7fe0", grass: "#4fa83d", electric: "#d4a90f", ice: "#4cb5c4",
    fighting: "#b8352c", poison: "#9a4aa8", ground: "#c79b45", flying: "#7f8fe0", psychic: "#e2557d", bug: "#8a9a1c",
    rock: "#a8923c", ghost: "#6550a0", dragon: "#5b3fe0", dark: "#5a4a40", steel: "#7f8fa6", fairy: "#d873b8"
  };
  var LEAGUES = [{ cp: 1500, name: "超級聯盟" }, { cp: 2500, name: "高級聯盟" }, { cp: 10000, name: "大師聯盟" }];
  var IVMODES = [["def", "PvPoke 預設"], ["best", "PvP 排名 #1"], ["hundo", "100%"], ["custom", "自訂"]];
  var SIDE_NAME = ["我方", "對手"], TEAM_NAME = ["我方隊伍", "對手隊伍"], SLOT_NAME = ["先發", "2 號", "3 號"];
  var HABITS = [["ai", "AI 判斷"], ["always", "每發都開"], ["lethal", "只擋致命"], ["first", "只開第一發"], ["never", "完全不開"]];
  var SHIELD_SVG = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1 2 3.2v4.3c0 3.4 2.6 6.3 6 7.5 3.4-1.2 6-4.1 6-7.5V3.2z" fill="currentColor"/></svg>';
  var FAIL_TEXT = { missing: "對手沒有放到這一發", busy: "那一回合還在出一般招式，來不及換", timer: "換人冷卻中（45 秒內只能換一次）", target: "那隻已經倒下或已經在場上" };

  var state = {
    mode: 1, cp: 1500, cap: 50, sides: [null, null], teams: [null, null], order: "best", plan: "spread",
    edits: { 1: [], 3: [] }, habit: "ai", sel: null, ghost: null,
    turn: 0, sweepN: 30, sweepS: 1, sweepSort: "rank", cmpWho: 0, cmpAll: false, logAll: false
  };
  var res = null, mx = null, playTimer = null, pickFor = null, poolCache = {}, sweepJob = 0, keyJob = 0, tracked = false, openSlots = {};
  var app = document.getElementById("app");

  // ---------- 小工具 ----------
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function cfg() { return { cp: state.cp, levelCap: state.cap }; }
  function lgName() { return LEAGUES.filter(function (l) { return l.cp === state.cp; })[0].name; }
  function tch(t) { var z = C.typeZh(t); return z === "超能力" ? "超" : z.charAt(0); }
  function nm(id) { return C.mon(id) ? C.mon(id).speciesName : id; }
  function fmt(n) { return Number(n).toLocaleString("zh-Hant"); }
  function lvTxt(l) { return "Lv" + (l % 1 ? l.toFixed(1) : l); }
  function pic(id, cls) {
    var m = C.mon(id);
    return '<span class="pic' + (m && m.sh ? " sh" : "") + (cls ? " " + cls : "") + '">' +
      (m && m.img ? '<img src="' + IMG + esc(m.img) + '" alt="" loading="lazy" decoding="async" width="128" height="128">' : "") + "</span>";
  }
  function types(id) {
    return '<span class="tys">' + C.mon(id).types.filter(function (t) { return t && t !== "none"; }).map(function (t) {
      return '<span class="ty" style="--c:' + TYPE_COLOR[t] + '">' + esc(C.typeZh(t)) + "</span>";
    }).join("") + "</span>";
  }
  function mvChip(id, elite) {
    var m = C.move(id); if (!m) return "";
    var cg = m.energyGain > 0 ? "" : " cg";
    return '<span class="mv' + cg + '" style="--c:' + (TYPE_COLOR[m.type] || "#888") + '" data-ti="' + esc(tch(m.type)) + '">' + esc(m.name) + (elite ? "<em>限定</em>" : "") + "</span>";
  }
  function rc(r) {
    var k = Math.min(1, Math.abs(r - 500) / 320);
    if (r > 500) return { bg: "hsl(152 62% " + (93 - k * 22) + "%)", fg: "hsl(152 70% " + (30 - k * 8) + "%)" };
    if (r < 500) return { bg: "hsl(352 82% " + (95 - k * 20) + "%)", fg: "hsl(352 65% " + (42 - k * 10) + "%)" };
    return { bg: "#eceaf3", fg: "#3b3650" };
  }
  function toast(t) {
    var d = document.createElement("div"); d.className = "toast"; d.textContent = t; document.body.appendChild(d);
    setTimeout(function () { d.remove(); }, 1800);
  }
  function pools(id) {
    var k = id + "|" + state.cp;
    if (!poolCache[k]) poolCache[k] = C.movePools(id, cfg());
    return poolCache[k];
  }
  function track(name, params) { try { if (window.track) window.track(name, params || {}); } catch (e) { /* 分析失敗不影響工具 */ } }
  function pressed(sel, attr, val) {
    $$(sel + " button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute(attr) === String(val))); });
  }

  // ---------- 狀態 ----------
  function newMon(id, prev) {
    var mv = C.defaultMoves(id, state.cp);
    return { id: id, fast: mv[0], c1: mv[1], c2: mv[2], iv: { mode: "def" }, buddy: prev ? !!prev.buddy : false,
      shields: prev && prev.shields != null ? prev.shields : 1, energy: prev ? prev.energy || 0 : 0,
      hpPct: prev ? prev.hpPct || 100 : 100, bait: prev ? prev.bait !== false : true };
  }
  function fixMoves(s) {
    var p = pools(s.id), f = p.fast.map(function (m) { return m.id; }), c = p.charged.map(function (m) { return m.id; });
    var d = C.defaultMoves(s.id, state.cp);
    if (f.indexOf(s.fast) < 0) s.fast = d[0];
    if (c.indexOf(s.c1) < 0) s.c1 = d[1];
    if (s.c2 && (c.indexOf(s.c2) < 0 || s.c2 === s.c1)) s.c2 = d[2] !== s.c1 ? d[2] : null;
    return s;
  }
  function isRecommended(s) {
    var r = C.rankOf(s.id, String(state.cp)); if (!r) return null;
    var m = r.moves;
    return s.fast === m[0] && ((s.c1 === m[1] && s.c2 === m[2]) || (s.c1 === m[2] && s.c2 === m[1]));
  }
  function defaultTeam(from) {
    var top = C.topList(state.cp, 6);
    return { mons: [0, 1, 2].map(function (k) { return newMon(top[from + k][0]); }), shields: 2 };
  }
  /** 目前模式下的兩方（1 對 1 也包成一隊一隻）。 */
  function sides() {
    if (state.mode === 3) return state.teams;
    return [{ mons: [state.sides[0]], shields: state.sides[0].shields }, { mons: [state.sides[1]], shields: state.sides[1].shields }];
  }
  function slotOf(side, k) { return sides()[side].mons[k]; }
  function edits() { return state.edits[state.mode]; }
  function opts(extraEdits, habit) {
    return { order: state.order, plan: state.mode === 3 ? state.plan : "free", habits: ["ai", habit || state.habit], edits: extraEdits || edits() };
  }
  function sideLabel(t) { return state.mode === 3 ? TEAM_NAME[t] : SIDE_NAME[t]; }
  /** 設定改變時清除沙盒修改（第幾發的定位已經不適用）。 */
  function clearSandbox() {
    if (edits().length || state.habit !== "ai") toast("已清除沙盒修改");
    state.edits[state.mode] = []; state.habit = "ai"; state.sel = null; state.ghost = null;
  }

  // ---------- 網址 ----------
  function encIV(iv) {
    return iv.mode === "best" ? "b" : iv.mode === "hundo" ? "h" : iv.mode === "custom" ? ("c" + [iv.atk, iv.def, iv.hp, iv.level || 0].join("-")) : "d";
  }
  function decIV(s) {
    if (s === "b") return { mode: "best" };
    if (s === "h") return { mode: "hundo" };
    if (s && s.charAt(0) === "c") {
      var v = s.slice(1).split("-").map(Number);
      return { mode: "custom", atk: v[0] || 0, def: v[1] || 0, hp: v[2] || 0, level: v[3] || 0 };
    }
    return { mode: "def" };
  }
  function encSide(s) {
    return [s.id, s.fast, s.c1, s.c2 || "-", encIV(s.iv), s.shields, s.energy || 0, s.hpPct || 100, s.bait ? 1 : 0, s.buddy ? 1 : 0].join(".");
  }
  function encSlot(s) { return [s.id, s.fast, s.c1, s.c2 || "-", encIV(s.iv), s.buddy ? 1 : 0].join("."); }
  function decMon(a) {
    if (!C.mon(a[0]) || C.mon(a[0]).hide) return null;
    var s = newMon(a[0]);
    if (a[1]) s.fast = a[1];
    if (a[2]) s.c1 = a[2];
    if (a[3]) s.c2 = a[3] === "-" ? null : a[3];
    s.iv = decIV(a[4]);
    return s;
  }
  function decSide(str) {
    if (!str || !/^[a-z0-9_.\-]+$/i.test(str)) return null;
    var a = str.split("."), s = decMon(a);
    if (!s) return null;
    s.shields = a[5] == null ? 1 : Math.max(0, Math.min(2, parseInt(a[5], 10) || 0));
    s.energy = Math.max(0, Math.min(100, parseInt(a[6], 10) || 0));
    s.hpPct = Math.max(1, Math.min(100, parseInt(a[7], 10) || 100));
    s.bait = a[8] !== "0";
    s.buddy = a[9] === "1";
    return fixMoves(s);
  }
  function decTeam(str, shields) {
    if (!str || !/^[a-z0-9_.\-~]+$/i.test(str)) return null;
    var mons = str.split("~").slice(0, 3).map(function (x) { var a = x.split("."), s = decMon(a); if (s) s.buddy = a[5] === "1"; return s ? fixMoves(s) : null; });
    if (mons.length !== 3 || mons.some(function (m) { return !m; })) return null;
    var seen = false;
    mons.forEach(function (m) { if (m.buddy) { if (seen) m.buddy = false; seen = true; } });   // 一隊只能有一隻最佳夥伴
    return { mons: mons, shields: shields };
  }
  var EK = { s: "shield", h: "hold", u: "use", w: "swap" }, KE = { shield: "s", hold: "h", use: "u", swap: "w" };
  function encEdits(list) {
    return list.map(function (e) {
      var v = e.k === "shield" ? (e.v ? 1 : 0) : e.k === "hold" ? e.d : e.k === "use" ? e.v : e.to;
      return KE[e.k] + e.side + "." + e.n + "." + v;
    }).join("~");
  }
  function decEdits(str) {
    if (!str || !/^[shuw][01]\.\d{1,2}\.\d(~[shuw][01]\.\d{1,2}\.\d)*$/.test(str)) return [];
    return str.split("~").slice(0, 20).map(function (x) {
      var k = EK[x.charAt(0)], side = Number(x.charAt(1)), p = x.slice(3).split(".").map(Number), e = { k: k, side: side, n: p[0] };
      if (k === "shield") e.v = p[1] === 1; else if (k === "hold") e.d = Math.min(3, Math.max(1, p[1])); else if (k === "use") e.v = p[1] ? 1 : 0; else e.to = Math.min(2, p[1]);
      return e;
    });
  }
  function readURL() {
    var q = {};
    location.search.replace(/^\?/, "").split("&").forEach(function (kv) {
      var i = kv.indexOf("="); if (i > 0) q[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1));
    });
    var l = parseInt(q.l, 10);
    if ([1500, 2500, 10000].indexOf(l) > -1) state.cp = l;
    if (q.cap === "40") state.cap = 40;
    if (q.m === "3") state.mode = 3;
    if (q.o === "f") state.order = "fixed";
    if (q.p === "f") state.plan = "free";
    if (HABITS.some(function (h) { return h[0] === q.oh; })) state.habit = q.oh;
    state.edits[state.mode] = decEdits(q.e).filter(function (e) { return state.mode === 3 || e.k !== "swap"; });
    var ts = (q.ts || "2-2").split("-").map(function (x) { var n = parseInt(x, 10); return isNaN(n) ? 2 : Math.max(0, Math.min(2, n)); });
    return { a: decSide(q.a), b: decSide(q.b), ta: decTeam(q.ta, ts[0]), tb: decTeam(q.tb, ts[1] == null ? 2 : ts[1]) };
  }
  function writeURL() {
    var u = location.pathname + "?l=" + state.cp + (state.cap === 40 ? "&cap=40" : "");
    if (state.mode === 3) {
      u += "&m=3&ta=" + state.teams[0].mons.map(encSlot).join("~") + "&tb=" + state.teams[1].mons.map(encSlot).join("~") +
        "&ts=" + state.teams[0].shields + "-" + state.teams[1].shields + "&o=" + (state.order === "best" ? "b" : "f") + "&p=" + (state.plan === "free" ? "f" : "s");
    } else {
      u += "&a=" + encSide(state.sides[0]) + "&b=" + encSide(state.sides[1]);
    }
    if (state.habit !== "ai") u += "&oh=" + state.habit;
    if (edits().length) u += "&e=" + encEdits(edits());
    try { history.replaceState(null, "", u); } catch (e) { /* file:// 等情況忽略 */ }
  }

  // ---------- 骨架 ----------
  function renderShell() {
    app.innerHTML =
      '<section class="setup" aria-label="對戰設定">' +
        '<div class="bar"><div class="seg mode" id="mode" role="group" aria-label="對戰模式"><button type="button" data-m="1">1 對 1</button><button type="button" data-m="3">3 對 3 隊伍</button></div>' +
          '<div class="seg" id="lg" role="group" aria-label="聯盟">' +
          LEAGUES.map(function (l) { return '<button type="button" data-cp="' + l.cp + '">' + l.name + "</button>"; }).join("") + "</div>" +
          '<div class="seg sm" id="cap" role="group" aria-label="等級上限">' +
          '<button type="button" data-cap="50">最高 Lv50</button><button type="button" data-cap="40">Lv40（不用 XL 糖果）</button></div></div>' +
        '<div id="one"><div class="duel"><div class="side" data-i="0" id="s0"></div>' +
          '<div class="vs"><b>VS</b><button type="button" class="swap" data-act="swap" aria-label="交換雙方">⇄ 交換</button></div>' +
          '<div class="side" data-i="1" id="s1"></div></div></div>' +
        '<div id="three" hidden>' +
          '<div class="bar rules"><span class="lbl">倒下後派誰上場</span><div class="seg sm" id="order" role="group" aria-label="倒下後派誰上場">' +
            '<button type="button" data-o="best">挑最有利的</button><button type="button" data-o="fixed">依隊伍順序</button></div>' +
            '<span class="lbl">護盾分配</span><div class="seg sm" id="plan" role="group" aria-label="護盾分配">' +
            '<button type="button" data-p="spread">平均分配</button><button type="button" data-p="free">需要就用</button></div></div>' +
          '<div class="duel teams"><div class="team" data-t="0" id="t0"></div>' +
          '<div class="vs"><b>VS</b><button type="button" class="swap" data-act="swap" aria-label="交換兩隊">⇄ 交換</button></div>' +
          '<div class="team" data-t="1" id="t1"></div></div>' +
          '<p class="rulenote">AI 不會主動換寶可夢（倒下才換）；要練「切角擋招」，在下方重播圖點對手的特殊招式，選一隻替補換上來擋。護盾整隊共用，' +
          '「平均分配」讓每隻最多用掉「剩餘護盾 ÷ 剩下隻數」面，「需要就用」則照 PvPoke 的 1 對 1 判斷。</p>' +
        "</div>" +
      "</section>" +
      '<section class="card verdict" id="verdict" aria-live="polite"></section>' +
      '<section class="card" id="replay"><h2 class="sec-h"><span class="ic">▶</span>重播與沙盒<small id="rp-sub"></small></h2>' +
        '<div class="habit"><span class="lbl">對手開盾習慣</span><div class="hab" id="hab" role="group" aria-label="對手開盾習慣"></div></div>' +
        '<div class="edits" id="edits"></div>' +
        '<div class="chart" id="chart"></div>' +
        '<div class="legend"><span><i style="background:var(--a)"></i>我方 HP</span><span><i style="background:var(--b)"></i>對手 HP</span>' +
        '<span style="color:var(--a)"><i class="d"></i>我方能量</span><span style="color:var(--b)"><i class="d"></i>對手能量</span>' +
        '<span id="ghostlg" hidden><i class="d" style="border-color:#9a95ad"></i>修改前的 HP</span><span>● 特殊招式（空心＝被擋）</span><span class="keylg">◎ 關鍵決策</span></div>' +
        '<div class="act" id="act"></div>' +
        '<div class="player"><button type="button" id="play" aria-label="播放">▶</button><input type="range" id="scrub" min="0" max="1" value="0" aria-label="回合"><span class="tn" id="tn"></span></div>' +
        '<div class="states" id="states"></div><p class="now" id="now"></p></section>' +
      '<section class="card" id="mxc"><h2 class="sec-h"><span class="ic">🛡</span>9 種盾數組合<small>不含沙盒修改，點格子切換</small></h2><div class="mxwrap" id="mx"></div>' +
        '<p class="mxnote" id="mxnote"></p></section>' +
      '<section class="card" id="logc"><h2 class="sec-h"><span class="ic">📜</span>對戰紀錄<small>點 ✎ 可以修改那一發</small></h2>' +
        '<div class="logtools"><label class="tgl"><input type="checkbox" id="logall"> 顯示每一次一般招式</label></div><ol class="log" id="log"></ol></section>' +
      '<section class="card" id="movec"><h2 class="sec-h"><span class="ic">⚔️</span>招式與能力值<small id="mv-sub">傷害是打在對方身上的實際數值</small></h2><div class="mtab" id="mtab"></div></section>' +
      '<section class="card" id="cmpc"><h2 class="sec-h"><span class="ic">🔁</span>換招比較<small>同一個對手、同樣盾數</small></h2>' +
        '<div class="bar"><div class="seg sm" id="cmpwho" role="group" aria-label="比較哪一方"><button type="button" data-w="0">我方換招</button><button type="button" data-w="1">對手換招</button></div></div>' +
        '<ul class="cmp" id="cmp"></ul><button type="button" class="more" id="cmpmore">顯示全部組合</button></section>' +
      '<section class="card" id="swc"><h2 class="sec-h"><span class="ic">📊</span>我方對上熱門寶可夢<small id="sw-sub"></small></h2>' +
        '<div class="swtools"><div class="seg sm" id="swn" role="group" aria-label="對手數量"><button type="button" data-n="30">前 30 名</button><button type="button" data-n="50">前 50 名</button><button type="button" data-n="100">前 100 名</button></div>' +
        '<div class="seg sm" id="sws" role="group" aria-label="護盾"><button type="button" data-s="0">雙方 0 盾</button><button type="button" data-s="1">雙方 1 盾</button><button type="button" data-s="2">雙方 2 盾</button></div>' +
        '<div class="seg sm" id="swo" role="group" aria-label="排序"><button type="button" data-o="rank">依排名</button><button type="button" data-o="rating">依評分</button></div></div>' +
        '<div class="prog" id="swprog"><i></i></div><div class="swsum" id="swsum"></div><ul class="swgrid" id="swgrid"></ul>' +
        '<p class="mxnote">對手都用 PvPoke 推薦招式與預設 IV；點任一隻就會換成牠當對手。</p></section>';
  }

  // ---------- 設定卡（1 對 1 的一方與 3 對 3 的一隻共用） ----------
  function moveOptions(list, cur, withNone) {
    var o = withNone ? ['<option value=""' + (!cur ? " selected" : "") + ">（不帶第二招）</option>"] : [];
    list.forEach(function (x) {
      var m = C.move(x.id); if (!m) return;
      var stats = m.energyGain > 0 ? ("威力 " + m.power + "・能量 +" + m.energyGain + "・" + m.turns + " 回合") : ("威力 " + m.power + "・能量 " + m.energy);
      o.push('<option value="' + esc(x.id) + '"' + (x.id === cur ? " selected" : "") + ">" + esc(m.name) + "（" + esc(C.typeZh(m.type)) + "）" + stats + (x.elite ? " ★限定" : "") + "</option>");
    });
    return o.join("");
  }
  function selWrap(k, id, inner, fast) {
    var m = C.move(id);
    return '<div class="sel' + (fast ? " f" : "") + '" style="--c:' + (m ? TYPE_COLOR[m.type] : "#bbb") + '" data-ti="' + (m ? esc(tch(m.type)) : "－") + '">' +
      '<select data-k="' + k + '" aria-label="' + (k === "fast" ? "一般招式" : k === "c1" ? "特殊招式 1" : "特殊招式 2") + '">' + inner + "</select></div>";
  }
  function whoButton(s, label, pv) {
    return '<button type="button" class="who" data-act="pick" aria-label="更換' + esc(label) + '">' + pic(s.id) +
      '<span style="min-width:0"><span class="nm">' + esc(nm(s.id)) + "</span>" +
      '<span class="sub">CP ' + fmt(pv.cp) + " · " + lvTxt(pv.level) + (pv.level > 50 || (state.cap === 40 && pv.level > 40) ? "（最佳夥伴）" : "") +
      " · IV " + pv.atk + "/" + pv.def + "/" + pv.hp + "</span>" + types(s.id) + '</span><span class="chg">更換</span></button>';
  }
  function moveFields(s, compact) {
    var p = pools(s.id), rec = isRecommended(s);
    return '<div class="fld">' + (compact ? "" : '<span class="lbl">招式</span>') + '<div class="mvsel">' +
      selWrap("fast", s.fast, moveOptions(p.fast, s.fast), true) +
      selWrap("c1", s.c1, moveOptions(p.charged, s.c1)) +
      (p.charged.length > 1 ? selWrap("c2", s.c2, moveOptions(p.charged.filter(function (x) { return x.id !== s.c1; }), s.c2, true)) : "") +
      "</div>" + (rec === true ? '<p class="mvinfo">✓ 這是 PvPoke 在' + lgName() + "的推薦招式</p>"
        : (rec === false ? '<p class="mvinfo"><a href="#" data-act="recmoves">改回推薦招式</a></p>' : "")) + "</div>";
  }
  function ivFields(s, pv) {
    var h = '<div class="fld"><div class="fld inl" style="margin:0"><span class="lbl">IV</span><div class="seg sm" role="group" aria-label="IV">' +
      IVMODES.map(function (x) { return '<button type="button" data-iv="' + x[0] + '" aria-pressed="' + (s.iv.mode === x[0]) + '">' + x[1] + "</button>"; }).join("") + "</div></div>";
    if (s.iv.mode === "best") h += '<p class="ivhint">能力值乘積第 1 名：總耐久最高，攻擊通常壓到最低。同種寶可夢對打、或雙方同時放特殊招式時，攻擊較高的一方會先出手，所以有時反而輸給 100%。</p>';
    if (s.iv.mode === "custom") {
      var opt = function (v) { var o = ""; for (var n = 0; n <= 15; n++) o += '<option value="' + n + '"' + (n === v ? " selected" : "") + ">" + n + "</option>"; return o; };
      var lv = '<option value="0"' + (!s.iv.level ? " selected" : "") + ">自動（最高 " + lvTxt(pv.maxLevel) + "）</option>";
      for (var L = pv.maxLevel; L >= 1; L -= 0.5) lv += '<option value="' + L + '"' + (Number(s.iv.level) === L ? " selected" : "") + ">" + lvTxt(L) + "</option>";
      h += '<div class="ivs"><label>攻擊<select data-ivk="atk">' + opt(s.iv.atk) + '</select></label><label>防禦<select data-ivk="def">' + opt(s.iv.def) +
        '</select></label><label>HP<select data-ivk="hp">' + opt(s.iv.hp) + '</select></label><label>等級<select data-ivk="level">' + lv + "</select></label></div>" +
        '<p class="ivsum">CP <b>' + fmt(pv.cp) + "</b> · " + lvTxt(pv.level) + " · 攻擊 " + pv.atk + " / 防禦 " + pv.def + " / HP " + pv.hp + "</p>";
    }
    h += '<p class="bud"><label class="tgl"><input type="checkbox" data-k="buddy"' + (s.buddy ? " checked" : "") + "> 最佳夥伴（等級上限 +1，可到 " + lvTxt(s.buddy ? pv.cap : pv.cap + 1) + "）</label></p>";
    return h + "</div>";
  }

  function renderSide(i) {
    var s = state.sides[i], m = C.mon(s.id), pv = C.ivPreview(s.id, s.iv, cfg(), s.buddy);
    var sh = C.shadowOf(s.id), rk = C.rankOf(s.id, String(state.cp));
    var h = '<div class="side-h"><span class="tag">' + SIDE_NAME[i] + "</span>" +
      (rk ? '<span class="rk">' + lgName() + " 排名 #" + rk.rank + "</span>" : '<span class="rk">未列入排名</span>') +
      (sh ? '<button type="button" class="shbtn" data-act="shadow" aria-pressed="' + (!!m.sh) + '">' + (m.sh ? "✓ 暗影" : "暗影") + "</button>" : "") + "</div>" +
      whoButton(s, SIDE_NAME[i] + "的寶可夢", pv) + moveFields(s);
    h += '<div class="fld inl"><span class="lbl">護盾</span><div class="shd" role="group" aria-label="護盾數">' +
      [0, 1, 2].map(function (n) { return '<button type="button" data-sh="' + n + '" aria-pressed="' + (s.shields === n) + '">' + SHIELD_SVG + n + "</button>"; }).join("") + "</div></div>";
    h += ivFields(s, pv);
    h += '<details class="adv"' + (s.energy || s.hpPct < 100 || !s.bait ? " open" : "") + "><summary>進階設定（起始能量、HP、騙盾）</summary>" +
      '<div class="g"><span>起始能量</span><input type="range" min="0" max="100" step="1" value="' + s.energy + '" data-k="energy" aria-label="起始能量"><span class="v">' + s.energy + "</span>" +
      '<span>起始 HP</span><input type="range" min="1" max="100" step="1" value="' + s.hpPct + '" data-k="hpPct" aria-label="起始 HP 百分比"><span class="v">' + s.hpPct + "%</span></div>" +
      '<p style="margin:8px 0 0"><label class="tgl"><input type="checkbox" data-k="bait"' + (s.bait ? " checked" : "") + "> 有兩招特殊招式時，會先用便宜的招式騙盾</label></p></details>";
    $("#s" + i).innerHTML = h;
  }

  function renderTeam(t) {
    var T = state.teams[t];
    var h = '<div class="side-h"><span class="tag">' + TEAM_NAME[t] + '</span><div class="shd" role="group" aria-label="整隊護盾數"><span class="lbl" style="margin-right:4px">護盾</span>' +
      [0, 1, 2].map(function (n) { return '<button type="button" data-tsh="' + n + '" aria-pressed="' + (T.shields === n) + '">' + SHIELD_SVG + n + "</button>"; }).join("") + "</div></div>";
    T.mons.forEach(function (s, k) {
      var pv = C.ivPreview(s.id, s.iv, cfg(), s.buddy), m = C.mon(s.id), sh = C.shadowOf(s.id);
      h += '<div class="slot" data-k="' + k + '"><div class="slot-h"><span class="no">' + (k + 1) + "</span><span>" + SLOT_NAME[k] + "</span>" +
        (sh ? '<button type="button" class="shbtn sm" data-act="shadow" aria-pressed="' + (!!m.sh) + '">' + (m.sh ? "✓ 暗影" : "暗影") + "</button>" : "") +
        '<span class="ord">' + (k > 0 ? '<button type="button" data-act="up" aria-label="往前移">▲</button>' : "") +
        (k < 2 ? '<button type="button" data-act="down" aria-label="往後移">▼</button>' : "") + "</span></div>" +
        whoButton(s, TEAM_NAME[t] + "第 " + (k + 1) + " 隻", pv) +
        '<div class="slot-mv">' + mvChip(s.fast) + mvChip(s.c1) + (s.c2 ? mvChip(s.c2) : "") + (s.buddy ? '<span class="tagx bf">最佳夥伴</span>' : "") + "</div>" +
        '<details class="edit" data-open="' + t + "-" + k + '"' + (openSlots[t + "-" + k] ? " open" : "") + "><summary>調整招式、IV、最佳夥伴</summary>" +
        moveFields(s, true) + ivFields(s, pv) + "</details></div>";
    });
    $("#t" + t).innerHTML = h;
  }

  // ---------- 結果摘要 ----------
  /** 一場結果的分數（給顏色與比較用）：1 對 1 用我方評分，3 對 3 用雙方剩餘 HP 比例換算。 */
  function outcome(r) {
    if (state.mode === 1) {
      var s = r.ratings[0];
      return { score: s, text: (s > 500 ? "勝" : s < 500 ? "敗" : "平") + " " + s };
    }
    var sc = function (t) { return r.hpLeft[t].reduce(function (a, h, k) { return a + h / r.maxHp[t][k]; }, 0); };
    var m = sc(0) - sc(1), score = Math.round(500 + Math.max(-1, Math.min(1, m / 2)) * 400);
    if (r.winner === 0 && score <= 500) score = 501;
    if (r.winner === 1 && score >= 500) score = 499;
    return { score: score, text: (r.winner === 0 ? "勝" : r.winner === 1 ? "敗" : "平") + " " + r.left[0] + ":" + r.left[1] };
  }
  function badge(r, cur) {
    var o = outcome(r), c = rc(o.score);
    return '<span class="ob" style="--cbg:' + c.bg + ";--cfg:" + c.fg + '">' + o.text + (cur ? "" : "") + "</span>";
  }

  function renderVerdict() {
    var w = res.winner, el = $("#verdict"), n = edits().length + (state.habit !== "ai" ? 1 : 0);
    el.className = "card verdict" + (w === 0 ? " w0" : w === 1 ? " w1" : "");
    var big = w === -1 ? "平手" : (w === 0 ? "勝 ─ 敗" : "敗 ─ 勝");
    var tag = n ? '<span class="sbx">沙盒：已修改 ' + n + " 處</span>" : "";
    var act = '<div class="vd-act"><button type="button" data-act="share">🔗 複製這場對戰的連結</button><button type="button" data-act="swap">⇄ 交換' + (state.mode === 3 ? "兩隊" : "雙方") + "</button>" +
      (n ? '<button type="button" data-act="reset">↺ 全部復原</button>' : "") + "</div>";
    if (state.mode === 1) {
      var pr = C.pair(cfg(), state.sides[0], state.sides[1]);
      var r1 = { winner: w, ratings: res.ratings, hp: res.hp, maxHp: [res.maxHp[0][0], res.maxHp[1][0]], lastTurn: res.lastTurn, events: res.events,
        moves: pr.moves, info: pr.info, shieldsLeft: res.shieldsLeft };
      var names = [nm(state.sides[0].id), nm(state.sides[1].id)];
      var mon = function (i) {
        var lost = w > -1 && w !== i;
        return '<div class="vd-mon' + (i ? " r" : "") + (lost ? " lost" : "") + '">' + pic(state.sides[i].id) + '<span style="min-width:0"><span class="vd-nm">' + esc(names[i]) +
          (w === i ? '<span class="crown">勝</span>' : "") + '</span><span class="vd-sub">' + SIDE_NAME[i] + " · CP " + fmt(pr.info[i].cp) + " · " + pr.info[i].shields + " 盾</span></span></div>";
      };
      var hpb = function (i) {
        var pct = r1.hp[i] / r1.maxHp[i] * 100;
        return '<div class="hpb' + (i ? " r" : "") + (r1.hp[i] <= 0 ? " dead" : pct < 30 ? " lowhp" : "") + '">剩餘 HP ' + r1.hp[i] + "／" + r1.maxHp[i] +
          '<div class="t"><i style="width:' + pct.toFixed(1) + '%"></i></div></div>';
      };
      var ins = C.insights(r1, names.map(esc), n ? null : mx);
      el.innerHTML = tag + '<div class="vd-top">' + mon(0) + '<div class="vd-res"><span class="big">' + big + '</span><span class="score">評分 ' + res.ratings[0] + " : " + res.ratings[1] + "</span></div>" + mon(1) + "</div>" +
        '<div class="hpbars">' + hpb(0) + hpb(1) + "</div>" + '<ul class="ins">' + ins.map(function (s) { return "<li>" + s + "</li>"; }).join("") + "</ul>" + act;
      return;
    }
    var row = function (t) {
      return '<div class="tv-row' + (t ? " r" : "") + '">' + state.teams[t].mons.map(function (m, k) {
        var hp = res.hpLeft[t][k], mh = res.maxHp[t][k], pct = hp / mh * 100;
        return '<div class="tv-mon' + (hp <= 0 ? " ko" : "") + '">' + pic(m.id) + '<span class="tv-nm">' + esc(nm(m.id)) + "</span>" +
          '<span class="tv-hp"><i style="width:' + pct.toFixed(0) + "%;background:" + (pct < 30 ? "#f59e0b" : "#10b981") + '"></i></span></div>';
      }).join("") + "</div>";
    };
    var names3 = [state.teams[0].mons.map(function (m) { return esc(nm(m.id)); }), state.teams[1].mons.map(function (m) { return esc(nm(m.id)); })];
    var ins3 = C.teamInsights(res, names3, TEAM_NAME);
    var flow = res.switches.map(function (s) {
      return '<button type="button" class="fl" data-jump="' + s.turn + '">第 ' + s.turn + " 回合 " + (s.side ? "對手" : "我方") + "換上 " + esc(nm(state.teams[s.side].mons[s.to].id)) +
        '<small>' + (s.kind === "manual" ? "切角擋招" : "倒下後上場") + "</small></button>";
    }).join("");
    el.innerHTML = tag + '<div class="tv"><div><span class="vd-sub">' + TEAM_NAME[0] + " · " + state.teams[0].shields + " 盾</span>" + row(0) + "</div>" +
      '<div class="vd-res"><span class="big">' + big + '</span><span class="score">剩下 ' + res.left[0] + " : " + res.left[1] + " 隻</span></div>" +
      '<div class="tvr"><span class="vd-sub">' + TEAM_NAME[1] + " · " + state.teams[1].shields + " 盾</span>" + row(1) + "</div></div>" +
      '<ul class="ins">' + ins3.map(function (s) { return "<li>" + s + "</li>"; }).join("") + "</ul>" +
      (flow ? '<div class="flow"><span class="vd-sub">對戰經過（點一下跳到那一回合）</span><div>' + flow + "</div></div>" : "") + act;
  }

  function mxTable(cell) {
    var h = '<table class="mx"><thead><tr><th></th><th colspan="3">對手的護盾</th></tr><tr><th>我方</th>' +
      [0, 1, 2].map(function (j) { return "<th>" + j + " 盾</th>"; }).join("") + "</tr></thead><tbody>";
    for (var i = 0; i <= 2; i++) {
      h += "<tr><th>" + i + " 盾</th>";
      for (var j = 0; j <= 2; j++) {
        var x = cell(i, j);
        h += '<td><button type="button" data-mx="' + i + "," + j + '" style="--cbg:' + x.c.bg + ";--cfg:" + x.c.fg + '" aria-current="' + x.cur + '" aria-label="我方 ' + i + " 盾、對手 " + j + " 盾，" + esc(x.label) + '">' +
          x.big + "<small>" + x.small + "</small></button></td>";
      }
      h += "</tr>";
    }
    return h + "</tbody></table>";
  }
  function renderMatrix() {
    var S = sides(), s0 = S[0].shields, s1 = S[1].shields;
    if (state.mode === 1) {
      $("#mx").innerHTML = mxTable(function (i, j) {
        var r = mx[i][j];
        return { c: rc(r), cur: i === s0 && j === s1, big: r, small: r > 500 ? "勝" : r < 500 ? "敗" : "平", label: "評分 " + r };
      });
      $("#mxnote").textContent = "數字是我方的對戰評分（0～1000，超過 500 就是贏）。直的是我方護盾數，橫的是對手護盾數。";
    } else {
      $("#mx").innerHTML = mxTable(function (i, j) {
        var x = mx[i][j], r = 500 + Math.max(-1, Math.min(1, x.margin / 2)) * 400;
        return { c: rc(Math.round(r)), cur: i === s0 && j === s1, big: x.winner === 0 ? "勝" : x.winner === 1 ? "敗" : "平",
          small: "剩 " + x.left[0] + "：" + x.left[1], label: (x.winner === 0 ? "我方勝" : x.winner === 1 ? "對手勝" : "平手") + "，剩 " + x.left[0] + " 比 " + x.left[1] + " 隻" };
      });
      $("#mxnote").textContent = "整隊護盾數的 9 種組合。「剩 2：0」代表打完我方還剩 2 隻、對手 0 隻；顏色越深代表贏（或輸）得越多。";
    }
  }

  // ---------- 沙盒：對手開盾習慣、修改清單、選項面板 ----------
  function withEdit(list, e) {
    // 同一個位置（種類、哪一方、第幾發）只保留一個修改；換人擋招同時會改那一發的開盾
    var out = list.filter(function (x) { return !(x.k === e.k && x.side === e.side && x.n === e.n); });
    out.push(e);
    return out;
  }
  function editText(e) {
    var who = sideLabel(e.side);
    if (e.k === "shield") return who + "第 " + e.n + " 次被打：" + (e.v ? "開盾" : "不開盾");
    if (e.k === "hold") return who + "第 " + e.n + " 發：晚 " + e.d + " 回合放";
    if (e.k === "use") return who + "第 " + e.n + " 發：改放第 " + (e.v + 1) + " 招";
    return "換上 " + nm(slotOf(e.side, e.to).id) + " 擋對手第 " + e.n + " 發";
  }
  function renderSandboxBar() {
    var list = edits();
    $("#hab").innerHTML = HABITS.map(function (h) {
      var r = h[0] === state.habit ? res : C.match(cfg(), sides(), opts(null, h[0]));
      return '<button type="button" data-hab="' + h[0] + '" aria-pressed="' + (state.habit === h[0]) + '"><span>' + h[1] + "</span>" + badge(r) + "</button>";
    }).join("");
    $("#edits").innerHTML = list.length ? list.map(function (e, i) {
      var st = res.editStatus[i];
      return '<span class="chip' + (st !== "ok" ? " warn" : "") + '">' + esc(editText(e)) + (st !== "ok" ? '<small>⚠ ' + esc(FAIL_TEXT[st] || "沒有套用") + "</small>" : "") +
        '<button type="button" data-unedit="' + i + '" aria-label="移除這個修改">×</button></span>';
    }).join("") + '<button type="button" class="chip reset" data-act="reset">↺ 全部復原</button>'
      : '<p class="hint">👆 點圖上的特殊招式圓圈（或對戰紀錄的 ✎），就能改<b>開不開盾</b>、<b>延後放招</b>、<b>改放另一招</b>' + (state.mode === 3 ? "，或<b>換人擋招</b>" : "") + "，每個選項都會先算好結果。</p>";
    $("#ghostlg").hidden = !state.ghost;
  }

  function optButton(label, list, current, extra) {
    var r = C.match(cfg(), sides(), opts(list));
    return '<button type="button" class="opt' + (current ? " on" : "") + '" data-edits="' + esc(encEdits(list)) + '"' + (extra || "") + ">" + label + badge(r) + "</button>";
  }
  function renderAct() {
    var el = $("#act");
    if (state.sel == null || !res.events[state.sel] || res.events[state.sel].kind !== "charged") { el.innerHTML = ""; el.hidden = true; return; }
    el.hidden = false;
    var e = res.events[state.sel], a = e.actor, d = 1 - a, list = edits();
    var att = slotOf(a, e.mon), def = slotOf(d, e.opMon);
    var cur = function (k, side, n) { return list.filter(function (x) { return x.k === k && x.side === side && x.n === n; })[0]; };
    var h = '<div class="act-h">' + pic(att.id) + "<div><b>第 " + e.turn + " 回合</b> · " + esc(nm(att.id)) + "（" + sideLabel(a) + "第 " + e.n + " 發）使出 " + mvChip(e.moveId) +
      " → " + esc(nm(def.id)) + (e.shielded ? '<span class="tagx sh">被擋</span>' : "，" + e.dmg + " 傷害") + '</div><button type="button" class="x" data-act="unsel" aria-label="關閉">×</button></div>';
    // 1. 防守方開不開盾
    var shBefore = res.series[Math.max(0, e.turn - 1)].sh[d];
    if (shBefore > 0 || e.shielded) {
      h += '<div class="act-r"><span class="lbl">' + esc(nm(def.id)) + " 要不要開盾</span><div class=\"opts\">" +
        optButton(SHIELD_SVG + "開盾", withEdit(list, { k: "shield", side: d, n: e.m, v: true }), e.shielded) +
        optButton("✕ 不開盾", withEdit(list, { k: "shield", side: d, n: e.m, v: false }), !e.shielded) + "</div></div>";
    }
    // 2. 攻擊方放招時機
    var ho = cur("hold", a, e.n), hv = ho ? ho.d : 0;
    var hl = function (dd) { return dd ? withEdit(list, { k: "hold", side: a, n: e.n, d: dd }) : list.filter(function (x) { return !(x.k === "hold" && x.side === a && x.n === e.n); }); };
    h += '<div class="act-r"><span class="lbl">' + esc(nm(att.id)) + " 放招時機</span><div class=\"opts\">" +
      optButton("照原本", hl(0), hv === 0) + optButton("晚 1 回合", hl(1), hv === 1) + optButton("晚 2 回合", hl(2), hv === 2) + optButton("晚 3 回合", hl(3), hv === 3) + "</div></div>";
    // 3. 改放另一招
    if (att.c2) {
      var uo = cur("use", a, e.n);
      h += '<div class="act-r"><span class="lbl">放哪一招</span><div class="opts">' + [att.c1, att.c2].map(function (mid, v) {
        var l = withEdit(list, { k: "use", side: a, n: e.n, v: v });
        return optButton(mvChip(mid), l, uo ? uo.v === v : e.moveId === mid);
      }).join("") + "</div></div>";
    }
    // 4. 切角擋招（3 對 3）：防守方換一隻有抗性的上來吃這招
    if (state.mode === 3) {
      var so = cur("swap", d, e.n), before = res.series[Math.max(0, e.turn - 1)], orig = before.cur[d], bench = [];
      sides()[d].mons.forEach(function (m, k) { if (k !== orig && before.all[d][k] > 0) bench.push(k); });
      if (bench.length) {
        var ok = res.swapOk[d][e.turn] || (so && res.editStatus[list.indexOf(so)] === "ok");
        var card = function (k, note) {
          var sl = slotOf(d, k), mv = C.pair(cfg(), att, sl).moves[0].filter(function (x) { return x.id === e.moveId; })[0];
          var ef = mv ? C.effWord(mv.eff) : "";
          return pic(sl.id) + '<span class="sw-t"><b>' + esc(nm(sl.id)) + (note ? "<em>" + note + "</em>" : "") + "</b><small>" + (mv ? "約吃 " + mv.damage + "（" + mv.pct + "%）" : "") + "</small>" +
            (ef ? '<span class="efx ' + (mv.eff > 1 ? "dn" : "up") + '">' + (mv.eff > 1 ? "被剋" : "抗性") + "</span>" : "") + "</span>";
        };
        h += '<div class="act-r"><span class="lbl">切角擋招：' + sideLabel(d) + "換一隻上來吃這招</span>" +
          (ok ? "" : '<p class="warn">⚠ 這一回合' + esc(nm(slotOf(d, orig).id)) + "還在出一般招式或換人冷卻中，引擎判定來不及換。</p>") + '<div class="opts">';
        h += optButton(card(orig, "不換"), list.filter(function (x) { return x !== so; }), !so, ' data-sw="1"');
        bench.forEach(function (k) {
          var l = withEdit(withEdit(list, { k: "swap", side: d, n: e.n, to: k }), { k: "shield", side: d, n: e.m, v: false });
          h += optButton(card(k, ""), l, !!(so && so.to === k), ' data-sw="1"' + (ok ? "" : " disabled"));
        });
        h += "</div><p class=\"mvinfo\">換上去的那隻預設不開盾（擋招通常是為了省盾），換完可以再點這一發改成開盾。</p></div>";
      }
    }
    el.innerHTML = h;
  }

  /** 關鍵決策：把某一發的開盾決定反過來，勝負就會改變的，在圖上加外框。 */
  function markKeyDecisions() {
    var job = ++keyJob, list = edits(), evs = [];
    res.events.forEach(function (e, i) {
      if (e.kind !== "charged") return;
      var d = 1 - e.actor;
      if (res.series[Math.max(0, e.turn - 1)].sh[d] > 0 || e.shielded) evs.push(i);
    });
    var base = outcome(res), k = 0;
    (function next() {
      if (job !== keyJob || k >= evs.length) return;
      var i = evs[k++], e = res.events[i];
      var r = C.match(cfg(), sides(), opts(withEdit(list, { k: "shield", side: 1 - e.actor, n: e.m, v: !e.shielded })));
      var o = outcome(r);
      if ((o.score > 500) !== (base.score > 500) || Math.abs(o.score - base.score) >= 150) {
        var g = $('#chart [data-ei="' + i + '"]'); if (g) g.classList.add("key");
      }
      setTimeout(next, 0);
    })();
  }

  // ---------- 重播 ----------
  var CH = { W: 1000, H: 286, L: 40, R: 14, laneA: 20, top: 44, bot: 236, laneB: 264 };
  function sizeChart() {
    var w = Math.round(($("#chart") && $("#chart").clientWidth) || 1000);
    CH.W = Math.max(300, w);
    var small = CH.W < 640;
    CH.L = small ? 34 : 40; CH.R = small ? 10 : 14;
    CH.H = small ? 250 : 286; CH.laneA = 18; CH.top = 40; CH.bot = CH.H - 50; CH.laneB = CH.H - 22;
  }
  function cx(t) { return CH.L + (t / Math.max(1, res.lastTurn)) * (CH.W - CH.L - CH.R); }
  function cy(p) { return CH.bot - p * (CH.bot - CH.top); }
  function idAt(side, k) { return slotOf(side, k).id; }
  function renderChart() {
    sizeChart();
    var T = res.lastTurn, s = res.series, h = [], t, small = CH.W < 640;
    h.push('<svg viewBox="0 0 ' + CH.W + " " + CH.H + '" role="img" aria-label="雙方 HP 與能量隨回合變化，點特殊招式可以修改">');
    [0, 0.5, 1].forEach(function (p) {
      h.push('<line x1="' + CH.L + '" x2="' + (CH.W - CH.R) + '" y1="' + cy(p) + '" y2="' + cy(p) + '" stroke="#ece8f6" stroke-width="1"/>');
      h.push('<text x="' + (CH.L - 6) + '" y="' + (cy(p) + 4) + '" font-size="12" text-anchor="end" fill="#9a95ad">' + (p * 100) + "%</text>");
    });
    var step = T > 160 ? 40 : T > 120 ? 20 : T > 60 ? 10 : (small && T > 30 ? 10 : 5);
    for (t = step; t < T; t += step) {
      h.push('<line x1="' + cx(t) + '" x2="' + cx(t) + '" y1="' + CH.top + '" y2="' + CH.bot + '" stroke="#f3f1f8"/>');
      h.push('<text x="' + cx(t) + '" y="' + (CH.bot + 14) + '" font-size="11" text-anchor="middle" fill="#9a95ad">' + t + "</text>");
    }
    h.push('<rect x="' + CH.L + '" y="' + (CH.laneA - 12) + '" width="' + (CH.W - CH.L - CH.R) + '" height="24" rx="12" fill="#fff4f8"/>');
    h.push('<rect x="' + CH.L + '" y="' + (CH.laneB - 12) + '" width="' + (CH.W - CH.L - CH.R) + '" height="24" rx="12" fill="#f5f2ff"/>');
    h.push('<text x="' + (CH.L - 6) + '" y="' + (CH.laneA + 4) + '" font-size="11" text-anchor="end" fill="#e0276c" font-weight="800">我方</text>');
    h.push('<text x="' + (CH.L - 6) + '" y="' + (CH.laneB + 4) + '" font-size="11" text-anchor="end" fill="#6d4aff" font-weight="800">對手</text>');
    var line = function (ser, fn, color, dash, width, op) {
      var pts = [cx(0) + "," + cy(fn(ser[0]))];
      for (t = 1; t < ser.length; t++) { pts.push(cx(t) + "," + cy(fn(ser[t - 1]))); pts.push(cx(t) + "," + cy(fn(ser[t]))); }
      return '<polyline fill="none" stroke="' + color + '" stroke-width="' + width + '" stroke-linejoin="round"' + (dash ? ' stroke-dasharray="' + dash + '"' : "") + (op ? ' opacity="' + op + '"' : "") + ' points="' + pts.join(" ") + '"/>';
    };
    if (state.ghost) {
      var gs = state.ghost.filter(function (x, i) { return i <= T; });
      [0, 1].forEach(function (i) { h.push(line(gs, function (x) { return x.hp[i] / x.max[i]; }, "#9a95ad", "3 4", 2.2, ".9")); });
    }
    [0, 1].forEach(function (i) { h.push(line(s, function (x) { return x.en[i] / 100; }, i ? "#6d4aff" : "#e0276c", "5 5", 2, ".55")); });
    [0, 1].forEach(function (i) { h.push(line(s, function (x) { return x.hp[i] / x.max[i]; }, i ? "#6d4aff" : "#e0276c", "", 3.2)); });
    res.events.forEach(function (e, idx) {
      var y = e.actor ? CH.laneB : CH.laneA, x = cx(e.turn), c = TYPE_COLOR[e.type] || "#888";
      if (e.kind === "fast") {
        h.push('<circle cx="' + x + '" cy="' + y + '" r="' + (small ? 2.2 : 2.8) + '" fill="' + c + '" opacity=".75"/>');
      } else if (e.kind === "charged") {
        var r = small ? 9 : 11;
        h.push('<line x1="' + x + '" x2="' + x + '" y1="' + (e.actor ? CH.top : y + 12) + '" y2="' + (e.actor ? y - 12 : CH.bot) + '" stroke="' + c + '" stroke-width="1" stroke-dasharray="2 4" opacity=".6"/>');
        h.push('<g class="cm' + (state.sel === idx ? " sel" : "") + '" data-ei="' + idx + '" tabindex="0" role="button" aria-label="第 ' + e.turn + " 回合 " + esc(e.name) + '，點一下修改">' +
          '<title>第 ' + e.turn + " 回合：" + esc(e.name) + (e.shielded ? "（被護盾擋下）" : "，" + e.dmg + " 傷害") + "｜點一下修改</title>" +
          '<circle class="ring" cx="' + x + '" cy="' + y + '" r="' + (r + 5) + '" fill="none" stroke-width="3"/>' +
          '<circle cx="' + x + '" cy="' + y + '" r="' + r + '" fill="' + (e.shielded ? "#fff" : c) + '" stroke="' + c + '" stroke-width="2.5"/>' +
          '<text x="' + x + '" y="' + (y + 4) + '" font-size="' + (small ? 10 : 11) + '" font-weight="900" text-anchor="middle" fill="' + (e.shielded ? c : "#fff") + '">' + esc(tch(e.type)) + "</text>" +
          '<circle cx="' + x + '" cy="' + y + '" r="' + (r + 9) + '" fill="transparent"/></g>');
      } else if (e.kind === "faint") {
        h.push('<text x="' + x + '" y="' + (y + 5) + '" font-size="15" font-weight="900" text-anchor="middle" fill="#d6334a">✕</text>');
      } else if (e.kind === "switch") {
        h.push('<g><title>第 ' + e.turn + " 回合：換上 " + esc(nm(idAt(e.actor, e.to))) + (e.manual ? "（切角擋招）" : "") + "</title>" +
          '<rect x="' + (x - 11) + '" y="' + (y - 9) + '" width="22" height="18" rx="6" fill="' + (e.manual ? "#f59e0b" : "#14111f") + '"/>' +
          '<text x="' + x + '" y="' + (y + 4) + '" font-size="11" font-weight="900" text-anchor="middle" fill="#fff">⇄</text></g>');
      }
    });
    // 游標不接收點擊，才不會擋住底下的特殊招式圓圈
    h.push('<g pointer-events="none"><line id="cur" x1="0" x2="0" y1="' + (CH.laneA - 14) + '" y2="' + (CH.laneB + 14) + '" stroke="#14111f" stroke-width="1.5" opacity=".7"/>');
    h.push('<circle id="cur0" r="5" fill="#e0276c" stroke="#fff" stroke-width="2"/><circle id="cur1" r="5" fill="#6d4aff" stroke="#fff" stroke-width="2"/></g>');
    h.push("</svg>");
    $("#chart").innerHTML = h.join("");
    $("#scrub").max = T;
    $("#rp-sub").textContent = "共 " + T + " 回合 · 約 " + (Math.round(T / 2 * 10) / 10) + " 秒";
  }

  function buffText(e) {
    var m = C.move(e.moveId); if (!m || !m.buffs) return "";
    var desc = function (arr) {
      var o = [];
      if (arr[0]) o.push("攻擊 " + (arr[0] > 0 ? "+" : "−") + Math.abs(arr[0]));
      if (arr[1]) o.push("防禦 " + (arr[1] > 0 ? "+" : "−") + Math.abs(arr[1]));
      return o.join("、");
    };
    var me = nm(idAt(e.actor, e.mon)), op = nm(idAt(1 - e.actor, e.opMon));
    if (m.buffTarget === "both") return me + " " + desc(m.buffsSelf) + "；" + op + " " + desc(m.buffsOpponent);
    return (m.buffTarget === "self" ? me : op) + " " + desc(m.buffs);
  }
  function evText(e, rich) {
    if (e.kind === "switch") return "<b>" + sideLabel(e.actor) + "換上 " + esc(nm(idAt(e.actor, e.to))) + "</b>" + '<span class="tagx ' + (e.manual ? "bf" : "sh") + '">' + (e.manual ? "切角擋招" : "倒下後上場") + "</span>";
    var who = esc(nm(idAt(e.actor, e.mon))), op = esc(nm(idAt(1 - e.actor, e.opMon)));
    if (e.kind === "charged") {
      return '<span class="mvn">' + who + "</span> 使出 " + (rich ? mvChip(e.moveId) : "「" + esc(e.name) + "」") +
        (e.shielded ? '<span class="tagx sh">被護盾擋下</span>' : "，對 " + op + " 造成 <b>" + e.dmg + "</b> 傷害（" + e.pct + "%）") +
        (e.buff ? '<span class="tagx bf">' + esc(buffText(e)) + "</span>" : "");
    }
    if (e.kind === "fast") return who + " 用「" + esc(e.name) + "」打出 " + e.dmg + "（+" + e.energy + " 能量）";
    if (e.kind === "faint") return "<b>" + who + ' 倒下</b><span class="tagx ko">' + (state.mode === 3 ? "換下一隻" : "戰鬥結束") + "</span>";
    if (e.kind === "form") return who + " 變身：" + e.text;
    return "";
  }

  var movesKey = "";
  function setTurn(t) {
    t = Math.max(0, Math.min(res.lastTurn, Math.round(t)));
    state.turn = t;
    var st = res.series[t];
    $("#scrub").value = t;
    $("#tn").textContent = "第 " + t + " / " + res.lastTurn + " 回合";
    var x = cx(t), cur = $("#cur");
    if (cur) {
      cur.setAttribute("x1", x); cur.setAttribute("x2", x);
      for (var i = 0; i < 2; i++) { var d = $("#cur" + i); d.setAttribute("cx", x); d.setAttribute("cy", cy(st.hp[i] / st.max[i])); }
    }
    var A = slotOf(0, st.cur[0]), B = slotOf(1, st.cur[1]), pr = C.pair(cfg(), A, B);
    $("#states").innerHTML = [0, 1].map(function (i) {
      var hp = st.hp[i], mh = st.max[i], en = st.en[i];
      var ticks = pr.moves[i].filter(function (m) { return m.kind === "charged"; }).map(function (m) {
        return '<span class="tick' + (en >= m.energy ? " ready" : "") + '" style="left:calc(' + m.energy + '% - 1px)" title="' + esc(m.name) + " 需要 " + m.energy + ' 能量"></span>';
      }).join("");
      var shields = ""; for (var k = 0; k < res.startShields[i]; k++) shields += '<span style="color:' + (k < st.sh[i] ? (i ? "#6d4aff" : "#e0276c") : "#d6d2e0") + '">' + SHIELD_SVG + "</span>";
      return '<div class="st" data-i="' + i + '"><div class="h"><span>' + esc(nm(idAt(i, st.cur[i]))) + '</span><span class="sh-ic" aria-label="剩 ' + st.sh[i] + ' 面護盾">' + shields + "</span></div>" +
        '<div class="meter hp' + (hp / mh < 0.3 ? " low" : "") + '">HP ' + hp + "／" + mh + '<div class="t"><i style="width:' + (hp / mh * 100).toFixed(1) + '%"></i></div></div>' +
        '<div class="meter en">能量 ' + en + "／100" + '<div class="t"><i style="width:' + en + '%"></i>' + ticks + "</div></div></div>";
    }).join("");
    var evs = res.events.filter(function (e) { return e.turn === t && e.kind !== "shield"; });
    $("#now").innerHTML = t === 0 ? "開場：拖曳上方的軸或按 ▶ 播放；點特殊招式圓圈可以修改那一發。"
      : ("<b>第 " + t + " 回合</b>：" + (evs.length ? evs.map(function (e) { return evText(e, false); }).join("；") : "雙方都還在出一般招式的動作中。"));
    $$("#log li").forEach(function (li) { li.classList.toggle("cur", Number(li.getAttribute("data-turn")) === t); });
    var key = st.cur.join(",");
    if (key !== movesKey) { movesKey = key; renderMoves(pr, A, B); }
  }

  function renderLog() {
    var list = [];
    res.events.forEach(function (e, i) { if (e.kind !== "shield" && (state.logAll || e.kind !== "fast")) list.push([e, i]); });
    $("#log").innerHTML = list.map(function (x) {
      var e = x[0];
      return '<li class="' + e.kind + '" data-i="' + e.actor + '" data-turn="' + e.turn + '"><span class="tt">第 ' + e.turn + ' 回合</span><span>' + evText(e, true) +
        (e.kind === "charged" ? '<button type="button" class="ed" data-ei="' + x[1] + '" aria-label="修改這一發">✎</button>' : "") + "</span></li>";
    }).join("") || "<li>沒有特殊招式。</li>";
  }

  function renderMoves(pr, A, B) {
    $("#mv-sub").textContent = state.mode === 3 ? "目前場上：" + nm(A.id) + " 對 " + nm(B.id) + "（拖曳重播軸會跟著換）" : "傷害是打在對方身上的實際數值";
    $("#mtab").innerHTML = [0, 1].map(function (i) {
      var inf = pr.info[i];
      var rows = pr.moves[i].map(function (m) {
        var e = C.effWord(m.eff), ef = e ? '<span class="efx ' + (m.eff > 1 ? "up" : "dn") + '">' + (m.eff > 1 ? "效果絕佳" : "效果不好") + " ×" + (m.eff > 2 ? "2.56" : m.eff > 1 ? "1.6" : m.eff < 0.4 ? "0.39" : "0.625") + "</span>" : "";
        var en = m.kind === "fast" ? ("+" + m.energy + '<span class="k">' + m.turns + " 回合 · 每回合 " + m.dpt + " 傷害 / " + m.ept + " 能量</span>")
          : (m.energy + '<span class="k">要 ' + m.fastNeeded + " 次一般招式（" + m.turnsNeeded + " 回合）</span>");
        return "<tr><td>" + mvChip(m.id, m.elite) + (m.stab ? '<span class="k">同屬性加成 ×1.2</span>' : "") + "</td>" +
          '<td class="n">' + m.damage + '<span class="k">' + m.pct + "% HP</span>" + ef + "</td><td>" + en + "</td></tr>";
      }).join("");
      return '<div class="mt" data-i="' + i + '"><h3><i></i>' + esc(nm(i ? B.id : A.id)) + "</h3>" +
        '<p class="mvinfo" style="margin:0 0 6px">CP ' + fmt(inf.cp) + " · " + lvTxt(inf.level) + " · IV " + inf.ivs.atk + "/" + inf.ivs.def + "/" + inf.ivs.hp +
        " · 攻擊 " + inf.atk + "・防禦 " + inf.def + "・HP " + inf.hp + (inf.shadow ? " · 暗影（攻擊 ×1.2、防禦 ×0.83）" : "") + "</p>" +
        "<table><thead><tr><th>招式</th><th>傷害</th><th>能量</th></tr></thead><tbody>" + rows + "</tbody></table></div>";
    }).join("");
  }

  // ---------- 換招比較、對上熱門（只有 1 對 1，不含沙盒修改） ----------
  function renderCompare() {
    var who = state.cmpWho, list = C.movesetCompare(cfg(), state.sides[0], state.sides[1], who);
    pressed("#cmpwho", "data-w", who);
    var show = state.cmpAll ? list : list.slice(0, 10);
    if (!show.some(function (o) { return o.current; })) { var c = list.filter(function (o) { return o.current; })[0]; if (c) show = show.concat([c]); }
    var pl = pools(state.sides[who].id), el = {};
    pl.fast.concat(pl.charged).forEach(function (m) { el[m.id] = m.elite; });
    $("#cmp").innerHTML = show.map(function (o) {
      var c = rc(o.rating);
      return '<li class="' + (o.current ? "cur" : "") + '" data-f="' + o.fast + '" data-c1="' + o.c1 + '" data-c2="' + (o.c2 || "") + '" title="點一下換成這組招式">' +
        '<span class="ms">' + mvChip(o.fast, el[o.fast]) + mvChip(o.c1, el[o.c1]) + (o.c2 ? mvChip(o.c2, el[o.c2]) : "") + (o.current ? '<span class="tagx bf">目前</span>' : "") + "</span>" +
        '<span class="rb" style="color:' + c.fg + '">' + o.rating + '<i><i style="width:' + (o.rating / 10) + "%;background:" + c.fg + '"></i></i></span></li>';
    }).join("");
    if (list.trimmed) $("#cmp").insertAdjacentHTML("beforeend", '<li class="note" style="cursor:default;background:none;display:block;color:var(--muted);font-size:.8rem">這隻可以學的招式很多，只列出傷害與能量效率最好的組合。</li>');
    $("#cmpmore").hidden = state.cmpAll || list.length <= 10;
    $("#cmpmore").textContent = "顯示全部 " + list.length + " 種組合";
  }
  function withSh(s, n) { var o = {}; for (var k in s) o[k] = s[k]; o.shields = n; return o; }
  function renderSweep() {
    var job = ++sweepJob, top = C.topList(state.cp, state.sweepN), out = [], i = 0, A = state.sides[0];
    pressed("#swn", "data-n", state.sweepN); pressed("#sws", "data-s", state.sweepS); pressed("#swo", "data-o", state.sweepSort);
    $("#sw-sub").textContent = lgName() + "前 " + state.sweepN + " 名";
    var bar = $("#swprog i"); $("#swprog").hidden = false;
    (function chunk() {
      if (job !== sweepJob) return;
      var end = Math.min(top.length, i + 12);
      for (; i < end; i++) {
        var r = top[i];
        out.push({ rank: i + 1, id: r[0],
          rating: C.quick(cfg(), withSh(A, state.sweepS), { id: r[0], fast: r[1], c1: r[2], c2: r[3] || null, iv: { mode: "def" }, shields: state.sweepS }) });
      }
      bar.style.width = (i / top.length * 100) + "%";
      if (i < top.length) { setTimeout(chunk, 0); return; }
      $("#swprog").hidden = true;
      var wins = out.filter(function (o) { return o.rating > 500; }).length, ties = out.filter(function (o) { return o.rating === 500; }).length;
      $("#swsum").innerHTML = '<span class="w">贏 ' + wins + " 隻</span>" + '<span class="l">輸 ' + (out.length - wins - ties) + " 隻</span>" + (ties ? '<span class="t">平手 ' + ties + " 隻</span>" : "") +
        '<span class="t">勝率 ' + Math.round(wins / out.length * 100) + "%</span>";
      var list = out.slice();
      if (state.sweepSort === "rating") list.sort(function (a, b) { return b.rating - a.rating; });
      $("#swgrid").innerHTML = list.map(function (o) {
        var c = rc(o.rating);
        return '<li><button type="button" data-op="' + o.id + '" style="--cbg:' + c.bg + ";--cfg:" + c.fg + '" title="點一下改成和' + esc(nm(o.id)) + '對戰">' +
          '<span class="no">#' + o.rank + "</span>" + pic(o.id) + '<span class="nm">' + esc(nm(o.id)) + '</span><span class="rt">' + o.rating + "</span></button></li>";
      }).join("");
    })();
  }

  // ---------- 主流程 ----------
  /** setup：設定區有沒有變（變了要重算矩陣、換招比較、熱門對手）；keepTurn：保留重播位置。 */
  function update(o) {
    o = o || {};
    stop();
    pressed("#mode", "data-m", state.mode); pressed("#lg", "data-cp", state.cp); pressed("#cap", "data-cap", state.cap);
    var three = state.mode === 3;
    $("#one").hidden = three; $("#three").hidden = !three;
    $("#cmpc").hidden = three; $("#swc").hidden = three;
    if (three) { pressed("#order", "data-o", state.order); pressed("#plan", "data-p", state.plan); renderTeam(0); renderTeam(1); }
    else { renderSide(0); renderSide(1); }
    res = C.match(cfg(), sides(), opts());
    if (o.setup !== false) {
      mx = three ? C.teamMatrix(cfg(), state.teams[0], state.teams[1], state.order, state.plan, ["ai", "ai"]) : C.matrix(cfg(), state.sides[0], state.sides[1]);
      renderMatrix();
      if (!three) setTimeout(function () { renderCompare(); renderSweep(); }, 0);
    }
    if (state.sel != null && (!res.events[state.sel] || res.events[state.sel].kind !== "charged")) state.sel = null;
    renderVerdict(); renderSandboxBar(); renderChart(); renderLog(); renderAct();
    movesKey = "";
    setTurn(o.keepTurn ? Math.min(state.turn, res.lastTurn) : res.lastTurn);
    setTimeout(markKeyDecisions, 30);
    writeURL();
    if (o.user && !tracked) { tracked = true; track("pvp_sim_use", { league: String(state.cp), mode: String(state.mode) }); }
  }
  /** 套用沙盒修改：保留修改前的 HP 曲線當對照，選中的那一發依「第幾發」重新找到。 */
  function applyEdits(list, habit) {
    var prev = res, sel = state.sel != null ? res.events[state.sel] : null;
    state.ghost = prev.series.map(function (x) { return { hp: x.hp.slice(), max: x.max.slice() }; });
    state.edits[state.mode] = list;
    if (habit) state.habit = habit;
    res = C.match(cfg(), sides(), opts());
    state.sel = null;
    if (sel) res.events.forEach(function (e, i) { if (state.sel == null && e.kind === "charged" && e.actor === sel.actor && e.n === sel.n) state.sel = i; });
    update({ setup: false, keepTurn: true });
    track("pvp_sim_sandbox", { mode: String(state.mode) });
  }

  function stop() { if (playTimer) { clearInterval(playTimer); playTimer = null; } var b = $("#play"); if (b) { b.textContent = "▶"; b.setAttribute("aria-label", "播放"); } }
  function play() {
    if (playTimer) { stop(); return; }
    if (state.turn >= res.lastTurn) setTurn(0);
    var b = $("#play"); b.textContent = "❚❚"; b.setAttribute("aria-label", "暫停");
    playTimer = setInterval(function () {
      if (state.turn >= res.lastTurn) { stop(); return; }
      setTurn(state.turn + 1);
    }, 140);
  }
  function selectEvent(i) {
    stop();
    state.sel = i;
    $$("#chart .cm").forEach(function (g) { g.classList.toggle("sel", Number(g.getAttribute("data-ei")) === i); });
    renderAct();
    setTurn(res.events[i].turn);
    var a = $("#act"); if (a && a.getBoundingClientRect().top > innerHeight - 120) a.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // ---------- 搜尋視窗 ----------
  var dlg = document.getElementById("picker"), pq = document.getElementById("pk-q");
  function openPicker(target) {
    pickFor = target; pq.value = ""; renderPick();
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute("open", "");
    // 手機上自動聚焦會跳出鍵盤、擋住熱門清單，只在有滑鼠的裝置自動聚焦
    if (window.matchMedia && window.matchMedia("(pointer: fine)").matches) setTimeout(function () { pq.focus(); }, 30);
  }
  function closePicker() { if (dlg.close) dlg.close(); else dlg.removeAttribute("open"); }
  function renderPick() {
    var q = pq.value, ids = C.search(q, String(state.cp), q ? 80 : 60);
    document.getElementById("pk-n").textContent = q ? (ids.length ? "找到 " + ids.length + (ids.length >= 80 ? "+" : "") + " 隻" : "找不到符合的寶可夢") : lgName() + "熱門寶可夢（依 PvPoke 排名）";
    document.getElementById("pk-l").innerHTML = ids.map(function (id) {
      var m = C.mon(id), r = C.rankOf(id, String(state.cp));
      return '<li><button type="button" data-id="' + id + '">' + pic(id) + '<span style="min-width:0"><span class="nm">' + esc(m.speciesName) + (m.sh ? ' <span class="tagx shd-t">暗影</span>' : "") +
        '</span><span class="en">#' + m.dex + " · " + esc(m.en) + "</span>" + types(id) + '</span><span class="rk">' + (r ? "#" + r.rank + "<br>" + r.score : "") + "</span></button></li>";
    }).join("");
  }
  pq.addEventListener("input", renderPick);
  document.getElementById("pk-x").addEventListener("click", closePicker);
  dlg.addEventListener("click", function (ev) {
    var b = ev.target.closest("button[data-id]");
    if (b && pickFor) {
      var id = b.getAttribute("data-id");
      if (pickFor.kind === "side") state.sides[pickFor.i] = newMon(id, state.sides[pickFor.i]);
      else state.teams[pickFor.t].mons[pickFor.k] = newMon(id, state.teams[pickFor.t].mons[pickFor.k]);
      closePicker(); clearSandbox(); update({ user: true });
      return;
    }
    if (ev.target === dlg) closePicker();     // 點背景關閉
  });
  pq.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter") { var b = $("#pk-l button"); if (b) b.click(); }
  });

  // ---------- 事件 ----------
  function targetOf(el) {
    var slot = el.closest(".slot"), team = el.closest(".team"), side = el.closest(".side");
    if (slot && team) { var t = Number(team.getAttribute("data-t")), k = Number(slot.getAttribute("data-k")); return { kind: "slot", t: t, k: k, obj: state.teams[t].mons[k] }; }
    if (team) { var tt = Number(team.getAttribute("data-t")); return { kind: "team", t: tt, obj: state.teams[tt] }; }
    if (side) { var i = Number(side.getAttribute("data-i")); return { kind: "side", i: i, obj: state.sides[i] }; }
    return null;
  }
  function setup() { clearSandbox(); update({ user: true }); }
  function bindEvents() {
    app.addEventListener("click", function (ev) {
      var t = ev.target, b;
      if ((b = t.closest("#mode button"))) { state.mode = Number(b.getAttribute("data-m")); state.sel = null; state.ghost = null; update({ user: true }); return; }
      if ((b = t.closest("#lg button"))) { state.cp = Number(b.getAttribute("data-cp")); poolCache = {}; setup(); return; }
      if ((b = t.closest("#cap button"))) { state.cap = Number(b.getAttribute("data-cap")); setup(); return; }
      if ((b = t.closest("#order button"))) { state.order = b.getAttribute("data-o"); setup(); return; }
      if ((b = t.closest("#plan button"))) { state.plan = b.getAttribute("data-p"); setup(); return; }
      if ((b = t.closest("[data-act=swap]"))) { if (state.mode === 3) state.teams.reverse(); else state.sides.reverse(); setup(); return; }
      if ((b = t.closest("[data-act=reset]"))) { state.edits[state.mode] = []; state.habit = "ai"; state.sel = null; state.ghost = null; update({ setup: false }); return; }
      if ((b = t.closest("[data-act=unsel]"))) { state.sel = null; renderAct(); $$("#chart .cm.sel").forEach(function (g) { g.classList.remove("sel"); }); return; }
      if ((b = t.closest("[data-act=share]"))) {
        var url = location.href;
        (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(function () { toast("已複製連結（含沙盒修改）"); }, function () { window.prompt("複製這個連結：", url); });
        track("pvp_sim_share", { league: String(state.cp), mode: String(state.mode) });
        return;
      }
      if ((b = t.closest("[data-hab]"))) { var hv = b.getAttribute("data-hab"); if (hv !== state.habit) applyEdits(edits(), hv); return; }
      if ((b = t.closest("[data-unedit]"))) { var l = edits().slice(); l.splice(Number(b.getAttribute("data-unedit")), 1); applyEdits(l); return; }
      if ((b = t.closest("button[data-edits]"))) { if (!b.disabled && !b.classList.contains("on")) applyEdits(decEdits(b.getAttribute("data-edits"))); return; }
      if ((b = t.closest(".ed[data-ei]"))) { selectEvent(Number(b.getAttribute("data-ei"))); $("#replay").scrollIntoView({ behavior: "smooth", block: "start" }); return; }
      if ((b = t.closest("[data-jump]"))) { stop(); setTurn(Number(b.getAttribute("data-jump"))); $("#replay").scrollIntoView({ behavior: "smooth", block: "start" }); return; }
      if ((b = t.closest("[data-mx]"))) {
        var v = b.getAttribute("data-mx").split(",").map(Number);
        if (state.mode === 3) { state.teams[0].shields = v[0]; state.teams[1].shields = v[1]; }
        else { state.sides[0].shields = v[0]; state.sides[1].shields = v[1]; }
        clearSandbox(); update({ user: true });
        $("#replay").scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      if ((b = t.closest("[data-op]"))) {
        state.sides[1] = newMon(b.getAttribute("data-op"), state.sides[1]);
        setup(); $("#verdict").scrollIntoView({ behavior: "smooth", block: "start" }); return;
      }
      if ((b = t.closest("#cmp li[data-f]"))) {
        var s = state.sides[state.cmpWho];
        s.fast = b.getAttribute("data-f"); s.c1 = b.getAttribute("data-c1"); s.c2 = b.getAttribute("data-c2") || null;
        setup(); return;
      }
      if ((b = t.closest("#cmpwho button"))) { state.cmpWho = Number(b.getAttribute("data-w")); state.cmpAll = false; renderCompare(); return; }
      if (t.closest("#cmpmore")) { state.cmpAll = true; renderCompare(); return; }
      if ((b = t.closest("#swn button"))) { state.sweepN = Number(b.getAttribute("data-n")); renderSweep(); return; }
      if ((b = t.closest("#sws button"))) { state.sweepS = Number(b.getAttribute("data-s")); renderSweep(); return; }
      if ((b = t.closest("#swo button"))) { state.sweepSort = b.getAttribute("data-o"); renderSweep(); return; }
      if ((b = t.closest("#log li[data-turn]"))) { setTurn(Number(b.getAttribute("data-turn"))); return; }
      if (t.closest("#play")) { play(); return; }
      var tg = targetOf(t); if (!tg) return;
      var sd = tg.obj;
      if ((b = t.closest("[data-tsh]"))) { sd.shields = Number(b.getAttribute("data-tsh")); setup(); return; }
      if (tg.kind === "team") return;
      if (t.closest("[data-act=pick]")) { openPicker(tg); return; }
      if (t.closest("[data-act=shadow]")) { sd.id = C.shadowOf(sd.id) || sd.id; fixMoves(sd); setup(); return; }
      if (t.closest("[data-act=recmoves]")) { ev.preventDefault(); var d = C.defaultMoves(sd.id, state.cp); sd.fast = d[0]; sd.c1 = d[1]; sd.c2 = d[2]; setup(); return; }
      if (t.closest("[data-act=up]") || t.closest("[data-act=down]")) {
        var mons = state.teams[tg.t].mons, k2 = tg.k + (t.closest("[data-act=up]") ? -1 : 1), tmp = mons[tg.k];
        mons[tg.k] = mons[k2]; mons[k2] = tmp; setup(); return;
      }
      if ((b = t.closest("[data-sh]"))) { sd.shields = Number(b.getAttribute("data-sh")); setup(); return; }
      if ((b = t.closest("[data-iv]"))) {
        var mode = b.getAttribute("data-iv");
        if (mode === "custom" && sd.iv.mode !== "custom") {
          var pv = C.ivPreview(sd.id, sd.iv, cfg(), sd.buddy);
          sd.iv = { mode: "custom", atk: pv.atk, def: pv.def, hp: pv.hp, level: 0 };
        } else if (mode !== "custom") sd.iv = { mode: mode };
        setup(); return;
      }
    });
    app.addEventListener("change", function (ev) {
      var t = ev.target, tg = targetOf(t); if (!tg || tg.kind === "team") return;
      var sd = tg.obj, k = t.getAttribute("data-k"), ivk = t.getAttribute("data-ivk");
      if (k === "fast") sd.fast = t.value;
      else if (k === "c1") { if (t.value === sd.c2) sd.c2 = sd.c1; sd.c1 = t.value; }
      else if (k === "c2") sd.c2 = t.value || null;
      else if (k === "bait") sd.bait = t.checked;
      else if (k === "buddy") {
        sd.buddy = t.checked;
        // 一位玩家只會有一隻最佳夥伴：同一隊勾了這隻，其他隻自動取消
        if (tg.kind === "slot" && t.checked) state.teams[tg.t].mons.forEach(function (m, i) { if (i !== tg.k) m.buddy = false; });
      }
      else if (k === "energy" || k === "hpPct") sd[k] = Number(t.value);
      else if (ivk) sd.iv[ivk] = Number(t.value);
      else return;
      setup();
    });
    app.addEventListener("input", function (ev) {
      var t = ev.target;
      if (t.id === "scrub") { stop(); setTurn(Number(t.value)); return; }
      var k = t.getAttribute && t.getAttribute("data-k");
      if (k === "energy" || k === "hpPct") { var v = t.nextElementSibling; if (v) v.textContent = t.value + (k === "hpPct" ? "%" : ""); }
    });
    $("#logall").addEventListener("change", function (ev) { state.logAll = ev.target.checked; renderLog(); setTurn(state.turn); });
    app.addEventListener("toggle", function (ev) {
      var d = ev.target; if (d.getAttribute && d.getAttribute("data-open")) openSlots[d.getAttribute("data-open")] = d.open;
    }, true);
    // 重播圖：點特殊招式圓圈打開修改面板；其他地方點或拖曳是移動回合
    var chart = $("#chart"), dragging = false;
    var at = function (ev) {
      var svg = chart.querySelector("svg"); if (!svg) return;
      var r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width * CH.W;
      stop(); setTurn((x - CH.L) / (CH.W - CH.L - CH.R) * res.lastTurn);
    };
    chart.addEventListener("pointerdown", function (ev) {
      var g = ev.target.closest && ev.target.closest("[data-ei]");
      if (g) { selectEvent(Number(g.getAttribute("data-ei"))); return; }
      dragging = true; at(ev);
    });
    chart.addEventListener("keydown", function (ev) {
      var g = ev.target.closest && ev.target.closest("[data-ei]");
      if (g && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); selectEvent(Number(g.getAttribute("data-ei"))); }
    });
    window.addEventListener("pointermove", function (ev) { if (dragging) at(ev); });
    window.addEventListener("pointerup", function () { dragging = false; });
    var rw = 0, lastW = 0;
    window.addEventListener("resize", function () {
      clearTimeout(rw);
      rw = setTimeout(function () { var w = $("#chart").clientWidth; if (res && Math.abs(w - lastW) > 8) { lastW = w; renderChart(); setTurn(state.turn); markKeyDecisions(); } }, 150);
    });
    document.addEventListener("keydown", function (ev) {
      if (!res || dlg.open || /input|select|textarea/i.test((ev.target && ev.target.tagName) || "")) return;
      if (!ev.target.closest || !ev.target.closest("#replay")) return;
      if (ev.key === "ArrowRight") { stop(); setTurn(state.turn + 1); ev.preventDefault(); }
      if (ev.key === "ArrowLeft") { stop(); setTurn(state.turn - 1); ev.preventDefault(); }
    });
  }

  // ---------- 啟動 ----------
  function boot(data) {
    C.init(E, data);
    var shown = data.pokemon.filter(function (p) { return !p.hide; }).length;
    $$("[data-n-mon]").forEach(function (e) { e.textContent = fmt(shown); });
    $$("[data-n-move]").forEach(function (e) { e.textContent = fmt(data.moves.length); });
    $$("[data-gm]").forEach(function (e) { e.textContent = String(data.gm).slice(0, 10); });
    $$("[data-engine]").forEach(function (e) { e.textContent = data.engine; });
    var u = readURL(), top = C.topList(state.cp, 2);
    state.sides[0] = u.a || newMon(top[0][0]);
    state.sides[1] = u.b || newMon(top[1][0]);
    state.teams[0] = u.ta || defaultTeam(0);
    state.teams[1] = u.tb || defaultTeam(3);
    renderShell(); bindEvents(); update();
  }

  if (!C || !E) { app.innerHTML = '<p class="loading">對戰引擎載入失敗，請重新整理頁面。</p>'; return; }
  fetch("../data/pvp_sim.json").then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(boot).catch(function (err) {
    app.innerHTML = '<p class="loading">對戰資料載入失敗（' + esc(err && err.message) + '），請重新整理頁面。</p>';
  });
})();
