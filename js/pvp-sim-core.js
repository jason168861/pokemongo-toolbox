/* PvP 對戰模擬器：計算核心（不碰 DOM）。
 *
 * 對戰本身完全交給 PvPoke 的引擎（js/pvpoke-engine.js → window.PvPokeEngine），
 * 這裡只負責：把畫面上的設定轉成引擎的 Pokemon／Battle、把引擎的時間軸整理成每回合的狀態、
 * 產生盾數矩陣、換招比較、對熱門寶可夢的勝負，以及中文的勝負分析。
 *
 * 資料：data/pvp_sim.json（scripts/build_pvp_sim.py 產生）。
 * 在瀏覽器掛在 window.PvPSimCore；Node 測試時用 module.exports。
 */
(function (root) {
  "use strict";

  var E = null, D = null, byId = {}, moveById = {}, moveByName = {}, rankMap = {}, searchList = [];
  var bestCache = {};

  var TYPE_ZH = {
    normal: "一般", fire: "火", water: "水", grass: "草", electric: "電", ice: "冰", fighting: "格鬥",
    poison: "毒", ground: "地面", flying: "飛行", psychic: "超能力", bug: "蟲", rock: "岩石", ghost: "幽靈",
    dragon: "龍", dark: "惡", steel: "鋼", fairy: "妖精"
  };

  function init(engine, data) {
    E = engine; D = data;
    E.load(data);                         // 引擎會依名稱排序 data.pokemon，所以下面一律用 speciesId 對照
    byId = {}; moveById = {}; moveByName = {}; rankMap = {}; searchList = []; bestCache = {};
    data.pokemon.forEach(function (p) { byId[p.speciesId] = p; });
    data.moves.forEach(function (m) { moveById[m.moveId] = m; if (!moveByName[m.name]) moveByName[m.name] = m; });
    Object.keys(data.ranks).forEach(function (cp) {
      var m = {};
      data.ranks[cp].forEach(function (r, i) { m[r[0]] = { rank: i + 1, moves: [r[1], r[2], r[3] || null], score: r[4] }; });
      rankMap[cp] = m;
    });
    data.pokemon.forEach(function (p) {
      if (p.hide) return;
      searchList.push({
        id: p.speciesId,
        key: (p.speciesName + " " + p.en + " " + p.speciesId.replace(/_/g, " ") + " #" + p.dex + (p.sh ? " 暗影 shadow" : "")).toLowerCase()
      });
    });
  }

  // ---------- 查詢 ----------

  function mon(id) { return byId[id]; }
  function move(id) { return moveById[id]; }
  function typeZh(t) { return TYPE_ZH[t] || t; }
  function rankOf(id, cp) { return (rankMap[cp] || {})[id] || null; }
  function topList(cp, n) { return (D.ranks[cp] || []).slice(0, n || 50); }

  function shadowOf(id) {
    if (/_shadow$/.test(id)) return byId[id.replace(/_shadow$/, "")] ? id.replace(/_shadow$/, "") : null;
    return byId[id + "_shadow"] ? id + "_shadow" : null;
  }

  /** 名稱搜尋：完全相同 > 開頭相同 > 包含；同一級依該聯盟的排名排序。 */
  function search(q, cp, limit) {
    q = (q || "").trim().toLowerCase();
    var rm = rankMap[cp] || {}, out = [];
    if (!q) {
      return topList(cp, limit || 60).map(function (r) { return r[0]; });
    }
    searchList.forEach(function (s) {
      var name = byId[s.id].speciesName.toLowerCase(), en = byId[s.id].en.toLowerCase();
      var lvl = -1;
      if (name === q || en === q || s.id === q) lvl = 0;
      else if (name.indexOf(q) === 0 || en.indexOf(q) === 0) lvl = 1;
      else if (s.key.indexOf(q) > -1) lvl = 2;
      if (lvl < 0) return;
      var r = rm[s.id] ? rm[s.id].rank : 9999;
      out.push([lvl, r, byId[s.id].dex, s.id]);
    });
    out.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1] || a[2] - b[2] || (a[3] < b[3] ? -1 : 1); });
    return out.slice(0, limit || 60).map(function (x) { return x[3]; });
  }

  /** 推薦招式：該聯盟 PvPoke 排名的招式 → 其他聯盟 → 依數值挑。 */
  function defaultMoves(id, cp) {
    var leagues = [String(cp), "1500", "2500", "10000"];
    for (var i = 0; i < leagues.length; i++) {
      var r = rankOf(id, leagues[i]);
      if (r) return r.moves.slice();
    }
    var p = byId[id];
    if (p.dm) return p.dm.slice();      // 沒有排名但資料有指定的（至尊洛奇亞／鳳王）
    var stab = function (m) { return p.types.indexOf(m.type) > -1 ? 1.2 : 1; };
    var fast = p.fastMoves.map(move).filter(Boolean).sort(function (a, b) {
      return (b.power * stab(b) + b.energyGain * 1.5) / b.turns - (a.power * stab(a) + a.energyGain * 1.5) / a.turns;
    })[0];
    var ch = p.chargedMoves.map(move).filter(Boolean).sort(function (a, b) {
      return (b.power * stab(b)) / b.energy - (a.power * stab(a)) / a.energy;
    });
    var c2 = ch.filter(function (m) { return ch[0] && m.type !== ch[0].type; })[0] || ch[1];
    return [fast ? fast.moveId : p.fastMoves[0], ch[0] ? ch[0].moveId : p.chargedMoves[0], c2 ? c2.moveId : null];
  }

  /** 可選的招式（含暗影的 FRUSTRATION、可學 RETURN 的寶可夢），與引擎的招式池一致。 */
  function movePools(id, cfg) {
    var b = newBattle(cfg), p = new E.Pokemon(id, 0, b);
    p.initialize(cfg.cp);
    var mk = function (m) { return { id: m.moveId, elite: !!(m.elite || m.legacy) }; };
    return { fast: p.fastMovePool.map(mk), charged: p.chargedMovePool.map(mk) };
  }

  // ---------- 引擎設定 ----------

  function newBattle(cfg) {
    var b = new E.Battle();
    b.setCP(cfg.cp);
    b.setCup("all");
    if (cfg.levelCap) b.setLevelCap(cfg.levelCap);
    return b;
  }

  /** 這隻寶可夢能用的最高等級：聯盟設定的上限（Lv40／Lv50），最佳夥伴再 +1（Lv41／Lv51）。 */
  function capOf(p, cfg, buddy) {
    return Math.min(cfg.levelCap || 50, p.baseLevelCap || 50) + (buddy ? 1 : 0);
  }

  function maxLevel(p, a, d, s, cfg, buddy) {
    for (var l = capOf(p, cfg, buddy); l >= 1; l -= 0.5) {
      if (p.calculateCP(p.getCPMByLevel(l), a, d, s) <= cfg.cp) return l;
    }
    return 1;
  }

  function setIVs(p, a, d, s, l) {
    p.ivs.atk = a; p.ivs.def = d; p.ivs.hp = s;
    p.setLevel(l, false);
    p.isCustom = true;
    p.initialize(false);
  }

  /** IV 模式：def＝PvPoke 預設、best＝PvP 排名第 1、hundo＝15/15/15、custom＝自訂（等級可指定）。
   *  buddy＝最佳夥伴：等級上限 +1（CP 上限照算，所以只有原本到不了上限的寶可夢會變強）。 */
  function applyIV(p, iv, cfg, buddy) {
    iv = iv || { mode: "def" };
    if (iv.mode === "best") {
      var cap = capOf(p, cfg, buddy);
      var key = p.speciesId + "|" + cfg.cp + "|" + cap, c = bestCache[key];
      if (!c) {
        p.levelCap = cap;
        p.maximizeStat("overall");
        c = bestCache[key] = { a: p.ivs.atk, d: p.ivs.def, s: p.ivs.hp, l: p.level };
      }
      setIVs(p, c.a, c.d, c.s, c.l);
    } else if (iv.mode === "hundo") {
      setIVs(p, 15, 15, 15, maxLevel(p, 15, 15, 15, cfg, buddy));
    } else if (iv.mode === "custom") {
      var a = clampInt(iv.atk, 0, 15), d = clampInt(iv.def, 0, 15), s = clampInt(iv.hp, 0, 15);
      var top = maxLevel(p, a, d, s, cfg, buddy);
      var l = iv.level ? Math.min(Number(iv.level), top) : top;
      setIVs(p, a, d, s, l);
    } else if (buddy) {
      // PvPoke 預設 IV 不變，只把等級拉到最佳夥伴可以到的最高等級
      setIVs(p, p.ivs.atk, p.ivs.def, p.ivs.hp, Math.max(p.level, maxLevel(p, p.ivs.atk, p.ivs.def, p.ivs.hp, cfg, true)));
    }
  }

  function clampInt(v, lo, hi) { v = parseInt(v, 10); return isNaN(v) ? hi : Math.max(lo, Math.min(hi, v)); }

  function makePokemon(b, side, index, cfg) {
    var p = new E.Pokemon(side.id, index, b);
    p.initialize(cfg.cp);
    applyIV(p, side.iv, cfg, side.buddy);
    if (side.fast) p.selectMove("fast", side.fast);
    if (side.c1) p.selectMove("charged", side.c1, 0);
    if (side.c2 && side.c2 !== side.c1) p.selectMove("charged", side.c2, 1);
    else if (p.chargedMoves.length > 1) p.selectMove("charged", "none", 1);
    return p;
  }

  /** side 可帶的開場狀態：shields、energy、hpPct（百分比）或 startHp（實際 HP，3 對 3 接續用）、
   *  buffs（攻防增減階段）、form（已經變身的型態，例如謎擬Ｑ現形）、bait（騙盾）。 */
  function prepare(cfg, A, B) {
    var b = newBattle(cfg);
    var p = makePokemon(b, A, 0, cfg), q = makePokemon(b, B, 1, cfg);
    b.setNewPokemon(p, 0, false);
    b.setNewPokemon(q, 1, false);
    [[p, A], [q, B]].forEach(function (x) {
      var poke = x[0], s = x[1];
      poke.reset();
      poke.setShields(s.shields == null ? 1 : s.shields);
      poke.setStartEnergy(s.energy || 0);
      if (s.startHp != null) poke.setStartHp(Math.max(1, Math.min(poke.stats.hp, s.startHp)));
      else poke.setStartHp(s.hpPct && s.hpPct < 100 ? Math.max(1, Math.floor(poke.stats.hp * s.hpPct / 100)) : 0);
      if (s.buffs && (s.buffs[0] || s.buffs[1])) poke.setStartBuffs([s.buffs[0], s.buffs[1]]);
      if (s.form && byId[s.form]) poke.startFormId = s.form;
      poke.baitShields = s.bait === false ? 0 : 1;
      poke.reset();
    });
    return { b: b, p: p, q: q };
  }

  function ratingOf(me, op) {
    return Math.floor(((me.hp / me.stats.hp) + ((op.stats.hp - op.hp) / op.stats.hp)) * 500);
  }

  function quick(cfg, A, B) {
    var s = prepare(cfg, A, B);
    s.b.simulate();
    return ratingOf(s.p, s.q);
  }

  // ---------- 完整模擬 ----------

  function eff(moveType, types) { return E.DamageCalculator.getEffectiveness(moveType, types); }

  function moveStats(att, def) {
    var list = [att.fastMove].concat(att.chargedMoves.filter(Boolean));
    return list.map(function (m) {
      var dmg = E.DamageCalculator.damage(att, def, m);
      var o = {
        id: m.moveId, name: m.name, type: m.type, kind: m.energyGain > 0 ? "fast" : "charged",
        damage: dmg, power: m.power, eff: eff(m.type, def.types), stab: m.stab > 1, elite: !!(m.elite || m.legacy),
        pct: Math.round(dmg / def.stats.hp * 1000) / 10
      };
      if (o.kind === "fast") {
        o.energy = m.energyGain; o.turns = m.turns;
        o.dpt = Math.round(dmg / m.turns * 100) / 100; o.ept = Math.round(m.energyGain / m.turns * 100) / 100;
      } else {
        o.energy = m.energy;
        o.fastNeeded = Math.ceil(m.energy / att.fastMove.energyGain);
        o.turnsNeeded = o.fastNeeded * att.fastMove.turns;
        if (m.buffs && m.buffApplyChance) {
          o.buffs = m.buffTarget === "both" ? { self: m.buffsSelf, opp: m.buffsOpponent }
            : (m.buffTarget === "self" ? { self: m.buffs } : { opp: m.buffs });
          o.buffChance = m.buffApplyChance;
        }
      }
      return o;
    });
  }

  function summary(p) {
    return {
      id: p.speciesId, cp: p.cp, level: p.level, ivs: { atk: p.ivs.atk, def: p.ivs.def, hp: p.ivs.hp },
      atk: Math.round(p.stats.atk * 10) / 10, def: Math.round(p.stats.def * 10) / 10, hp: p.stats.hp,
      startHp: p.startHp, startEnergy: p.startEnergy, shields: p.startingShields,
      statProduct: Math.round(p.stats.atk * p.stats.def * p.stats.hp),
      shadow: p.shadowType === "shadow"
    };
  }

  function normalizeTimeline(tl) {
    var out = [];
    tl.forEach(function (e, i) {
      var t = e.type || "";
      if (t.indexOf("tap") === 0 || t === "switchAvailable") return;
      var o = { turn: e.turn, time: e.time, actor: e.actor, seq: i };
      if (t.indexOf("fast ") === 0 || t.indexOf("charged ") === 0) {
        var bits = t.split(" ");
        var m = moveByName[e.name];
        o.kind = bits[0]; o.type = bits[1]; o.name = e.name; o.moveId = m ? m.moveId : null;
        o.dmg = Number(e.values[0]) || 0; o.energy = Number(e.values[1]) || 0; o.pct = Number(e.values[2]) || 0;
        o.buff = bits[2] || null;
        if (o.buff && typeof e.values[3] === "string") o.buffText = e.values[3];
      } else if (t === "shield" || t === "shieldSpecial") {
        o.kind = "shield"; o.blocked = Number(e.values[0]) || 0; o.special = t === "shieldSpecial";
      } else if (t === "faint") {
        o.kind = "faint";
      } else if (t === "formChange") {
        o.kind = "form";
        o.text = String(e.values[0] || "");
      } else {
        return;
      }
      out.push(o);
    });
    // 同一回合：先結算特殊招式與護盾，再結算一般招式（顯示順序；HP 計算與順序無關）
    var rank = { charged: 0, shield: 1, fast: 2, form: 3, faint: 4 };
    out.sort(function (a, b) { return a.turn - b.turn || a.time - b.time || rank[a.kind] - rank[b.kind] || a.seq - b.seq; });
    // 標記被護盾擋下的特殊招式
    out.forEach(function (e) {
      if (e.kind !== "charged") return;
      e.shielded = out.some(function (s) { return s.kind === "shield" && s.turn === e.turn && s.actor === 1 - e.actor; });
    });
    return out;
  }

  /** 依時間軸重建每回合結束時的 HP／能量／護盾。series[t] = 第 t 回合結束時的狀態（t=0 是開戰前）。 */
  function buildSeries(events, start, lastTurn) {
    var st = { hp: start.hp.slice(), en: start.en.slice(), sh: start.sh.slice() };
    var series = [{ hp: st.hp.slice(), en: st.en.slice(), sh: st.sh.slice() }], k = 0;
    for (var t = 1; t <= lastTurn; t++) {
      while (k < events.length && events[k].turn <= t) {
        var e = events[k++];
        if (e.kind === "fast" || e.kind === "charged") {
          st.hp[1 - e.actor] = Math.max(0, st.hp[1 - e.actor] - e.dmg);
          st.en[e.actor] = Math.max(0, Math.min(100, st.en[e.actor] + e.energy));
        } else if (e.kind === "shield") {
          st.sh[e.actor] = Math.max(0, st.sh[e.actor] - 1);
        }
      }
      series.push({ hp: st.hp.slice(), en: st.en.slice(), sh: st.sh.slice() });
    }
    return series;
  }

  function run(cfg, A, B) {
    var s = prepare(cfg, A, B), p = s.p, q = s.q, b = s.b;
    var moves = [moveStats(p, q), moveStats(q, p)];
    var start = { hp: [p.startHp, q.startHp], en: [p.startEnergy, q.startEnergy], sh: [p.startingShields, q.startingShields] };
    var info = [summary(p), summary(q)];
    b.simulate();
    var events = normalizeTimeline(b.getTimeline());
    var lastTurn = events.reduce(function (m, e) { return Math.max(m, e.turn); }, 1);
    var series = buildSeries(events, start, lastTurn);
    var winner = (p.hp <= 0 && q.hp <= 0) ? -1 : (q.hp <= 0 ? 0 : (p.hp <= 0 ? 1 : (ratingOf(p, q) > 500 ? 0 : (ratingOf(p, q) < 500 ? 1 : -1))));
    return {
      cfg: cfg, sides: [A, B], info: info, moves: moves, events: events, series: series, lastTurn: lastTurn,
      winner: winner, ratings: [ratingOf(p, q), ratingOf(q, p)],
      hp: [Math.max(0, p.hp), Math.max(0, q.hp)], maxHp: [p.stats.hp, q.stats.hp],
      shieldsLeft: [p.shields, q.shields], energyLeft: [p.energy, q.energy],
      durationMs: b.getDuration ? b.getDuration() : null,
      end: [p, q].map(function (x) {
        return { hp: Math.max(0, x.hp), energy: x.energy, shields: x.shields, buffs: x.statBuffs.slice(), form: x.activeFormId };
      }),
      replayOk: series[series.length - 1].hp[0] === Math.max(0, p.hp) && series[series.length - 1].hp[1] === Math.max(0, q.hp)
    };
  }

  function withShields(side, n) { var o = {}; for (var k in side) o[k] = side[k]; o.shields = n; return o; }

  /** 3×3 盾數矩陣：m[我方盾][對手盾] = 我方的對戰評分。 */
  function matrix(cfg, A, B) {
    var m = [];
    for (var i = 0; i <= 2; i++) {
      m.push([]);
      for (var j = 0; j <= 2; j++) m[i].push(quick(cfg, withShields(A, i), withShields(B, j)));
    }
    return m;
  }

  /** 換招比較：side 這一方所有招式組合對上同一個對手。cap 是組合上限（招式太多的寶可夢只取前幾招）。 */
  function movesetCompare(cfg, A, B, who, cap) {
    var me = who === 1 ? B : A, op = who === 1 ? A : B;
    var pools = movePools(me.id, cfg);
    var fast = pools.fast.map(function (m) { return m.id; });
    var charged = pools.charged.map(function (m) { return m.id; });
    cap = cap || 240;
    var trimmed = false;
    if (fast.length * charged.length * (charged.length - 1) / 2 > cap) {
      // 招式很多（夢幻、圖圖犬…）：一般招式取「每回合傷害＋能量」最高的 6 招、特殊招式取「每點能量傷害」最高的 7 招，
      // 再加上目前選的，避免手機上算太久
      var p = byId[me.id], st = function (m) { return p.types.indexOf(m.type) > -1 ? 1.2 : 1; };
      var cs = function (id) { var m = moveById[id]; return (m.power * st(m)) / m.energy; };
      var fs = function (id) { var m = moveById[id]; return (m.power * st(m) + m.energyGain) / m.turns; };
      var keepC = charged.slice().sort(function (a, b) { return cs(b) - cs(a); }).slice(0, 7);
      [me.c1, me.c2].forEach(function (c) { if (c && keepC.indexOf(c) < 0) keepC.push(c); });
      charged = keepC;
      trimmed = true;
      if (fast.length > 6) {
        var keepF = fast.slice().sort(function (a, b) { return fs(b) - fs(a); }).slice(0, 6);
        if (keepF.indexOf(me.fast) < 0) keepF.push(me.fast);
        fast = keepF;
      }
    }
    var out = [];
    fast.forEach(function (f) {
      for (var i = 0; i < charged.length; i++) {
        for (var j = i; j < charged.length; j++) {
          if (j === i && charged.length > 1) continue;
          var side = {}; for (var k in me) side[k] = me[k];
          side.fast = f; side.c1 = charged[i]; side.c2 = j === i ? null : charged[j];
          var s = who === 1 ? prepare(cfg, op, side) : prepare(cfg, side, op);
          s.b.simulate();
          out.push({ fast: f, c1: side.c1, c2: side.c2, rating: who === 1 ? ratingOf(s.q, s.p) : ratingOf(s.p, s.q),
            current: f === me.fast && ((side.c1 === me.c1 && side.c2 === me.c2) || (side.c1 === me.c2 && side.c2 === me.c1)) });
        }
      }
    });
    out.sort(function (a, b) { return b.rating - a.rating; });
    out.trimmed = trimmed;
    return out;
  }

  /** 對上熱門寶可夢：A 對該聯盟排名前 n 名（用各自的推薦招式與 PvPoke 預設 IV）。 */
  function sweep(cfg, A, n, shields) {
    return topList(cfg.cp, n).map(function (r) {
      var B = { id: r[0], fast: r[1], c1: r[2], c2: r[3] || null, iv: { mode: "def" }, shields: shields };
      return { id: r[0], moves: [r[1], r[2], r[3] || null], rating: quick(cfg, withShields(A, shields), B) };
    });
  }

  // ---------- 勝負分析（中文） ----------

  function effWord(x) {
    if (x > 2) return "效果絕佳（×2.56）";
    if (x > 1.5) return "效果絕佳（×1.6）";
    if (x < 0.4) return "效果非常差（×0.39）";
    if (x < 0.7) return "效果不好（×0.625）";
    return "";
  }

  function insights(res, names, mx) {
    var out = [], w = res.winner, n = names;
    var hpPct = function (i) { return Math.round(res.hp[i] / res.maxHp[i] * 100); };
    var sec = res.lastTurn / 2;
    if (w === -1) {
      out.push("雙方在同一回合倒下，這場是<b>平手</b>。");
    } else {
      var margin = hpPct(w);
      var how = margin >= 60 ? "大勝" : (margin >= 25 ? "獲勝" : "險勝");
      out.push(n[w] + " <b>" + how + "</b>，還剩 <b>" + res.hp[w] + "／" + res.maxHp[w] + " HP（" + margin + "%）</b>，" +
        "共 " + res.lastTurn + " 回合（約 " + (Math.round(sec * 10) / 10) + " 秒）。");
    }
    // 一般招式的節奏
    var f0 = res.moves[0][0], f1 = res.moves[1][0];
    out.push("一般招式：" + n[0] + " 的「" + f0.name + "」每 " + f0.turns + " 回合打 " + f0.damage + "、回 " + f0.energy + " 能量；" +
      n[1] + " 的「" + f1.name + "」每 " + f1.turns + " 回合打 " + f1.damage + "、回 " + f1.energy + " 能量。" +
      (Math.abs(f0.dpt - f1.dpt) >= 0.3 ? (f0.dpt > f1.dpt ? n[0] : n[1]) + " 的一般招式壓力比較大。" : ""));
    // 第一發特殊招式
    var first = [null, null];
    res.events.forEach(function (e) { if (e.kind === "charged" && first[e.actor] === null) first[e.actor] = e; });
    if (first[0] && first[1]) {
      var d = first[1].turn - first[0].turn;
      out.push("第一發特殊招式：" + n[0] + " 在第 " + first[0].turn + " 回合放出「" + first[0].name + "」，" + n[1] + " 在第 " + first[1].turn +
        " 回合放出「" + first[1].name + "」" + (d === 0 ? "，兩邊同時。" : "，" + (d > 0 ? n[0] : n[1]) + " 早了 " + Math.abs(d) + " 回合。"));
    } else if (first[0] || first[1]) {
      var a = first[0] ? 0 : 1;
      out.push(n[1 - a] + " 一發特殊招式都沒放出來就倒下了；" + n[a] + " 在第 " + first[a].turn + " 回合放出第一發「" + first[a].name + "」。");
    }
    // 屬性相剋：依攻擊方整理，「效果絕佳」排前面
    var notes = [];
    [0, 1].forEach(function (i) {
      var groups = {};
      res.moves[i].forEach(function (m) {
        var wd = effWord(m.eff);
        if (wd) (groups[wd] = groups[wd] || []).push("「" + m.name + "」");
      });
      var keys = Object.keys(groups).sort(function (a, b) { return (b.indexOf("絕佳") > -1) - (a.indexOf("絕佳") > -1); });
      if (keys.length) notes.push(n[i] + " 的" + keys.map(function (k) { return groups[k].join("、") + k; }).join("，"));
    });
    if (notes.length) out.push("屬性相剋：" + notes.join("；") + "。");
    // 護盾
    var used = [res.info[0].shields - res.shieldsLeft[0], res.info[1].shields - res.shieldsLeft[1]];
    if (used[0] || used[1]) {
      out.push("護盾：" + n[0] + " 用了 " + used[0] + " 面、" + n[1] + " 用了 " + used[1] + " 面" +
        (res.winner > -1 && res.shieldsLeft[res.winner] > 0 ? "；" + n[res.winner] + " 打完還留著 " + res.shieldsLeft[res.winner] + " 面。" : "。"));
    }
    // 盾數影響
    if (mx) {
      var wins = 0, cells = 0;
      mx.forEach(function (row) { row.forEach(function (r) { cells++; if (r > 500) wins++; }); });
      if (wins === cells) out.push("9 種盾數組合 " + n[0] + " <b>全部都贏</b>，這是很穩的對位。");
      else if (wins === 0) out.push("9 種盾數組合 " + n[0] + " <b>全部都輸</b>，換別隻上場比較好。");
      else out.push("9 種盾數組合中 " + n[0] + " 贏 <b>" + wins + "</b> 種，結果會隨盾數改變，可以點下方的盾數矩陣看每一種情況。");
    }
    return out;
  }

  // ---------- 沙盒對戰（1 對 1、3 對 3 共用） ----------
  //
  // 對戰仍由 PvPoke 引擎逐回合計算（Battle.start + step，與 simulate() 相同），只在兩個地方插手：
  //   getTurnAction：使用者指定「延後放招／改放另一招／換人擋招」時，改用使用者的動作。
  //   useMove：使用者指定某一次「開盾／不開盾」，或對手的開盾習慣、護盾分配時，改變開盾決定。
  // 沒有任何指定時，結果與 PvPoke 的 simulate() 完全一樣（測試用排名資料驗證）。
  //
  // edits（都用「第幾發」定位，前面改了、後面的回合往後移也不會錯位）：
  //   {k:"shield", side, n, v}   side 這邊第 n 次被特殊招式打到：v=true 開盾、false 不開
  //   {k:"hold",   side, n, d}   side 的第 n 發特殊招式延後 d 回合
  //   {k:"use",    side, n, v}   side 的第 n 發特殊招式改放第 v 招（能量不夠就累積到夠再放）
  //   {k:"swap",   side, n, to}  對手第 n 發特殊招式出手的那一回合，side 換成第 to 隻上場擋招（切角擋招）
  //   {k:"swapT",  side, t, to}  第 t 回合（正在出招就等到最早可以換的回合）side 換成第 to 隻
  //   {k:"charge", side, n, v}   side 的第 n 發特殊招式只蓄力 v（0.25～0.75），傷害按比例縮小（與 PvPoke 相同算法）
  // opts.react = "counter"：我方主動換人後，對手若有明顯更好的對位（評分高 60 以上），下一回合起換上來克制
  // habits[side]：開盾習慣 ai（PvPoke 判斷）| always（每發都開）| never（不開）| lethal（只擋會被打倒的）| first（只開第一發）
  // plan：spread（3 對 3 每隻最多用「剩餘護盾 ÷ 剩下隻數」面）| free（需要就用）

  function edit(edits, k, side, n) {
    for (var i = 0; i < edits.length; i++) { var e = edits[i]; if (e.k === k && e.side === side && e.n === n) return e; }
    return null;
  }

  function matchOnce(cfg, sides, opts, swapAt) {
    var edits = opts.edits || [], habits = opts.habits || ["ai", "ai"], plan = opts.plan || "free";
    var nMon = [sides[0].mons.length, sides[1].mons.length];
    var maxHp = [0, 1].map(function (t) {
      return sides[t].mons.map(function (m) { var b = newBattle(cfg); return makePokemon(b, m, t, cfg).stats.hp; });
    });
    // 每隻寶可夢跨段落保留的狀態
    var ms = [0, 1].map(function (t) {
      return sides[t].mons.map(function (m, k) {
        var hp = maxHp[t][k];
        if (nMon[t] === 1 && m.hpPct && m.hpPct < 100) hp = Math.max(1, Math.floor(hp * m.hpPct / 100));
        return { hp: hp, en: nMon[t] === 1 ? (m.energy || 0) : 0, alive: true, buffs: null, form: null };
      });
    });
    var start = { hp: [ms[0].map(function (x) { return x.hp; }), ms[1].map(function (x) { return x.hp; })],
      en: [ms[0].map(function (x) { return x.en; }), ms[1].map(function (x) { return x.en; })] };
    var cur = [0, 0], shields = [sides[0].shields == null ? 1 : sides[0].shields, sides[1].shields == null ? 1 : sides[1].shields];
    var startShields = shields.slice();
    var cnt = { thrown: [0, 0], hit: [0, 0], want: {} }, timer = [0, 0];
    var stint = [{ used: 0, allow: 2 }, { used: 0, allow: 2 }];
    var events = [], switches = [], swapOk = [{}, {}], swapFail = {}, offset = 0, ko = [[], []], reactN = 0;
    var pend = swapAt.map(function (x) { var o = {}; for (var k in x) o[k] = x[k]; o.done = false; return o; });
    function clone(o) { var c = {}; for (var k in o) c[k] = o[k]; return c; }
    function aliveCount(t) { return ms[t].filter(function (x) { return x.alive; }).length; }
    function newStint(t) {
      var n = aliveCount(t);
      stint[t] = { used: 0, allow: plan === "spread" && n > 1 ? Math.ceil(shields[t] / n) : 99 };
    }
    newStint(0); newStint(1);

    for (var guard = 0; guard < 12; guard++) {
      var b = newBattle(cfg);
      var objs = [0, 1].map(function (t) {
        return sides[t].mons.map(function (m, k) {
          var p = makePokemon(b, m, t, cfg), st = ms[t][k];
          p.setShields(shields[t]);
          p.setStartEnergy(st.en || 0);
          p.setStartHp(Math.max(1, st.hp));
          if (k === cur[t] && st.buffs && (st.buffs[0] || st.buffs[1])) p.setStartBuffs([st.buffs[0], st.buffs[1]]);
          if (k === cur[t] && st.form && byId[st.form]) p.startFormId = st.form;
          p.baitShields = m.bait === false ? 0 : 1;
          p.reset();
          return p;
        });
      });
      var players = [0, 1].map(function (t) {
        var P = new E.Player(t, false, b);
        P.ai = { evaluateMatchup: function () {} };   // 引擎在換人冷卻結束時會呼叫 AI；我們沒有 AI，給一個空的
        P.setTeam(objs[t]);
        P.switchTimer = timer[t];
        return P;
      });
      b.setPlayers(players);
      b.setNewPokemon(objs[0][cur[0]], 0, false);
      b.setNewPokemon(objs[1][cur[1]], 1, false);
      var segCur = [cur[0], cur[1]], segSw = [];
      var origTA = b.getTurnAction, origUM = b.useMove;
      // 對手跟著換：用目前雙方的 HP、能量評估，有明顯更好的對位才換
      var liveState = function (t, k) {
        var p = objs[t][k], on = b.getPokemon()[t] === p;
        return { hp: on ? p.hp : p.startHp, en: on ? p.energy : p.startEnergy };
      };
      var scheduleReact = function (g, mine, myShields) {
        var o = 1, curO = segCur[o];
        if (players[o].getSwitchTimer() > 0) return;
        var me = clone(sides[0].mons[mine]), ls0 = liveState(0, mine);
        me.shields = myShields; me.startHp = Math.max(1, ls0.hp); me.energy = ls0.en;
        var rate = function (k) {
          var op = clone(sides[o].mons[k]), ls = liveState(o, k);
          op.startHp = Math.max(1, ls.hp); op.energy = ls.en; op.shields = b.getPokemon()[o].shields;
          var s2 = prepare(cfg, me, op); s2.b.simulate(); return ratingOf(s2.q, s2.p);
        };
        var best = -1, br = rate(curO) + 60;
        ms[o].forEach(function (x, k) {
          if (k === curO || !x.alive || liveState(o, k).hp <= 0) return;
          var r = rate(k); if (r > br) { br = r; best = k; }
        });
        if (best >= 0) pend.push({ side: o, turn: g + 1, to: best, from: true, auto: true, id: "react" + (reactN++) });
      };

      b.getTurnAction = function (poke, opp) {
        var side = poke.index, g = offset + b.getTurns();
        if (!poke.hasActed && poke.hp > 0 && opp.hp > 0) {
          var ok = poke.cooldown === 0 && players[side].getSwitchTimer() === 0;
          if (ok) swapOk[side][g] = true;
          var sw = null;
          for (var i = 0; i < pend.length; i++) {
            var x = pend[i];
            if (x.done || x.side !== side) continue;
            if (x.from ? x.turn <= g : x.turn === g) { sw = x; break; }
          }
          if (sw) {
            var to = sw.to;
            if (to === segCur[side] || !ms[side][to] || !ms[side][to].alive) { sw.done = true; swapFail[sw.id] = "target"; }
            else if (!ok) {
              // 指定回合換人：正在出招就等到最早可以換的回合；擋招（對手出招那一回合）錯過就算了
              if (!sw.from) { sw.done = true; swapFail[sw.id] = poke.cooldown > 0 ? "busy" : "timer"; }
              else if (g - sw.turn > 120) { sw.done = true; swapFail[sw.id] = "timer"; }
            } else {
              sw.done = true;
              poke.hasActed = true;
              if (side === 0 && opts.react === "counter" && !sw.auto) scheduleReact(g, to, poke.shields);
              objs[side][to].setShields(poke.shields);      // 護盾整隊共用
              segSw.push({ turn: g, side: side, from: segCur[side], to: to, auto: !!sw.auto });
              switches.push({ turn: g, side: side, from: segCur[side], to: to, kind: sw.auto ? "react" : "manual" });
              segCur[side] = to;
              stint[side] = { used: 0, allow: plan === "spread" && aliveCount(side) > 1 ? Math.ceil(poke.shields / aliveCount(side)) : 99 };
              return new E.TimelineAction("switch", side, b.getTurns(), to, { priority: poke.priority + 20 });
            }
          }
        }
        var a = origTA.call(b, poke, opp);
        if (a && a.type === "charged") {
          var n = cnt.thrown[side] + 1, key = side + ":" + n;
          if (cnt.want[key] == null) cnt.want[key] = g;
          var hold = edit(edits, "hold", side, n), use = edit(edits, "use", side, n);
          var wait = hold && g < cnt.want[key] + hold.d;
          if (!wait && use && poke.chargedMoves[use.v]) {
            if (poke.energy >= poke.chargedMoves[use.v].energy) a.value = use.v;
            else wait = true;
          }
          if (wait) a = new E.TimelineAction("fast", side, b.getTurns(), 0, { priority: poke.priority });
          else {
            var ce = edit(edits, "charge", side, n);
            if (ce) a.settings.charge = ce.v;
          }
        }
        return a;
      };

      b.useMove = function (att, def, move) {
        if (!(move.energy > 0)) return origUM.apply(b, arguments);
        cnt.thrown[att.index]++;
        var side = def.index, m = ++cnt.hit[side];
        if (def.shields <= 0 || (move.hasTag && move.hasTag("instant"))) return origUM.apply(b, arguments);
        var d = null, e = edit(edits, "shield", side, m), h = habits[side];
        if (e) d = !!e.v;
        else if (h === "always") d = true;
        else if (h === "never") d = false;
        else if (h === "lethal") d = E.DamageCalculator.damage(att, def, move) >= def.hp;
        else if (h === "first") d = startShields[side] - def.shields === 0;
        else if (stint[side].used >= stint[side].allow) d = false;
        var before = def.shields, r, args = arguments;
        if (d === false) {
          def.shields = 0;
          try { r = origUM.apply(b, args); } finally { def.shields = before; }
        } else if (d === true) {
          var w = E.ActionLogic.wouldShield;
          E.ActionLogic.wouldShield = function () { return { value: true, shieldWeight: 1, noShieldWeight: 0 }; };
          try { r = origUM.apply(b, args); } finally { E.ActionLogic.wouldShield = w; }
        } else {
          r = origUM.apply(b, args);
        }
        if (def.shields < before) stint[side].used++;
        return r;
      };

      b.start();
      var steps = 0;
      while (steps++ < 2000) {
        b.step();
        var pk = b.getPokemon();
        if (pk[0].hp <= 0 || pk[1].hp <= 0 || b.getDuration() > 240000) break;
      }
      var lastLocal = b.getTurns() - 1;
      // 時間軸：換成整場的回合數，並記下每個事件是哪一隻
      var curAt = function (side, lt) {
        var k = cur[side];
        segSw.forEach(function (s) { if (s.side === side && s.turn - offset <= lt) k = s.to; });
        return k;
      };
      normalizeTimeline(b.getTimeline()).forEach(function (e) {
        if (e.kind === "faint") e.turn = Math.min(e.turn, lastLocal);   // 引擎記在下一回合，改成倒下的那一回合
        e.mon = curAt(e.actor, e.turn);
        e.opMon = curAt(1 - e.actor, e.turn);
        e.turn += offset;
        events.push(e);
      });
      segSw.forEach(function (s) { events.push({ kind: "switch", turn: s.turn, actor: s.side, from: s.from, to: s.to, mon: s.to, manual: true, react: s.auto, time: -1 }); });
      // 更新每隻的狀態
      var onField = b.getPokemon();
      [0, 1].forEach(function (t) {
        objs[t].forEach(function (p, k) {
          var st = ms[t][k];
          if (p === onField[t]) {
            st.hp = Math.max(0, p.hp); st.en = p.energy; st.buffs = p.statBuffs.slice(); st.form = p.activeFormId;
          } else if (st.alive) {
            st.hp = p.startHp; st.en = p.startEnergy; st.buffs = null;
            st.form = p.formChange && p.formChange.resetOnSwitch ? null : (p.activeFormId !== p.speciesId ? p.activeFormId : st.form);
          }
        });
        shields[t] = onField[t].shields;
        timer[t] = players[t].getSwitchTimer();
        cur[t] = segCur[t];
      });
      offset += lastLocal;
      var fa = onField[0].hp <= 0, fb = onField[1].hp <= 0;
      if (fb) ko[0].push({ by: cur[0], victim: cur[1], turn: offset });
      if (fa) ko[1].push({ by: cur[1], victim: cur[0], turn: offset });
      if (fa) ms[0][cur[0]].alive = false;
      if (fb) ms[1][cur[1]].alive = false;
      if (!fa && !fb) break;
      var nxt = [cur[0], cur[1]];
      [0, 1].forEach(function (t) {
        if (!(t === 0 ? fa : fb)) return;
        var cands = [];
        ms[t].forEach(function (x, k) { if (x.alive) cands.push(k); });
        if (!cands.length) { nxt[t] = -1; return; }
        nxt[t] = cands[0];
        var oppAlive = !(t === 0 ? fb : fa);
        if (opts.order === "best" && cands.length > 1 && oppAlive) {
          var o = 1 - t, oppSide = {}, src = sides[o].mons[cur[o]], so = ms[o][cur[o]], br = -1;
          for (var x in src) oppSide[x] = src[x];
          oppSide.startHp = so.hp; oppSide.energy = so.en; oppSide.buffs = so.buffs; oppSide.form = so.form; oppSide.shields = shields[o];
          cands.forEach(function (k) {
            var me = {}; for (var y in sides[t].mons[k]) me[y] = sides[t].mons[k][y];
            me.shields = shields[t]; me.startHp = ms[t][k].hp; me.energy = ms[t][k].en;
            var s2 = t === 0 ? prepare(cfg, me, oppSide) : prepare(cfg, oppSide, me);
            s2.b.simulate();
            var r = t === 0 ? ratingOf(s2.p, s2.q) : ratingOf(s2.q, s2.p);
            if (r > br) { br = r; nxt[t] = k; }
          });
        }
      });
      if (nxt[0] < 0 || nxt[1] < 0) break;
      [0, 1].forEach(function (t) {
        if (nxt[t] !== cur[t]) {
          switches.push({ turn: offset + 1, side: t, from: cur[t], to: nxt[t], kind: "faint" });
          events.push({ kind: "switch", turn: offset + 1, actor: t, from: cur[t], to: nxt[t], mon: nxt[t], manual: false, time: -1 });
          cur[t] = nxt[t];
          newStint(t);
        }
      });
    }
    // 事件排序：同一回合先換人，再特殊招式、護盾、一般招式
    var rank = { "switch": -1, charged: 0, shield: 1, fast: 2, form: 3, faint: 4 };
    events.sort(function (a, b) { return a.turn - b.turn || rank[a.kind] - rank[b.kind] || a.time - b.time || (a.seq || 0) - (b.seq || 0); });
    // 第幾發（攻擊方）／第幾次被打（防守方）
    var c1 = [0, 0], c2 = [0, 0];
    events.forEach(function (e) { if (e.kind === "charged") { e.n = ++c1[e.actor]; e.m = ++c2[1 - e.actor]; } });
    // 逐回合狀態
    var st = { hp: [start.hp[0].slice(), start.hp[1].slice()], en: [start.en[0].slice(), start.en[1].slice()], sh: startShields.slice(), cur: [0, 0] };
    var snap = function () {
      return { hp: [st.hp[0][st.cur[0]], st.hp[1][st.cur[1]]], en: [st.en[0][st.cur[0]], st.en[1][st.cur[1]]], sh: st.sh.slice(), cur: st.cur.slice(),
        max: [maxHp[0][st.cur[0]], maxHp[1][st.cur[1]]], all: [st.hp[0].slice(), st.hp[1].slice()] };
    };
    var series = [snap()], i = 0;
    for (var t = 1; t <= offset; t++) {
      while (i < events.length && events[i].turn <= t) {
        var e = events[i++];
        if (e.kind === "switch") st.cur[e.actor] = e.to;
        else if (e.kind === "fast" || e.kind === "charged") {
          var dd = 1 - e.actor;
          st.hp[dd][st.cur[dd]] = Math.max(0, st.hp[dd][st.cur[dd]] - e.dmg);
          st.en[e.actor][st.cur[e.actor]] = Math.max(0, Math.min(100, st.en[e.actor][st.cur[e.actor]] + e.energy));
        } else if (e.kind === "shield") st.sh[e.actor] = Math.max(0, st.sh[e.actor] - 1);
      }
      series.push(snap());
    }
    var left = [aliveCount(0), aliveCount(1)];
    var hpLeft = [0, 1].map(function (t) { return ms[t].map(function (x) { return x.alive ? x.hp : 0; }); });
    var replayOk = [0, 1].every(function (t) { return st.hp[t].every(function (h, k) { return h === hpLeft[t][k]; }); });
    var winner = left[0] && !left[1] ? 0 : (left[1] && !left[0] ? 1 : -1);
    return {
      events: events, series: series, lastTurn: offset, switches: switches, swapOk: swapOk, swapFail: swapFail, ko: ko,
      left: left, hpLeft: hpLeft, maxHp: maxHp, winner: winner, alive: ms.map(function (a) { return a.map(function (x) { return x.alive; }); }),
      shieldsLeft: shields.slice(), shieldsUsed: [startShields[0] - shields[0], startShields[1] - shields[1]], startShields: startShields,
      energyLeft: [ms[0].map(function (x) { return x.en; }), ms[1].map(function (x) { return x.en; })], replayOk: replayOk
    };
  }

  /** 沙盒對戰：先處理「換人擋招」（要知道對手第 n 發在哪一回合才能換），再跑完整場。 */
  function match(cfg, sides, opts) {
    opts = opts || {};
    var edits = opts.edits || [], swapAt = [], status = {};
    edits.forEach(function (e, i) { if (e.k === "swapT") swapAt.push({ side: e.side, turn: e.t, to: e.to, id: i, from: true }); });
    var swaps = edits.map(function (e, i) { return { e: e, i: i }; }).filter(function (x) { return x.e.k === "swap"; })
      .sort(function (a, b) { return a.e.n - b.e.n; });
    swaps.forEach(function (x) {
      var r = matchOnce(cfg, sides, opts, swapAt), opp = 1 - x.e.side, T = null;
      r.events.forEach(function (ev) { if (T === null && ev.kind === "charged" && ev.actor === opp && ev.n === x.e.n) T = ev.turn; });
      if (T === null) status[x.i] = "missing";
      else swapAt.push({ side: x.e.side, turn: T, to: x.e.to, id: x.i });
    });
    var res = matchOnce(cfg, sides, opts, swapAt);
    Object.keys(res.swapFail).forEach(function (id) { if (!/^react/.test(id)) status[id] = res.swapFail[id]; });
    res.events.forEach(function (e) {
      if (e.kind !== "charged") return;
      var ce = edit(edits, "charge", e.actor, e.n);
      if (ce) e.charge = ce.v;
    });
    res.editStatus = edits.map(function (e, i) { return status[i] || "ok"; });
    // 1 對 1 的評分（與 PvPoke 相同算法）
    if (sides[0].mons.length === 1 && sides[1].mons.length === 1) {
      var last = res.series[res.series.length - 1], m0 = res.maxHp[0][0], m1 = res.maxHp[1][0];
      var hp0 = last.hp[0], hp1 = last.hp[1];
      res.ratings = [Math.floor(((hp0 / m0) + ((m1 - hp1) / m1)) * 500), Math.floor(((hp1 / m1) + ((m0 - hp0) / m0)) * 500)];
      if (hp0 > 0 && hp1 > 0) res.winner = res.ratings[0] > 500 ? 0 : (res.ratings[0] < 500 ? 1 : -1);
      res.hp = [hp0, hp1];
    }
    return res;
  }

  /** 兩隻之間的招式數據與能力值（給招式表、能量條刻度用）。 */
  var pairCache = {};
  function pair(cfg, A, B) {
    var key = JSON.stringify([cfg, A.id, A.fast, A.c1, A.c2, A.iv, A.buddy, B.id, B.fast, B.c1, B.c2, B.iv, B.buddy]);
    if (pairCache[key]) return pairCache[key];
    var s = prepare(cfg, A, B);
    var out = { moves: [moveStats(s.p, s.q), moveStats(s.q, s.p)], info: [summary(s.p), summary(s.q)] };
    pairCache[key] = out;
    return out;
  }

  /** 3×3 整隊護盾矩陣（不含使用者指定的動作）。 */
  function teamMatrix(cfg, TA, TB, order, plan, habits) {
    var m = [];
    for (var i = 0; i <= 2; i++) {
      m.push([]);
      for (var j = 0; j <= 2; j++) {
        var r = match(cfg, [{ mons: TA.mons, shields: i }, { mons: TB.mons, shields: j }], { order: order, plan: plan, habits: habits });
        var sc = function (t) { return r.hpLeft[t].reduce(function (s, h, k) { return s + h / r.maxHp[t][k]; }, 0); };
        m[i].push({ winner: r.winner, left: r.left, margin: Math.round((sc(0) - sc(1)) * 100) / 100 });
      }
    }
    return m;
  }

  function teamInsights(tr, names, teamNames) {
    var out = [], w = tr.winner;
    var alive = function (t) {
      return names[t].map(function (n, k) { return tr.alive[t][k] ? n + "（" + Math.round(tr.hpLeft[t][k] / tr.maxHp[t][k] * 100) + "%）" : null; }).filter(Boolean);
    };
    if (w === -1) out.push("雙方最後一隻同時倒下，這場是<b>平手</b>。");
    else out.push(teamNames[w] + " <b>獲勝</b>，還剩 <b>" + tr.left[w] + " 隻</b>：" + alive(w).join("、") + "。共 " + tr.lastTurn + " 回合（約 " + Math.round(tr.lastTurn / 2) + " 秒）。");
    [0, 1].forEach(function (t) {
      var cnt = {};
      tr.ko[t].forEach(function (k) { cnt[k.by] = (cnt[k.by] || 0) + 1; });
      var top = Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a]; })[0];
      if (top != null && cnt[top] >= 2) out.push(teamNames[t] + " 的 <b>" + names[t][top] + "</b> 一隻打倒了 " + cnt[top] + " 隻。");
    });
    var manual = tr.switches.filter(function (s) { return s.kind === "manual"; });
    if (manual.length) out.push("切角擋招：" + manual.map(function (s) { return "第 " + s.turn + " 回合" + teamNames[s.side] + "換上 " + names[s.side][s.to]; }).join("；") + "。");
    out.push("護盾：" + teamNames[0] + " 用了 " + tr.shieldsUsed[0] + " 面、" + teamNames[1] + " 用了 " + tr.shieldsUsed[1] + " 面。");
    return out;
  }

  var api = {
    match: match, pair: pair, teamMatrix: teamMatrix, teamInsights: teamInsights,
    init: init, mon: mon, move: move, typeZh: typeZh, rankOf: rankOf, topList: topList, search: search,
    shadowOf: shadowOf, defaultMoves: defaultMoves, movePools: movePools, run: run, quick: quick,
    matrix: matrix, movesetCompare: movesetCompare, sweep: sweep, insights: insights, effWord: effWord,
    ivPreview: function (id, iv, cfg, buddy) {
      var b = newBattle(cfg), p = new E.Pokemon(id, 0, b);
      p.initialize(cfg.cp); applyIV(p, iv, cfg, buddy);
      return { atk: p.ivs.atk, def: p.ivs.def, hp: p.ivs.hp, level: p.level, cp: p.cp,
        maxLevel: maxLevel(p, p.ivs.atk, p.ivs.def, p.ivs.hp, cfg, buddy), cap: capOf(p, cfg, buddy) };
    },
    data: function () { return D; }
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PvPSimCore = api;
})(this);
