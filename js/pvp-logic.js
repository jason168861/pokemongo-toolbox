// js/pvp-logic.js
// --- Start of cpm.js content ---
const CPMs = [
  0.0939999967813491, 0.135137430784308, 0.166397869586944, 0.192650914456886,
  0.215732470154762, 0.236572655026622, 0.255720049142837, 0.273530381100769,
  0.29024988412857, 0.306057381335773, 0.321087598800659, 0.335445032295077,
  0.349212676286697, 0.36245774877879, 0.375235587358474, 0.387592411085168,
  0.399567276239395, 0.41119354951725, 0.422500014305114, 0.432926413410414,
  0.443107545375824, 0.453059953871985, 0.46279838681221, 0.472336077786704,
  0.481684952974319, 0.490855810259008, 0.499858438968658, 0.508701756943992,
  0.517393946647644, 0.525942508771329, 0.534354329109191, 0.542635762230353,
  0.550792694091796, 0.558830599438087, 0.566754519939422, 0.574569148039264,
  0.582278907299041, 0.589887911977272, 0.59740000963211, 0.604823657502073,
  0.61215728521347, 0.61940411056605, 0.626567125320434, 0.633649181622743,
  0.640652954578399, 0.647580963301656, 0.654435634613037, 0.661219263506722,
  0.667934000492096, 0.674581899290818, 0.681164920330047, 0.687684905887771,
  0.694143652915954, 0.700542893277978, 0.706884205341339, 0.713169102333341,
  0.719399094581604, 0.725575616972598, 0.731700003147125, 0.734741011137376,
  0.737769484519958, 0.740785574597326, 0.743789434432983, 0.746781208702482,
  0.749761044979095, 0.752729105305821, 0.75568550825119, 0.758630366519684,
  0.761563837528228, 0.764486065255226, 0.767397165298461, 0.77029727397159,
  0.77318650484085, 0.776064945942412, 0.778932750225067, 0.781790064808426,
  0.784636974334716, 0.787473583646825, 0.790300011634826, 0.792803950958807,
  0.795300006866455, 0.79780392148697, 0.800300002098083, 0.802803892322847,
  0.805299997329711, 0.807803863460723, 0.81029999256134, 0.812803834895026,
  0.815299987792968, 0.817803806620319, 0.820299983024597, 0.822803778631297,
  0.825299978256225, 0.827803750922782, 0.830299973487854, 0.832803753381377,
  0.835300028324127, 0.837803755931569, 0.840300023555755, 0.842803729034748,
  0.845300018787384, 0.847803702398935, 0.850300014019012, 0.852803676019539,
  0.85530000925064, 0.857803649892077, 0.860300004482269, 0.862803624012168,
  0.865299999713897,
];
// --- End of cpm.js content ---

// --- Start of leagues.js content ---
const LEAGUES = [
  { key: 'great', cp: 1500, name: '超級聯盟', icon:'https://raw.githubusercontent.com/RetroJohn86/PoGo-Unpacked-DL-Assets/refs/heads/main/Image%20Cache/Battle%20League/d296f502da73fd186835b4949ce0f6.png' },
  { key: 'ultra', cp: 2500, name: '高級聯盟' , icon:'https://raw.githubusercontent.com/RetroJohn86/PoGo-Unpacked-DL-Assets/refs/heads/main/Image%20Cache/Battle%20League/cc0ac43e0e99d93af3b098fff08751.png'},
  { key: 'master', cp: 10000, name: '大師聯盟', icon: 'https://raw.githubusercontent.com/RetroJohn86/PoGo-Unpacked-DL-Assets/refs/heads/main/Image%20Cache/Battle%20League/b7c026bb43f0d0bfc9742ee4860580.png'},
  { key: 'little', cp: 500, name: '小小盃', icon: 'https://raw.githubusercontent.com/RetroJohn86/PoGo-Unpacked-DL-Assets/refs/heads/main/Image%20Cache/Battle%20League/439c56a9910ad2d36ec706ae9e5bd3.png'},
];
// --- End of leagues.js content ---

// --- Start of logic.js content ---
function getCP(atk, def, sta, level) {
  const cpmIndex = (level - 1) * 2;
  const cpm = CPMs[cpmIndex];
  const cp = (atk * Math.sqrt(def) * Math.sqrt(sta) * Math.pow(cpm, 2)) / 10;
  return Math.floor(Math.max(10, cp));
}

function getIVSpreads(floor) {
  const ivCombinations= [];
  for (let atk = floor; atk <= 15; atk++) {
    for (let def = floor; def <= 15; def++) {
      for (let sta = floor; sta <= 15; sta++) {
        ivCombinations.push({ atk, def, sta });
      }
    }
  }
  return ivCombinations;
}

function getActualCPMIndex(estimatedCPM) {
  let start = 0;
  let end = CPMs.length - 1;
  while (start <= end) {
    const cpmIndex = (end + start) >> 1;
    if (CPMs[cpmIndex] < estimatedCPM) {
      start = cpmIndex + 1;
    }
    else if (CPMs[cpmIndex] > estimatedCPM) {
      end = cpmIndex - 1;
    }
    else {
      return cpmIndex;
    }
  }
  return start - 1;
}

function getLevel(atk, def, sta, maxCP, maxLevel) {
  if (maxCP === 10000) {
    return maxLevel;
  }
  const estimatedCPM = Math.pow(
    (100 * Math.pow(maxCP + 1, 2)) / (Math.pow(atk, 2) * def * sta),
    0.25,
  );
  const actualCPMIndex = getActualCPMIndex(estimatedCPM);
  return Math.min(1 + actualCPMIndex / 2, maxLevel);
}

function getStats(atk, def, sta, level) {
  const cpmIndex = (level - 1) * 2;
  const cpm = CPMs[cpmIndex];
  return {
    atk: atk * cpm,
    def: def * cpm,
    sta: Math.max(10, Math.floor(sta * cpm)),
  };
}

function getMaximizedStats(species, ivs, maxCP, maxLevel) {
  const atk = ivs.atk + species.stats.atk;
  const def = ivs.def + species.stats.def;
  const sta = ivs.sta + species.stats.sta;
  const level = getLevel(atk, def, sta, maxCP, maxLevel);
  const cp = getCP(atk, def, sta, level);
  const stats = getStats(atk, def, sta, level);
  const product = stats.atk * stats.def * stats.sta;
  const bulkProduct = stats.def * stats.sta;
  return { level, ivs, stats, cp, product, bulkProduct };
}

const compareToMax = (value, max) => ({
  value,
  percentOfMax: value / max,
});

function generateRankedSpreads(pokemon, floor, maxCP, maxLevel, minLevel, rankingMetric) {
  const getRankingMetricValue = (spread) => {
    if (rankingMetric === 'product') return spread.product;
    if (rankingMetric === 'bulkProduct') return spread.bulkProduct;
    return spread.stats[rankingMetric];
  };

  const ivSpreads = getIVSpreads(floor);
  const spreadsWithStats = ivSpreads
    .map((ivs) => getMaximizedStats(pokemon, ivs, maxCP, maxLevel))
    .filter((spreadWithStats) => spreadWithStats.level >= minLevel)
    .sort((a, b) => {
      if (getRankingMetricValue(b) === getRankingMetricValue(a)) {
        if (rankingMetric === 'product') return b.cp - a.cp;
        return b.product - a.product;
      }
      return getRankingMetricValue(b) - getRankingMetricValue(a);
    });

  if (spreadsWithStats.length === 0) return [];

  const rankOneSpread = spreadsWithStats[0];
  const output = [];
  for (let i = 0; i < spreadsWithStats.length; i++) {
    let rank = i + 1;
    const currentSpread = spreadsWithStats[i];
    const previousSpread = spreadsWithStats[i - 1];
    if (previousSpread && getRankingMetricValue(currentSpread) === getRankingMetricValue(previousSpread)) {
      rank = output[i - 1].rank;
    }
    output.push({
      rank,
      ivs: currentSpread.ivs,
      cp: currentSpread.cp,
      level: currentSpread.level,
      stats: {
        atk: compareToMax(currentSpread.stats.atk, rankOneSpread.stats.atk),
        def: compareToMax(currentSpread.stats.def, rankOneSpread.stats.def),
        sta: compareToMax(currentSpread.stats.sta, rankOneSpread.stats.sta),
      },
      product: compareToMax(currentSpread.product, rankOneSpread.product),
      bulkProduct: compareToMax(currentSpread.bulkProduct, rankOneSpread.bulkProduct),
    });
  }
  return output;
}
// --- End of logic.js content ---