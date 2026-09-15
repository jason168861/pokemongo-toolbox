/* 交易清單的「查價搜尋字」規則 —— index.html(使用者按 $)與 price-editor.html(站長調規則)共用。
   兩邊一定要跑同一份程式,不然編輯器預覽看到的字,跟使用者實際搜到的會對不起來。

   組字順序(先命中先用):
     1. combo[組合鍵]  整句指定某一個組合(背卡 + 造型那種社群叫法千奇百怪的)
     2. template 套字  預設 "pokemon go {name} {shiny} {kind} {form} {bg}"
          {name}  mon[圖鑑編號],沒設就用英文官方名(eBay 是英文站)
          {shiny} words.shiny(異色才有)
          {kind}  words.dynamax / gigantamax / purified(看卡片的徽章)
          {form}  form["編號|代碼"](只套用這隻)→ form[代碼](全部共用)→ 都沒設就不加
                  —— JAN_2020_NOEVOLVE 這種代碼拿去搜只會更糟;設成 "" = 這隻不加
          {bg}    bg[背卡 image_name],沒設就用「城市 / 活動名 + background」;設成 "" = 不加
          {dex}   圖鑑編號
   使用者對單張卡自己改的字(c.pq)不歸這裡管,index.html 會先看那個。

   組合鍵 = 編號|shiny|kind|型態造型代碼|背卡 image_name,例:"150|shiny||| GO Las Vegas background.png"
   只由卡片本身算得出來的欄位組成 → 使用者清單裡存的舊卡也對得到。 */
(function(root){
  const DEF={
    template:'pokemon go {name} {shiny} {kind} {form} {bg}',
    words:{shiny:'shiny',dynamax:'dynamax',gigantamax:'gigantamax',purified:'purified',background:'background'},
    // {q} 會換成搜尋字
    sites:{ebay:'https://www.ebay.com/sch/i.html?_nkw={q}'},
  };
  const own=(o,k)=>!!o&&Object.prototype.hasOwnProperty.call(o,k);
  const isStr=v=>typeof v==='string';

  // 檔案壞掉 / 欄位型別不對 → 該欄退回預設,不讓整個查價功能掛掉
  function normCfg(d){
    d=d&&typeof d==='object'?d:{};
    const pick=(def,over)=>{ const o={...def};
      if(over&&typeof over==='object') for(const k in def) if(isStr(over[k])) o[k]=over[k];
      return o; };
    const map=m=>{ const o={};
      if(m&&typeof m==='object') for(const k in m) if(isStr(m[k])) o[k]=m[k];
      return o; };
    return {
      template:isStr(d.template)&&d.template.trim()?d.template:DEF.template,
      words:pick(DEF.words,d.words), sites:pick(DEF.sites,d.sites),
      mon:map(d.mon), form:map(d.form), bg:map(d.bg), combo:map(d.combo),
    };
  }
  // 卡片只存了徽章圖的路徑(與中文 tag),從這裡反推是哪一種
  function kindOf(c){
    const b=String((c&&c.badge)||''), t=(c&&c.tag)||'';
    if(/gigantamax/i.test(b)||t==='超極巨化') return 'gigantamax';
    if(/dynamax/i.test(b)||t==='極巨化') return 'dynamax';
    if(/purified/i.test(b)||t==='淨化') return 'purified';
    return '';
  }
  function bgOf(c,BG){ return (c&&c.bg&&(BG||[]).find(b=>b.image_url===c.bg))||null; }
  // 卡片沒存型態/造型代碼 → 用 sprite 網址回查 pokemon.json。
  // 對不到(wiki 原圖、超極巨化圖)就是空字串;base_form 本身不算型態
  function formCodeOf(c,POKE){
    const p=c&&POKE&&POKE[c.dex]; if(!p||!p.variants) return '';
    const v=p.variants.find(x=>x.url===c.url); if(!v) return '';
    return v.costume||(v.form&&v.form!==p.base_form?v.form:'');
  }
  function comboKey(c,ctx){
    const b=bgOf(c,ctx.BG);
    return [c.dex, c.shiny?'shiny':'', kindOf(c), formCodeOf(c,ctx.POKE), b?b.image_name:''].join('|');
  }
  // 地點卡只取城市(「Las Vegas, Nevada, USA」→「Las Vegas」),活動卡用全名
  function defaultBgWord(b,words){
    if(!b||!b.name) return '';
    const nm=(b.type==='location'?b.name.split(',')[0]:b.name).trim();
    const w=(words||DEF.words).background;
    return w?nm+' '+w:nm;
  }
  // ctx = {POKE, BG, enName(dex)};opt.ignoreCombo = 只看規則(編輯器顯示「不整句指定時會是什麼」用)
  function build(c,cfg,ctx,opt){
    cfg=cfg||normCfg(null);
    if(!(opt&&opt.ignoreCombo)){
      const k=comboKey(c,ctx);
      if(isStr(cfg.combo[k])&&cfg.combo[k].trim()) return cfg.combo[k].trim();
    }
    const W=cfg.words, b=bgOf(c,ctx.BG), code=formCodeOf(c,ctx.POKE), kind=kindOf(c), dex=String(c.dex);
    const val={
      name: own(cfg.mon,dex)?cfg.mon[dex]:(ctx.enName?ctx.enName(c.dex):dex),
      shiny: c.shiny?W.shiny:'',
      kind: kind?W[kind]:'',
      // 先看「這隻 + 代碼」(dex|CODE),沒有才用全部共用的 CODE —— 同一個造型代碼在不同寶可夢身上常是不同東西
      form: !code ? '' : own(cfg.form,dex+'|'+code) ? cfg.form[dex+'|'+code] : own(cfg.form,code) ? cfg.form[code] : '',
      bg: b?(own(cfg.bg,b.image_name)?cfg.bg[b.image_name]:defaultBgWord(b,W)):'',
      dex,
    };
    return cfg.template.replace(/\{(\w+)\}/g,(m,k)=>own(val,k)?val[k]:m).replace(/\s+/g,' ').trim();
  }
  function siteURL(tpl,q){
    tpl=tpl||'';
    return tpl.includes('{q}') ? tpl.split('{q}').join(encodeURIComponent(String(q||'').trim())) : tpl;
  }
  root.PriceQuery={DEF,own,normCfg,kindOf,bgOf,formCodeOf,comboKey,defaultBgWord,build,siteURL};
})(typeof window!=='undefined'?window:globalThis);
