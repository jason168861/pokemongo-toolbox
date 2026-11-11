/* PvP 對戰模擬器（/pvp-sim/）：畫面與互動。
 * 計算全部在 js/pvp-sim-core.js（PvPoke 引擎），這裡只負責設定、繪製與網址同步。
 *
 * 兩種模式：
 *   1 對 1：兩隻寶可夢打到一方倒下。
 *   3 對 3：兩隊各 3 隻，依序接力（規則見 pvp-sim-core.js 的 runTeam）。
 *
 * 網址參數（可分享）：
 *   共同：l=1500|2500|10000、cap=40（不用 XL）
 *   1 對 1：a=<一方>&b=<另一方>
 *     一方 = speciesId.一般招式.特殊招式1.特殊招式2(或 -).IV.護盾.起始能量.起始HP%.騙盾(1/0).最佳夥伴(1/0)
 *   3 對 3：m=3&ta=<隊伍>&tb=<隊伍>&ts=我方盾-對手盾&o=b|f（倒下後派誰）&p=s|f（護盾分配）
 *     隊伍 = 三隻用 ~ 分隔，每隻 = speciesId.一般招式.特殊招式1.特殊招式2.IV.最佳夥伴
 *   IV = d（PvPoke 預設）| b（PvP 排名第 1）| h（100%）| c攻-防-HP-等級（等級 0＝自動）
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
  var SHIELD_SVG = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1 2 3.2v4.3c0 3.4 2.6 6.3 6 7.5 3.4-1.2 6-4.1 6-7.5V3.2z" fill="currentColor"/></svg>';

  var state = {
    mode: 1, cp: 1500, cap: 50, sides: [null, null], teams: [null, null], order: "best", plan: "spread", seg: 0,
    turn: 0, sweepN: 30, sweepS: 1, sweepSort: "rank", cmpWho: 0, cmpAll: false, logAll: false
  };
  var res1 = null, mx1 = null, teamRes = null, teamMx = null;
  var view = { res: null, ids: ["", ""] };          // 目前在重播、紀錄、招式表顯示的那一場 1 對 1
  var playTimer = null, pickFor = null, poolCache = {}, sweepJob = 0, tracked = false, openSlots = {};
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
  /** 招式不在招式池（換成暗影／一般型態、網址亂改）就改回推薦招式。 */
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
          '<p class="rulenote">3 對 3 的規則：雙方不主動換寶可夢，打到一方倒下才換下一隻上場；場上存活的那隻保留 HP、能量與攻防增減，護盾整隊共用。' +
          '「平均分配」讓每隻最多用掉「剩餘護盾 ÷ 剩下隻數」面，比較接近實戰；「需要就用」則照 PvPoke 的 1 對 1 判斷，常常第一隻就把盾開完。</p>' +
        "</div>" +
      "</section>" +
      '<section class="card verdict" id="verdict" aria-live="polite"></section>' +
      '<section class="card" id="segc" hidden><h2 class="sec-h"><span class="ic">🔗</span>對戰經過<small>點一段就能在下方重播</small></h2><ol class="segs" id="segs"></ol></section>' +
      '<section class="card" id="mxc"><h2 class="sec-h"><span class="ic">🛡</span>9 種盾數組合<small>點格子切換到那個情境</small></h2><div class="mxwrap" id="mx"></div>' +
        '<p class="mxnote" id="mxnote"></p></section>' +
      '<section class="card" id="replay"><h2 class="sec-h"><span class="ic">▶</span><span id="rp-h">逐回合重播</span><small id="rp-sub"></small></h2>' +
        '<div class="chart" id="chart"></div>' +
        '<div class="legend"><span><i style="background:var(--a)"></i>我方 HP</span><span><i style="background:var(--b)"></i>對手 HP</span>' +
        '<span style="color:var(--a)"><i class="d"></i>我方能量</span><span style="color:var(--b)"><i class="d"></i>對手能量</span><span>● 特殊招式（空心＝被護盾擋下）</span></div>' +
        '<div class="player"><button type="button" id="play" aria-label="播放">▶</button><input type="range" id="scrub" min="0" max="1" value="0" aria-label="回合"><span class="tn" id="tn"></span></div>' +
        '<div class="states" id="states"></div><p class="now" id="now"></p></section>' +
      '<section class="card" id="logc"><h2 class="sec-h"><span class="ic">📜</span>對戰紀錄</h2>' +
        '<div class="logtools"><label class="tgl"><input type="checkbox" id="logall"> 顯示每一次一般招式</label></div><ol class="log" id="log"></ol></section>' +
      '<section class="card" id="movec"><h2 class="sec-h"><span class="ic">⚔️</span>招式與能力值<small>傷害是打在對方身上的實際數值</small></h2><div class="mtab" id="mtab"></div></section>' +
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

  // ---------- 1 對 1 結果 ----------
  function renderVerdict1() {
    var res = res1, w = res.winner, el = $("#verdict"), n = [nm(state.sides[0].id), nm(state.sides[1].id)];
    el.className = "card verdict" + (w === 0 ? " w0" : w === 1 ? " w1" : "");
    var mon = function (i) {
      var lost = w > -1 && w !== i;
      return '<div class="vd-mon' + (i ? " r" : "") + (lost ? " lost" : "") + '">' + pic(state.sides[i].id) + '<span style="min-width:0"><span class="vd-nm">' + esc(n[i]) +
        (w === i ? '<span class="crown">勝</span>' : "") + '</span><span class="vd-sub">' + SIDE_NAME[i] + " · CP " + fmt(res.info[i].cp) + " · " + res.info[i].shields + " 盾</span></span></div>";
    };
    var big = w === -1 ? "平手" : (w === 0 ? "勝 ─ 敗" : "敗 ─ 勝");
    var hpb = function (i) {
      var pct = res.hp[i] / res.maxHp[i] * 100;
      return '<div class="hpb' + (i ? " r" : "") + (res.hp[i] <= 0 ? " dead" : pct < 30 ? " lowhp" : "") + '">剩餘 HP ' + res.hp[i] + "／" + res.maxHp[i] +
        '<div class="t"><i style="width:' + pct.toFixed(1) + '%"></i></div></div>';
    };
    var ins = C.insights(res, n.map(esc), mx1);
    el.innerHTML = '<div class="vd-top">' + mon(0) + '<div class="vd-res"><span class="big">' + big + '</span><span class="score">評分 ' + res.ratings[0] + " : " + res.ratings[1] + "</span></div>" + mon(1) + "</div>" +
      '<div class="hpbars">' + hpb(0) + hpb(1) + "</div>" +
      '<ul class="ins">' + ins.map(function (s) { return "<li>" + s + "</li>"; }).join("") + "</ul>" +
      '<div class="vd-act"><button type="button" data-act="share">🔗 複製這場對戰的連結</button><button type="button" data-act="swap">⇄ 交換雙方</button></div>';
  }

  function renderMatrix1() {
    var s0 = state.sides[0].shields, s1 = state.sides[1].shields;
    $("#mx").innerHTML = mxTable(function (i, j) {
      var r = mx1[i][j], c = rc(r);
      return { c: c, cur: i === s0 && j === s1, big: r, small: r > 500 ? "勝" : r < 500 ? "敗" : "平", label: "評分 " + r };
    });
    $("#mxnote").textContent = "數字是我方的對戰評分（0～1000，超過 500 就是贏）。直的是我方護盾數，橫的是對手護盾數。";
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

  // ---------- 3 對 3 結果 ----------
  function teamNames(t) { return state.teams[t].mons.map(function (m) { return nm(m.id); }); }
  function renderVerdict3() {
    var tr = teamRes, w = tr.winner, el = $("#verdict");
    el.className = "card verdict" + (w === 0 ? " w0" : w === 1 ? " w1" : "");
    var row = function (t) {
      return '<div class="tv-row' + (t ? " r" : "") + '">' + state.teams[t].mons.map(function (m, k) {
        var hp = tr.hpLeft[t][k], mh = tr.maxHp[t][k], pct = hp / mh * 100;
        return '<div class="tv-mon' + (hp <= 0 ? " ko" : "") + '">' + pic(m.id) + '<span class="tv-nm">' + esc(nm(m.id)) + "</span>" +
          '<span class="tv-hp"><i style="width:' + pct.toFixed(0) + "%;background:" + (pct < 30 ? "#f59e0b" : "#10b981") + '"></i></span></div>';
      }).join("") + "</div>";
    };
    var big = w === -1 ? "平手" : (w === 0 ? "勝 ─ 敗" : "敗 ─ 勝");
    var ins = C.teamInsights(tr, [teamNames(0).map(esc), teamNames(1).map(esc)], TEAM_NAME);
    el.innerHTML = '<div class="tv"><div><span class="vd-sub">' + TEAM_NAME[0] + " · " + state.teams[0].shields + " 盾</span>" + row(0) + "</div>" +
      '<div class="vd-res"><span class="big">' + big + '</span><span class="score">剩下 ' + tr.left[0] + " : " + tr.left[1] + " 隻</span></div>" +
      '<div class="tvr"><span class="vd-sub">' + TEAM_NAME[1] + " · " + state.teams[1].shields + " 盾</span>" + row(1) + "</div></div>" +
      '<ul class="ins">' + ins.map(function (s) { return "<li>" + s + "</li>"; }).join("") + "</ul>" +
      '<div class="vd-act"><button type="button" data-act="share">🔗 複製這場對戰的連結</button><button type="button" data-act="swap">⇄ 交換兩隊</button></div>';
  }
  function renderSegments() {
    $("#segs").innerHTML = teamRes.segments.map(function (sg, i) {
      var r = sg.res, a = state.teams[0].mons[sg.a].id, b = state.teams[1].mons[sg.b].id;
      var out = r.end[0].hp <= 0 && r.end[1].hp <= 0 ? "同時倒下" : (r.end[1].hp <= 0 ? esc(nm(b)) + " 倒下" : esc(nm(a)) + " 倒下");
      return '<li><button type="button" data-seg="' + i + '" aria-current="' + (i === state.seg) + '">' +
        '<span class="sg-n">第 ' + (i + 1) + " 段<small>回合 " + (sg.offset + 1) + "～" + (sg.offset + r.lastTurn) + "</small></span>" +
        '<span class="sg-m">' + pic(a) + '<span class="sg-t"><b>' + esc(nm(a)) + '</b><span class="sg-hp">HP ' + r.series[0].hp[0] + "→" + r.end[0].hp + "</span></span></span>" +
        '<span class="sg-vs">VS</span>' +
        '<span class="sg-m r">' + pic(b) + '<span class="sg-t"><b>' + esc(nm(b)) + '</b><span class="sg-hp">HP ' + r.series[0].hp[1] + "→" + r.end[1].hp + "</span></span></span>" +
        '<span class="sg-out">' + out + '<small>可用護盾 ' + sg.allowed[0] + "／" + sg.allowed[1] + "</small></span></button></li>";
    }).join("");
  }
  function renderMatrix3() {
    var s0 = state.teams[0].shields, s1 = state.teams[1].shields;
    $("#mx").innerHTML = mxTable(function (i, j) {
      var x = teamMx[i][j], r = 500 + Math.max(-1, Math.min(1, x.margin / 2)) * 400;
      return { c: rc(Math.round(r)), cur: i === s0 && j === s1, big: x.winner === 0 ? "勝" : x.winner === 1 ? "敗" : "平",
        small: "剩 " + x.left[0] + "：" + x.left[1], label: (x.winner === 0 ? "我方勝" : x.winner === 1 ? "對手勝" : "平手") + "，剩 " + x.left[0] + " 比 " + x.left[1] + " 隻" };
    });
    $("#mxnote").textContent = "整隊護盾數的 9 種組合。「剩 2：0」代表打完我方還剩 2 隻、對手 0 隻；顏色越深代表贏（或輸）得越多。";
  }

  // ---------- 重播（1 對 1 或 3 對 3 的其中一段） ----------
  var CH = { W: 1000, H: 286, L: 40, R: 14, laneA: 20, top: 44, bot: 236, laneB: 264 };
  function sizeChart() {
    var w = Math.round(($("#chart") && $("#chart").clientWidth) || 1000);
    CH.W = Math.max(300, w);
    var small = CH.W < 640;
    CH.L = small ? 34 : 40; CH.R = small ? 10 : 14;
    CH.H = small ? 250 : 286; CH.laneA = 18; CH.top = 40; CH.bot = CH.H - 50; CH.laneB = CH.H - 22;
  }
  function cx(t) { return CH.L + (t / Math.max(1, view.res.lastTurn)) * (CH.W - CH.L - CH.R); }
  function cy(p) { return CH.bot - p * (CH.bot - CH.top); }
  function renderChart() {
    sizeChart();
    var res = view.res, T = res.lastTurn, s = res.series, h = [], i, t, small = CH.W < 640;
    h.push('<svg viewBox="0 0 ' + CH.W + " " + CH.H + '" role="img" aria-label="雙方 HP 與能量隨回合變化">');
    [0, 0.5, 1].forEach(function (p) {
      h.push('<line x1="' + CH.L + '" x2="' + (CH.W - CH.R) + '" y1="' + cy(p) + '" y2="' + cy(p) + '" stroke="#ece8f6" stroke-width="1"/>');
      h.push('<text x="' + (CH.L - 6) + '" y="' + (cy(p) + 4) + '" font-size="12" text-anchor="end" fill="#9a95ad">' + (p * 100) + "%</text>");
    });
    var step = T > 120 ? 20 : T > 60 ? 10 : (small && T > 30 ? 10 : 5);
    for (t = step; t < T; t += step) {
      h.push('<line x1="' + cx(t) + '" x2="' + cx(t) + '" y1="' + CH.top + '" y2="' + CH.bot + '" stroke="#f3f1f8"/>');
      h.push('<text x="' + cx(t) + '" y="' + (CH.bot + 14) + '" font-size="11" text-anchor="middle" fill="#9a95ad">' + t + "</text>");
    }
    h.push('<rect x="' + CH.L + '" y="' + (CH.laneA - 12) + '" width="' + (CH.W - CH.L - CH.R) + '" height="24" rx="12" fill="#fff4f8"/>');
    h.push('<rect x="' + CH.L + '" y="' + (CH.laneB - 12) + '" width="' + (CH.W - CH.L - CH.R) + '" height="24" rx="12" fill="#f5f2ff"/>');
    h.push('<text x="' + (CH.L - 6) + '" y="' + (CH.laneA + 4) + '" font-size="11" text-anchor="end" fill="#e0276c" font-weight="800">我方</text>');
    h.push('<text x="' + (CH.L - 6) + '" y="' + (CH.laneB + 4) + '" font-size="11" text-anchor="end" fill="#6d4aff" font-weight="800">對手</text>');
    var line = function (fn, color, dash, width) {
      var pts = [cx(0) + "," + cy(fn(s[0]))];
      for (t = 1; t < s.length; t++) { pts.push(cx(t) + "," + cy(fn(s[t - 1]))); pts.push(cx(t) + "," + cy(fn(s[t]))); }
      return '<polyline fill="none" stroke="' + color + '" stroke-width="' + width + '" stroke-linejoin="round"' + (dash ? ' stroke-dasharray="5 5" opacity=".55"' : "") + ' points="' + pts.join(" ") + '"/>';
    };
    [0, 1].forEach(function (i) { h.push(line(function (x) { return x.en[i] / 100; }, i ? "#6d4aff" : "#e0276c", true, 2)); });
    [0, 1].forEach(function (i) { h.push(line(function (x) { return x.hp[i] / res.maxHp[i]; }, i ? "#6d4aff" : "#e0276c", false, 3.2)); });
    res.events.forEach(function (e) {
      var y = e.actor ? CH.laneB : CH.laneA, x = cx(e.turn), c = TYPE_COLOR[e.type] || "#888";
      if (e.kind === "fast") {
        h.push('<circle cx="' + x + '" cy="' + y + '" r="' + (small ? 2.2 : 2.8) + '" fill="' + c + '" opacity=".75"/>');
      } else if (e.kind === "charged") {
        h.push('<line x1="' + x + '" x2="' + x + '" y1="' + (e.actor ? CH.top : y + 12) + '" y2="' + (e.actor ? y - 12 : CH.bot) + '" stroke="' + c + '" stroke-width="1" stroke-dasharray="2 4" opacity=".6"/>');
        h.push('<g><title>第 ' + e.turn + " 回合：" + esc(e.name) + (e.shielded ? "（被護盾擋下）" : "，" + e.dmg + " 傷害") + "</title>" +
          '<circle cx="' + x + '" cy="' + y + '" r="' + (small ? 9 : 11) + '" fill="' + (e.shielded ? "#fff" : c) + '" stroke="' + c + '" stroke-width="2.5"/>' +
          '<text x="' + x + '" y="' + (y + 4) + '" font-size="' + (small ? 10 : 11) + '" font-weight="900" text-anchor="middle" fill="' + (e.shielded ? c : "#fff") + '">' + esc(tch(e.type)) + "</text></g>");
      } else if (e.kind === "faint") {
        h.push('<text x="' + x + '" y="' + (y + 5) + '" font-size="15" font-weight="900" text-anchor="middle" fill="#d6334a">✕</text>');
      }
    });
    h.push('<line id="cur" x1="0" x2="0" y1="' + (CH.laneA - 14) + '" y2="' + (CH.laneB + 14) + '" stroke="#14111f" stroke-width="1.5" opacity=".7"/>');
    h.push('<circle id="cur0" r="5" fill="#e0276c" stroke="#fff" stroke-width="2"/><circle id="cur1" r="5" fill="#6d4aff" stroke="#fff" stroke-width="2"/>');
    h.push("</svg>");
    $("#chart").innerHTML = h.join("");
    $("#scrub").max = T;
    var sub = "共 " + T + " 回合 · 約 " + (Math.round(T / 2 * 10) / 10) + " 秒";
    if (state.mode === 3) {
      var sg = teamRes.segments[state.seg];
      sub = "第 " + (state.seg + 1) + " 段（整場第 " + (sg.offset + 1) + "～" + (sg.offset + T) + " 回合）";
    }
    $("#rp-h").textContent = state.mode === 3 ? "分段重播" : "逐回合重播";
    $("#rp-sub").textContent = sub;
  }

  function buffText(e) {
    var m = C.move(e.moveId); if (!m || !m.buffs) return "";
    var desc = function (arr) {
      var o = [];
      if (arr[0]) o.push("攻擊 " + (arr[0] > 0 ? "+" : "−") + Math.abs(arr[0]));
      if (arr[1]) o.push("防禦 " + (arr[1] > 0 ? "+" : "−") + Math.abs(arr[1]));
      return o.join("、");
    };
    var me = nm(view.ids[e.actor]), op = nm(view.ids[1 - e.actor]);
    if (m.buffTarget === "both") return me + " " + desc(m.buffsSelf) + "；" + op + " " + desc(m.buffsOpponent);
    return (m.buffTarget === "self" ? me : op) + " " + desc(m.buffs);
  }

  function evText(e, rich) {
    var who = esc(nm(view.ids[e.actor])), op = esc(nm(view.ids[1 - e.actor]));
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

  function setTurn(t) {
    var res = view.res;
    t = Math.max(0, Math.min(res.lastTurn, Math.round(t)));
    state.turn = t;
    var st = res.series[t];
    $("#scrub").value = t;
    $("#tn").textContent = "第 " + t + " / " + res.lastTurn + " 回合";
    var x = cx(t), cur = $("#cur");
    if (cur) {
      cur.setAttribute("x1", x); cur.setAttribute("x2", x);
      for (var i = 0; i < 2; i++) { var d = $("#cur" + i); d.setAttribute("cx", x); d.setAttribute("cy", cy(st.hp[i] / res.maxHp[i])); }
    }
    $("#states").innerHTML = [0, 1].map(function (i) {
      var hp = st.hp[i], mh = res.maxHp[i], en = st.en[i];
      var ticks = res.moves[i].filter(function (m) { return m.kind === "charged"; }).map(function (m) {
        return '<span class="tick' + (en >= m.energy ? " ready" : "") + '" style="left:calc(' + m.energy + '% - 1px)" title="' + esc(m.name) + " 需要 " + m.energy + ' 能量"></span>';
      }).join("");
      var shields = ""; for (var k = 0; k < res.info[i].shields; k++) shields += '<span style="color:' + (k < st.sh[i] ? (i ? "#6d4aff" : "#e0276c") : "#d6d2e0") + '">' + SHIELD_SVG + "</span>";
      return '<div class="st" data-i="' + i + '"><div class="h"><span>' + esc(nm(view.ids[i])) + '</span><span class="sh-ic" aria-label="剩 ' + st.sh[i] + ' 面護盾">' + shields + "</span></div>" +
        '<div class="meter hp' + (hp / mh < 0.3 ? " low" : "") + '">HP ' + hp + "／" + mh + '<div class="t"><i style="width:' + (hp / mh * 100).toFixed(1) + '%"></i></div></div>' +
        '<div class="meter en">能量 ' + en + "／100" + '<div class="t"><i style="width:' + en + '%"></i>' + ticks + "</div></div></div>";
    }).join("");
    var evs = res.events.filter(function (e) { return e.turn === t && e.kind !== "shield"; });
    $("#now").innerHTML = t === 0 ? "開場：HP " + st.hp[0] + "／" + st.hp[1] + "、能量 " + st.en[0] + "／" + st.en[1] + "、可用護盾 " + st.sh[0] + "／" + st.sh[1] + "。拖曳上方的軸或按 ▶ 播放。"
      : ("<b>第 " + t + " 回合</b>：" + (evs.length ? evs.map(function (e) { return evText(e, false); }).join("；") : "雙方都還在出一般招式的動作中。"));
    $$("#log li").forEach(function (li) { li.classList.toggle("cur", Number(li.getAttribute("data-turn")) === t); });
  }

  function renderLog() {
    var evs = view.res.events.filter(function (e) { return e.kind !== "shield" && (state.logAll || e.kind !== "fast"); });
    $("#log").innerHTML = evs.map(function (e) {
      return '<li class="' + e.kind + '" data-i="' + e.actor + '" data-turn="' + e.turn + '"><span class="tt">第 ' + e.turn + ' 回合</span><span>' + evText(e, true) + "</span></li>";
    }).join("") || "<li>沒有特殊招式。</li>";
  }

  function renderMoves() {
    var res = view.res;
    $("#mtab").innerHTML = [0, 1].map(function (i) {
      var inf = res.info[i];
      var rows = res.moves[i].map(function (m) {
        var e = C.effWord(m.eff), ef = e ? '<span class="efx ' + (m.eff > 1 ? "up" : "dn") + '">' + (m.eff > 1 ? "效果絕佳" : "效果不好") + " ×" + (m.eff > 2 ? "2.56" : m.eff > 1 ? "1.6" : m.eff < 0.4 ? "0.39" : "0.625") + "</span>" : "";
        var en = m.kind === "fast" ? ("+" + m.energy + '<span class="k">' + m.turns + " 回合 · 每回合 " + m.dpt + " 傷害 / " + m.ept + " 能量</span>")
          : (m.energy + '<span class="k">要 ' + m.fastNeeded + " 次一般招式（" + m.turnsNeeded + " 回合）</span>");
        return "<tr><td>" + mvChip(m.id, m.elite) + (m.stab ? '<span class="k">同屬性加成 ×1.2</span>' : "") + "</td>" +
          '<td class="n">' + m.damage + '<span class="k">' + m.pct + "% HP</span>" + ef + "</td><td>" + en + "</td></tr>";
      }).join("");
      return '<div class="mt" data-i="' + i + '"><h3><i></i>' + esc(nm(view.ids[i])) + "</h3>" +
        '<p class="mvinfo" style="margin:0 0 6px">CP ' + fmt(inf.cp) + " · " + lvTxt(inf.level) + " · IV " + inf.ivs.atk + "/" + inf.ivs.def + "/" + inf.ivs.hp +
        " · 攻擊 " + inf.atk + "・防禦 " + inf.def + "・HP " + inf.hp + (inf.shadow ? " · 暗影（攻擊 ×1.2、防禦 ×0.83）" : "") + "</p>" +
        "<table><thead><tr><th>招式</th><th>傷害</th><th>能量</th></tr></thead><tbody>" + rows + "</tbody></table></div>";
    }).join("");
  }

  function showView(res, ids, keepTurn) {
    view.res = res; view.ids = ids;
    renderChart(); renderLog(); renderMoves();
    setTurn(keepTurn ? Math.min(state.turn, res.lastTurn) : res.lastTurn);
  }

  // ---------- 換招比較、對上熱門（只有 1 對 1） ----------
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
  function update(opts) {
    opts = opts || {};
    stop();
    pressed("#mode", "data-m", state.mode); pressed("#lg", "data-cp", state.cp); pressed("#cap", "data-cap", state.cap);
    var three = state.mode === 3;
    $("#one").hidden = three; $("#three").hidden = !three;
    $("#segc").hidden = !three; $("#cmpc").hidden = three; $("#swc").hidden = three;
    if (three) {
      pressed("#order", "data-o", state.order); pressed("#plan", "data-p", state.plan);
      renderTeam(0); renderTeam(1);
      teamRes = C.runTeam(cfg(), state.teams[0], state.teams[1], state.order, state.plan);
      teamMx = C.teamMatrix(cfg(), state.teams[0], state.teams[1], state.order, state.plan);
      if (!opts.keepSeg || state.seg >= teamRes.segments.length) state.seg = 0;
      renderVerdict3(); renderSegments(); renderMatrix3();
      showSeg(opts.keepTurn);
    } else {
      renderSide(0); renderSide(1);
      res1 = C.run(cfg(), state.sides[0], state.sides[1]);
      mx1 = C.matrix(cfg(), state.sides[0], state.sides[1]);
      renderVerdict1(); renderMatrix1();
      showView(res1, [state.sides[0].id, state.sides[1].id], opts.keepTurn);
      setTimeout(function () { renderCompare(); renderSweep(); }, 0);
    }
    writeURL();
    if (opts.user && !tracked) { tracked = true; track("pvp_sim_use", { league: String(state.cp), mode: String(state.mode) }); }
  }
  function showSeg(keepTurn) {
    var sg = teamRes.segments[state.seg];
    $$("#segs button").forEach(function (b) { b.setAttribute("aria-current", String(Number(b.getAttribute("data-seg")) === state.seg)); });
    showView(sg.res, [state.teams[0].mons[sg.a].id, state.teams[1].mons[sg.b].id], keepTurn);
  }

  function stop() { if (playTimer) { clearInterval(playTimer); playTimer = null; } var b = $("#play"); if (b) { b.textContent = "▶"; b.setAttribute("aria-label", "播放"); } }
  function play() {
    if (playTimer) { stop(); return; }
    if (state.turn >= view.res.lastTurn) setTurn(0);
    var b = $("#play"); b.textContent = "❚❚"; b.setAttribute("aria-label", "暫停");
    playTimer = setInterval(function () {
      if (state.turn >= view.res.lastTurn) {
        // 3 對 3：一段播完自動接下一段
        if (state.mode === 3 && state.seg < teamRes.segments.length - 1) { state.seg++; showSeg(false); setTurn(0); return; }
        stop(); return;
      }
      setTurn(state.turn + 1);
    }, 140);
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
      closePicker(); update({ user: true });
      return;
    }
    if (ev.target === dlg) closePicker();     // 點背景關閉
  });
  pq.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter") { var b = $("#pk-l button"); if (b) b.click(); }
  });

  // ---------- 事件 ----------
  /** 點到的是 1 對 1 的哪一方，或 3 對 3 的哪一隊、哪一隻。 */
  function targetOf(el) {
    var slot = el.closest(".slot"), team = el.closest(".team"), side = el.closest(".side");
    if (slot && team) { var t = Number(team.getAttribute("data-t")), k = Number(slot.getAttribute("data-k")); return { kind: "slot", t: t, k: k, obj: state.teams[t].mons[k] }; }
    if (team) { var tt = Number(team.getAttribute("data-t")); return { kind: "team", t: tt, obj: state.teams[tt] }; }
    if (side) { var i = Number(side.getAttribute("data-i")); return { kind: "side", i: i, obj: state.sides[i] }; }
    return null;
  }
  function bindEvents() {
    app.addEventListener("click", function (ev) {
      var t = ev.target, b;
      if ((b = t.closest("#mode button"))) { state.mode = Number(b.getAttribute("data-m")); update({ user: true }); return; }
      if ((b = t.closest("#lg button"))) { state.cp = Number(b.getAttribute("data-cp")); poolCache = {}; update({ user: true }); return; }
      if ((b = t.closest("#cap button"))) { state.cap = Number(b.getAttribute("data-cap")); update({ user: true }); return; }
      if ((b = t.closest("#order button"))) { state.order = b.getAttribute("data-o"); update({ user: true }); return; }
      if ((b = t.closest("#plan button"))) { state.plan = b.getAttribute("data-p"); update({ user: true }); return; }
      if ((b = t.closest("[data-act=swap]"))) { if (state.mode === 3) state.teams.reverse(); else state.sides.reverse(); update({ user: true }); return; }
      if ((b = t.closest("[data-act=share]"))) {
        var url = location.href;
        (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(function () { toast("已複製連結"); }, function () { window.prompt("複製這個連結：", url); });
        track("pvp_sim_share", { league: String(state.cp), mode: String(state.mode) });
        return;
      }
      if ((b = t.closest("[data-mx]"))) {
        var v = b.getAttribute("data-mx").split(",").map(Number);
        if (state.mode === 3) { state.teams[0].shields = v[0]; state.teams[1].shields = v[1]; }
        else { state.sides[0].shields = v[0]; state.sides[1].shields = v[1]; }
        update({ user: true });
        $(state.mode === 3 ? "#segc" : "#replay").scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      if ((b = t.closest("[data-seg]"))) { stop(); state.seg = Number(b.getAttribute("data-seg")); showSeg(false); $("#replay").scrollIntoView({ behavior: "smooth", block: "start" }); return; }
      if ((b = t.closest("[data-op]"))) {
        state.sides[1] = newMon(b.getAttribute("data-op"), state.sides[1]);
        update({ user: true }); $("#verdict").scrollIntoView({ behavior: "smooth", block: "start" }); return;
      }
      if ((b = t.closest("#cmp li[data-f]"))) {
        var s = state.sides[state.cmpWho];
        s.fast = b.getAttribute("data-f"); s.c1 = b.getAttribute("data-c1"); s.c2 = b.getAttribute("data-c2") || null;
        update({ user: true }); return;
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
      if ((b = t.closest("[data-tsh]"))) { sd.shields = Number(b.getAttribute("data-tsh")); update({ user: true }); return; }
      if (tg.kind === "team") return;
      if (t.closest("[data-act=pick]")) { openPicker(tg); return; }
      if (t.closest("[data-act=shadow]")) { sd.id = C.shadowOf(sd.id) || sd.id; fixMoves(sd); update({ user: true }); return; }
      if (t.closest("[data-act=recmoves]")) { ev.preventDefault(); var d = C.defaultMoves(sd.id, state.cp); sd.fast = d[0]; sd.c1 = d[1]; sd.c2 = d[2]; update({ user: true }); return; }
      if (t.closest("[data-act=up]") || t.closest("[data-act=down]")) {
        var mons = state.teams[tg.t].mons, k2 = tg.k + (t.closest("[data-act=up]") ? -1 : 1), tmp = mons[tg.k];
        mons[tg.k] = mons[k2]; mons[k2] = tmp; update({ user: true }); return;
      }
      if ((b = t.closest("[data-sh]"))) { sd.shields = Number(b.getAttribute("data-sh")); update({ user: true }); return; }
      if ((b = t.closest("[data-iv]"))) {
        var mode = b.getAttribute("data-iv");
        if (mode === "custom" && sd.iv.mode !== "custom") {
          var pv = C.ivPreview(sd.id, sd.iv, cfg(), sd.buddy);
          sd.iv = { mode: "custom", atk: pv.atk, def: pv.def, hp: pv.hp, level: 0 };
        } else if (mode !== "custom") sd.iv = { mode: mode };
        update({ user: true }); return;
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
      update({ user: true, keepTurn: k === "bait", keepSeg: false });
    });
    app.addEventListener("input", function (ev) {
      var t = ev.target;
      if (t.id === "scrub") { stop(); setTurn(Number(t.value)); return; }
      var k = t.getAttribute && t.getAttribute("data-k");
      if (k === "energy" || k === "hpPct") { var v = t.nextElementSibling; if (v) v.textContent = t.value + (k === "hpPct" ? "%" : ""); }
    });
    $("#logall").addEventListener("change", function (ev) { state.logAll = ev.target.checked; renderLog(); setTurn(state.turn); });
    // 記住 3 對 3 哪幾隻的編輯區是打開的（重繪後維持）
    app.addEventListener("toggle", function (ev) {
      var d = ev.target; if (d.getAttribute && d.getAttribute("data-open")) openSlots[d.getAttribute("data-open")] = d.open;
    }, true);
    // 拖曳重播圖
    var chart = $("#chart"), dragging = false;
    var at = function (ev) {
      var svg = chart.querySelector("svg"); if (!svg) return;
      var r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width * CH.W;
      stop(); setTurn((x - CH.L) / (CH.W - CH.L - CH.R) * view.res.lastTurn);
    };
    chart.addEventListener("pointerdown", function (ev) { dragging = true; at(ev); });
    window.addEventListener("pointermove", function (ev) { if (dragging) at(ev); });
    window.addEventListener("pointerup", function () { dragging = false; });
    var rw = 0, lastW = 0;
    window.addEventListener("resize", function () {
      clearTimeout(rw);
      rw = setTimeout(function () { var w = $("#chart").clientWidth; if (view.res && Math.abs(w - lastW) > 8) { lastW = w; renderChart(); setTurn(state.turn); } }, 150);
    });
    document.addEventListener("keydown", function (ev) {
      if (!view.res || dlg.open || /input|select|textarea/i.test((ev.target && ev.target.tagName) || "")) return;
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
