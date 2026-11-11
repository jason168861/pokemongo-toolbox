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
    var p = byId[id], stab = function (m) { return p.types.indexOf(m.type) > -1 ? 1.2 : 1; };
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

  // ---------- 3 對 3 ----------

  /** team = { mons: [slot, slot, slot], shields: 0～2 }；slot 和 1 對 1 的 side 一樣（id、招式、iv、buddy、bait）。
   *  規則（簡化，畫面上有寫）：
   *   - 不主動換寶可夢，一直打到有一方倒下；倒下的換下一隻上場（2026 新規則：倒下後換人不花回合）。
   *   - 場上存活的那隻保留 HP、能量、攻防增減與型態；護盾是整隊共用。
   *   - order：fixed＝依隊伍順序上場；best＝從還沒上場的寶可夢中，挑對目前對手評分最高的那隻。
   *  plan：護盾分配。PvPoke 的 1 對 1 邏輯會把護盾當成最後一隻在用（常常第一隻就開完），
   *   spread＝每一隻最多只能用「剩餘護盾 ÷ 還活著的隻數（無條件進位）」面，比較接近實戰；free＝需要就開。
   *  每一段對戰都是 PvPoke 引擎的 1 對 1 模擬，接續時把上一段結束的狀態當作開場狀態。 */
  function runTeam(cfg, TA, TB, order, plan) {
    var teams = [TA, TB];
    var st = teams.map(function (t) {
      return { alive: t.mons.map(function () { return true; }), cur: 0, carry: null, shields: t.shields == null ? 2 : t.shields };
    });
    function slotSide(t, k, carry, shields) {
      var s = {}, src = teams[t].mons[k];
      for (var x in src) s[x] = src[x];
      s.shields = shields; s.hpPct = 100;
      s.energy = carry ? carry.energy : 0; s.startHp = carry ? carry.hp : null;
      s.buffs = carry ? carry.buffs : null; s.form = carry ? carry.form : null;
      return s;
    }
    function ratingFor(t, me, op) {
      var s = t === 0 ? prepare(cfg, me, op) : prepare(cfg, op, me);
      s.b.simulate();
      return t === 0 ? ratingOf(s.p, s.q) : ratingOf(s.q, s.p);
    }
    function allow(t) {
      var n = st[t].alive.filter(Boolean).length;
      return plan === "free" || n <= 1 ? st[t].shields : Math.min(st[t].shields, Math.ceil(st[t].shields / n));
    }
    function pickNext(t, opp) {
      var cands = [];
      st[t].alive.forEach(function (a, k) { if (a) cands.push(k); });
      if (!cands.length) return -1;
      if (order !== "best" || cands.length === 1 || !opp) return cands[0];
      var best = cands[0], br = -1;
      cands.forEach(function (k) {
        var r = ratingFor(t, slotSide(t, k, null, allow(t)), opp);
        if (r > br) { br = r; best = k; }
      });
      return best;
    }
    var segs = [], offset = 0, ko = [[], []];
    for (var guard = 0; guard < 8; guard++) {
      var al = [allow(0), allow(1)];
      var A = slotSide(0, st[0].cur, st[0].carry, al[0]), B = slotSide(1, st[1].cur, st[1].carry, al[1]);
      var res = run(cfg, A, B);
      segs.push({ a: st[0].cur, b: st[1].cur, res: res, offset: offset, teamShields: [st[0].shields, st[1].shields], allowed: al });
      offset += res.lastTurn;
      var fa = res.end[0].hp <= 0, fb = res.end[1].hp <= 0;
      st[0].shields -= al[0] - res.end[0].shields; st[1].shields -= al[1] - res.end[1].shields;
      st[0].carry = fa ? null : res.end[0]; st[1].carry = fb ? null : res.end[1];
      if (fb) ko[0].push({ by: st[0].cur, victim: st[1].cur });
      if (fa) ko[1].push({ by: st[1].cur, victim: st[0].cur });
      if (fa) st[0].alive[st[0].cur] = false;
      if (fb) st[1].alive[st[1].cur] = false;
      if (!fa && !fb) break;
      var nA = st[0].cur, nB = st[1].cur;
      if (fa) nA = pickNext(0, fb ? null : slotSide(1, st[1].cur, st[1].carry, allow(1)));
      if (fb) nB = pickNext(1, fa ? null : slotSide(0, st[0].cur, st[0].carry, allow(0)));
      if (nA < 0 || nB < 0) break;
      st[0].cur = nA; st[1].cur = nB;
    }
    // 每隻的最大 HP 與剩餘 HP（沒上場的是滿血）
    var maxHp = [0, 1].map(function (t) {
      return teams[t].mons.map(function (m) {
        var b = newBattle(cfg), p = makePokemon(b, m, 0, cfg);
        return p.stats.hp;
      });
    });
    var hpLeft = [0, 1].map(function (t) {
      return teams[t].mons.map(function (m, k) {
        if (!st[t].alive[k]) return 0;
        if (k === st[t].cur && st[t].carry) return st[t].carry.hp;
        return maxHp[t][k];
      });
    });
    var left = st.map(function (x) { return x.alive.filter(Boolean).length; });
    var winner = left[0] && !left[1] ? 0 : (left[1] && !left[0] ? 1 : -1);
    var score = function (t) { return hpLeft[t].reduce(function (s, h, k) { return s + h / maxHp[t][k]; }, 0); };
    return {
      segments: segs, winner: winner, left: left, alive: st.map(function (x) { return x.alive.slice(); }),
      hpLeft: hpLeft, maxHp: maxHp, ko: ko, totalTurns: offset,
      shieldsUsed: [teams[0].shields - st[0].shields, teams[1].shields - st[1].shields], shieldsLeft: [st[0].shields, st[1].shields],
      margin: Math.round((score(0) - score(1)) * 100) / 100
    };
  }

  /** 3×3 整隊護盾矩陣：m[我方盾][對手盾] = { winner, left:[我方剩幾隻, 對手剩幾隻], margin }。 */
  function teamMatrix(cfg, TA, TB, order, plan) {
    var m = [];
    for (var i = 0; i <= 2; i++) {
      m.push([]);
      for (var j = 0; j <= 2; j++) {
        var r = runTeam(cfg, { mons: TA.mons, shields: i }, { mons: TB.mons, shields: j }, order, plan);
        m[i].push({ winner: r.winner, left: r.left, margin: r.margin });
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
    else out.push(teamNames[w] + " <b>獲勝</b>，還剩 <b>" + tr.left[w] + " 隻</b>：" + alive(w).join("、") + "。共 " + tr.totalTurns + " 回合（約 " + Math.round(tr.totalTurns / 2) + " 秒）。");
    [0, 1].forEach(function (t) {
      var cnt = {};
      tr.ko[t].forEach(function (k) { cnt[k.by] = (cnt[k.by] || 0) + 1; });
      var top = Object.keys(cnt).sort(function (a, b) { return cnt[b] - cnt[a]; })[0];
      if (top != null && cnt[top] >= 2) out.push(teamNames[t] + " 的 <b>" + names[t][top] + "</b> 一隻打倒了 " + cnt[top] + " 隻。");
    });
    var s0 = tr.segments[0], lead = s0.res.winner;
    out.push("先發對位：" + names[0][s0.a] + " 對 " + names[1][s0.b] + "，" + (lead === -1 ? "同歸於盡" : (lead === 0 ? names[0][s0.a] : names[1][s0.b]) + " 贏") + "。");
    out.push("護盾：" + teamNames[0] + " 用了 " + tr.shieldsUsed[0] + " 面、" + teamNames[1] + " 用了 " + tr.shieldsUsed[1] + " 面。");
    return out;
  }

  var api = {
    runTeam: runTeam, teamMatrix: teamMatrix, teamInsights: teamInsights,
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
