#!/usr/bin/env node
/* 隊伍跑分：每個聯盟、每一種三隻組合與上場順序，對上「常用隊伍」打 3 對 3，算出隊伍分數。
 *
 *   node scripts/score_pvp_teams.js            # 三個聯盟，候選池前 30 名
 *   POOL=40 LEAGUES=1500 node scripts/score_pvp_teams.js
 *
 * 規則（頁面上的說明要和這裡一致）：
 *   候選池：data/pvp_sim.json 的 PvPoke 聯盟排名前 POOL 名（推薦招式、PvPoke 預設 IV）；
 *           同一隊不放兩隻同編號的寶可夢（暗影與一般型態算同一種）。
 *   組合：所有三隻組合 × 6 種上場順序（先發、2 號、3 號）；倒下後依隊伍順序上場（雙方都是）。
 *   對手：同一聯盟的「常用隊伍」（PvPoke 訓練模式的隊伍統計，data/pvp_sim.json 的 teams）。
 *   對戰：雙方 2 面護盾、護盾平均分配、AI 依 PvPoke 邏輯，模擬器 js/pvp-sim-core.js 的 match()。
 *   分數：每場 500 ＋（我方剩餘 HP 比例總和 − 對手剩餘 HP 比例總和）÷ 2 × 400，限制在 100～900；
 *         隊伍分數＝對全部常用隊伍的平均；另記勝、敗、平。
 * 輸出：data/pvp_team_scores.json。每個聯盟：
 *   pool：候選池 [speciesId, 一般招式, 特殊招式 1, 特殊招式 2]
 *   list：[總名次, [[先發, 2 號, 3 號（pool 的索引）, 分數, 勝, 敗, 平] × 6 種順序（分數高到低）]]
 *         依該組合最好的順序排序；收錄前 TOP 名，再補上每隻寶可夢分數最高的 3 組（讓頁面可以篩「含某隻」）。
 * 用 worker_threads 平行計算（核心數 − 2 個 worker）。
 */
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm"), os = require("os");
const { Worker, isMainThread, parentPort, workerData } = require("worker_threads");
const ROOT = path.resolve(__dirname, "..");

function loadCore() {
  const ctx = { window: {}, console: { log() {}, error() {}, warn() {} }, Math, JSON, Date, Map, Set, Array, Object, parseInt, parseFloat, isNaN };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(ROOT, "js/pvpoke-engine.js"), "utf8"), ctx);
  vm.runInContext(fs.readFileSync(path.join(ROOT, "js/pvp-sim-core.js"), "utf8"), ctx);
  const C = vm.runInContext("PvPSimCore", ctx);
  const data = JSON.parse(fs.readFileSync(path.join(ROOT, "data/pvp_sim.json"), "utf8"));
  C.init(ctx.window.PvPokeEngine, data);
  return { C, data };
}
const mon = (r) => ({ id: r[0], fast: r[1], c1: r[2], c2: r[3] || null, iv: { mode: "def" } });
function battleScore(r) {
  const sc = (t) => r.hpLeft[t].reduce((a, h, k) => a + h / r.maxHp[t][k], 0);
  return Math.max(100, Math.min(900, 500 + (sc(0) - sc(1)) / 2 * 400));
}

if (!isMainThread) {
  // ---- worker：拿到一批隊伍，對全部對手打一輪 ----
  const { C } = loadCore();
  const { cp, pool, teams, opps } = workerData;
  const cfg = { cp, levelCap: 50 };
  const oppSides = opps.map((o) => ({ mons: o.mons.map(mon), shields: 2 }));
  const out = [];
  let done = 0;
  for (const t of teams) {
    const mine = { mons: t.map((i) => mon(pool[i])), shields: 2 };
    let sum = 0, w = 0, l = 0, d = 0;
    for (const o of oppSides) {
      const r = C.match(cfg, [mine, o], { order: "fixed", plan: "spread" });
      sum += battleScore(r);
      if (r.winner === 0) w++; else if (r.winner === 1) l++; else d++;
    }
    out.push({ t, score: Math.round(sum / oppSides.length * 10) / 10, w, l, d });
    if (++done % 50 === 0) parentPort.postMessage({ progress: 50 });
  }
  parentPort.postMessage({ progress: done % 50, result: out });
  return;
}

// ---- 主程式 ----
const POOL = Number(process.env.POOL || 30), TOP = Number(process.env.TOP || 400);
const LEAGUES = (process.env.LEAGUES || "1500,2500,10000").split(",").map(Number);
const WORKERS = Math.max(1, Number(process.env.WORKERS || os.cpus().length - 2));
const { data, C } = loadCore();

function permutations(a) {
  return [[a[0], a[1], a[2]], [a[0], a[2], a[1]], [a[1], a[0], a[2]], [a[1], a[2], a[0]], [a[2], a[0], a[1]], [a[2], a[1], a[0]]];
}

async function runLeague(cp) {
  const ranks = (data.ranks[String(cp)] || []).slice(0, POOL), pool = ranks.map((r) => r.slice(0, 4));
  const opps = (data.teams || {})[String(cp)] || [];
  if (!ranks.length || !opps.length) { console.log(`${cp}：沒有排名或常用隊伍，略過`); return null; }
  const dex = (id) => C.mon(id).dex;
  const teams = [];
  for (let i = 0; i < ranks.length; i++) for (let j = i + 1; j < ranks.length; j++) for (let k = j + 1; k < ranks.length; k++) {
    if (new Set([i, j, k].map((x) => dex(pool[x][0]))).size < 3) continue;   // 同一種寶可夢不放兩隻
    for (const p of permutations([i, j, k])) teams.push(p);
  }
  const total = teams.length * opps.length;
  console.log(`${cp}：候選 ${ranks.length} 隻、${teams.length} 種隊伍（含順序）× 常用隊伍 ${opps.length} 隊 = ${total.toLocaleString()} 場，${WORKERS} 個 worker`);
  const t0 = Date.now(), chunks = [];
  const size = Math.ceil(teams.length / WORKERS);
  for (let i = 0; i < teams.length; i += size) chunks.push(teams.slice(i, i + size));
  let progress = 0, lastLog = 0;
  const results = (await Promise.all(chunks.map((ch) => new Promise((resolve, reject) => {
    const w = new Worker(__filename, { workerData: { cp, pool, teams: ch, opps } });
    w.on("message", (m) => {
      if (m.progress) {
        progress += m.progress;
        if (Date.now() - lastLog > 15000) { lastLog = Date.now(); console.log(`  ${cp}：${progress}/${teams.length}（${Math.round((Date.now() - t0) / 1000)} 秒）`); }
      }
      if (m.result) resolve(m.result);
    });
    w.on("error", reject);
  })))).flat();
  // 同一組合（不分順序）的 6 種順序放在一起，依最好的順序排序
  const byCombo = new Map();
  for (const r of results) {
    const key = r.t.slice().sort((a, b) => a - b).join(",");
    if (!byCombo.has(key)) byCombo.set(key, []);
    byCombo.get(key).push([r.t[0], r.t[1], r.t[2], r.score, r.w, r.l, r.d]);
  }
  const combos = [...byCombo.values()].map((o) => o.sort((a, b) => b[3] - a[3] || b[4] - a[4]));
  combos.sort((a, b) => b[0][3] - a[0][3] || b[0][4] - a[0][4]);
  const keep = new Set(combos.slice(0, TOP).map((_, i) => i));
  pool.forEach((_, idx) => {
    let n = 0;
    for (let i = 0; i < combos.length && n < 3; i++) if (combos[i][0].slice(0, 3).includes(idx)) { keep.add(i); n++; }
  });
  const list = [...keep].sort((a, b) => a - b).map((i) => [i + 1, combos[i]]);
  const best = combos[0][0];
  console.log(`  ${cp}：完成，${Math.round((Date.now() - t0) / 1000)} 秒；${combos.length} 種組合，第 1 名 ${best.slice(0, 3).map((x) => C.mon(pool[x][0]).speciesName).join("・")} ${best[3]}（${best[4]} 勝 ${best[5]} 敗）`);
  return { pool, opponents: opps.length, battles: total, combos: combos.length, list };
}

(async () => {
  const out = {
    generated: new Date().toISOString().slice(0, 10), gm: data.gm, teamsUpdated: data.teamsUpdated,
    method: { pool: POOL, shields: 2, plan: "spread", order: "fixed", opponents: "common teams" }, leagues: {}
  };
  for (const cp of LEAGUES) { const r = await runLeague(cp); if (r) out.leagues[String(cp)] = r; }
  const file = path.join(ROOT, "data", "pvp_team_scores.json");
  fs.writeFileSync(file, JSON.stringify(out));
  console.log(`已寫出 data/pvp_team_scores.json（${fs.statSync(file).size.toLocaleString()} bytes）`);
})();
