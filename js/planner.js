(function(global){
  const RATING_SCORE={"▲▲▲":50,"▲▲":40,"▲":30,"⊜":20,"▼":10,"▼▼":5,"▼▼▼":0,"":15};
  function excludedNames(display){const out=new Set(); let m; const re=/\((?:no|without)\s+([^)]*)\)/gi; while((m=re.exec(display))){m[1].split(/\s+and\s+|\s*,\s*/i).map(x=>x.trim().toLowerCase()).filter(Boolean).forEach(x=>out.add(x));} const re2=/\(instead of\s+([^)]*)\)/gi; while((m=re2.exec(display))){const x=m[1].trim().toLowerCase();if(x)out.add(x);} return out;}
  function resolveTeam(token,teams={}){
    const raw=String(token||'').trim().toLowerCase();
    if(teams[raw])return teams[raw];
    const base=raw.replace(/\s*\([^)]*\)\s*$/,'').trim();
    if(base&&teams[base])return teams[base];
    return null;
  }
  function expandedTokens(counter,teams={}){
    const out=new Set();
    for(const token of (counter.tokens||[])){
      const roster=resolveTeam(token,teams);
      if(roster)for(const c of roster)out.add(String(c).trim().toLowerCase());
      else out.add(String(token).trim().toLowerCase());
    }
    for(const x of excludedNames(counter.display))out.delete(x);
    return out;
  }
  function conflictMap(selected,teams={}){const usage={}; selected.forEach((c,i)=>{for(const token of expandedTokens(c,teams)){(usage[token]??=[]).push(i);}}); return Object.fromEntries(Object.entries(usage).filter(([,v])=>v.length>1));}
  function chooseBest(countersPerRoom,teams={},excluded=new Set(),fixed={}){
    if(!countersPerRoom.length||countersPerRoom.some(x=>!x.length))return {combo:[],conflicts:{},score:-1e9};
    const pools=countersPerRoom.map((counters,i)=>{
      const forced=fixed&&fixed[i];
      const source=forced?[forced]:counters.slice().sort((a,b)=>((b.score??RATING_SCORE[b.rating]??15)-(a.score??RATING_SCORE[a.rating]??15))||a.display.localeCompare(b.display,undefined,{sensitivity:'base'}));
      return source.filter(c=>{
        for(const x of expandedTokens(c,teams))if(excluded.has(x))return false;
        return true;
      }).slice(0,forced?1:20);
    });
    if(pools.some(x=>!x.length))return {combo:[],conflicts:{},score:-1e9};
    let beam=[{score:0,combo:[],counts:{}}];const width=5000;
    for(const pool of pools){
      const next=[];
      for(const state of beam){
        for(const c of pool){
          const counts={...state.counts};let added=0,newDup=0;
          for(const token of expandedTokens(c,teams)){
            const prev=counts[token]||0;
            if(prev>=1){added++;if(prev===1)newDup++;}
            counts[token]=prev+1;
          }
          const score=state.score+(c.score??RATING_SCORE[c.rating]??15)-added*200-newDup*50;
          next.push({score,combo:[...state.combo,c],counts});
        }
      }
      next.sort((a,b)=>b.score-a.score);beam=next.slice(0,width);
    }
    const best=beam[0];return {combo:best.combo,conflicts:conflictMap(best.combo,teams),score:best.score};
  }
  function overlap(a,b,teams={}){
    const aa=expandedTokens(a,teams),bb=expandedTokens(b,teams);
    return [...aa].filter(x=>bb.has(x));
  }
  global.MSFPlanner={RATING_SCORE,expandedTokens,conflictMap,chooseBest,overlap};
})(window);
