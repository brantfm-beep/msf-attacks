const state={mode:'Alliance War',data:null,teamDirectory:{},publicRosters:{},dataStatus:null,characters:[],roomCount:1,planDefs:[],planLocks:{},defenses:JSON.parse(localStorage.getItem('msf-war-defenses')||'[]'),editDefense:null,teams:JSON.parse(localStorage.getItem('msf-team-rosters')||'{}')};
const $=id=>document.getElementById(id);
const els={warMode:$('warMode'),ccMode:$('ccMode'),season:$('season'),source:$('source'),rooms:$('rooms'),remainingTitle:$('remainingTitle'),hint:$('hint'),addBtn:$('addBtn'),removeBtn:$('removeBtn'),buildBtn:$('buildBtn'),clearBtn:$('clearBtn'),defenseBtn:$('defenseBtn'),defenseCount:$('defenseCount'),resultsPanel:$('resultsPanel'),results:$('results'),dialog:$('defenseDialog'),saved:$('savedDefenses'),defName:$('defName'),members:$('memberInputs'),defMsg:$('defenseMessage'),teamTemplate:$('teamTemplate'),useTemplate:$('useTemplate'),templateMsg:$('templateMessage')};
function esc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function db(){return state.data[state.mode]}
function groups(){return [...new Set(db().defenses.map(d=>d.group))].sort((a,b)=>a.localeCompare(b,undefined,{sensitivity:'base'}));}
function defsFor(g){return db().defenses.filter(d=>d.group===g).sort((a,b)=>a.variant.localeCompare(b.variant,undefined,{sensitivity:'base'}));}
function selectedValues(){return [...els.rooms.querySelectorAll('.room')].map(r=>({group:r.querySelector('.group').value,variant:r.querySelector('.variant')?.value||''}));}
function setMode(mode){state.mode=mode;state.roomCount=1;els.warMode.classList.toggle('active',mode==='Alliance War');els.ccMode.classList.toggle('active',mode==='Cosmic Crucible');renderHeader();renderRooms();clearResults();}
function renderHeader(){const war=state.mode==='Alliance War',max=war?14:6,noun=war?'attacks':'rooms';els.season.textContent=`${state.mode} • ${db().season} • ${db().defenses.length} defense configurations`;els.source.textContent=`Bundled v0.4.0 counter snapshot • local web build`;els.remainingTitle.textContent=war?'Remaining Attacks':'Remaining Rooms';els.hint.textContent=`Plan only the ${noun} you still need (1–${max}).`;els.addBtn.textContent=war?'+ Add Attack':'+ Add Room';els.removeBtn.textContent=war?'− Remove Attack':'− Remove Room';els.clearBtn.textContent=war?'Clear Attacks':'Clear Rooms';els.buildBtn.textContent=war?'Build War Plan':'Build Crucible Plan';els.defenseBtn.style.display=war?'':'none';renderDefenseCount();}
function renderRooms(preserve=[]){const war=state.mode==='Alliance War',gs=groups();els.rooms.innerHTML='';for(let i=0;i<state.roomCount;i++){const card=document.createElement('div');card.className='room';card.innerHTML=`<h3>${war?'ATTACK':'ROOM'} ${i+1}</h3><div class="field-row"><label>Defense</label><select class="group"><option value=""></option>${gs.map(g=>`<option>${esc(g)}</option>`).join('')}</select></div>${war?'':'<div class="field-row"><label>Variant</label><select class="variant"><option value=""></option></select></div>'}`;els.rooms.appendChild(card);const group=card.querySelector('.group'),variant=card.querySelector('.variant');group.addEventListener('change',()=>{if(variant){const defs=defsFor(group.value);variant.innerHTML='<option value=""></option>'+defs.map(d=>`<option>${esc(d.variant)}</option>`).join('');const base=defs.find(d=>d.variant.localeCompare(group.value,undefined,{sensitivity:'base'})===0)||defs[0];if(base)variant.value=base.variant;}clearResults();});if(preserve[i]?.group){group.value=preserve[i].group;group.dispatchEvent(new Event('change'));if(variant&&preserve[i].variant)variant.value=preserve[i].variant;} }
}
function currentDefense(card){const g=card.querySelector('.group').value;if(!g)return null;const defs=defsFor(g);if(state.mode==='Alliance War')return defs[0]||null;const v=card.querySelector('.variant').value;return defs.find(d=>d.variant===v)||null;}
function excludedWarChars(){const s=new Set();state.defenses.forEach(d=>(d.members||[]).forEach(x=>s.add(x.trim().toLowerCase())));return s;}
function clearResults(){state.planDefs=[];state.planLocks={};els.resultsPanel.classList.add('hidden');els.results.innerHTML='';}
function plannerTeams(){
  const out={};
  Object.entries(state.publicRosters||{}).forEach(([team,entry])=>{
    const members=Array.isArray(entry)?entry:(entry&&Array.isArray(entry.members)?entry.members:[]);
    if(members.length)out[team.toLowerCase()]=members.map(x=>String(x).trim().toLowerCase());
  });
  Object.entries(state.teams||{}).forEach(([team,members])=>{
    const key=team.toLowerCase();
    if(!out[key]&&Array.isArray(members)&&members.length)out[key]=members.map(x=>String(x).trim().toLowerCase());
  });
  return out;
}
function lockedUsedTokens(exceptRoom=-1){
  const teams=plannerTeams(),used=new Set();
  Object.entries(state.planLocks).forEach(([i,c])=>{
    if(Number(i)===exceptRoom||!c)return;
    MSFPlanner.expandedTokens(c,teams).forEach(x=>used.add(x));
  });
  return used;
}
function counterBlockedByLocks(counter,roomIndex){
  const used=lockedUsedTokens(roomIndex),teams=plannerTeams();
  return [...MSFPlanner.expandedTokens(counter,teams)].filter(x=>used.has(x));
}
function setCounterLock(roomIndex,counterIndex){
  const d=state.planDefs[roomIndex];
  if(!d)return;
  const counter=d.counters[counterIndex];
  if(!counter)return;
  const blocked=counterBlockedByLocks(counter,roomIndex);
  if(blocked.length)return;
  if(state.planLocks[roomIndex]===counter)delete state.planLocks[roomIndex];
  else state.planLocks[roomIndex]=counter;
  renderPlanResults();
}

function buildPlan(){
  const cards=[...els.rooms.querySelectorAll('.room')],defs=[];
  for(let i=0;i<cards.length;i++){
    const d=currentDefense(cards[i]);
    if(!d){alert(`Choose a defense for ${state.mode==='Alliance War'?'Attack':'Room'} ${i+1}.`);return;}
    defs.push(d);
  }
  state.planDefs=defs;
  state.planLocks={};
  renderPlanResults(true);
}

function renderPlanResults(scroll=false){
  const defs=state.planDefs;
  if(!defs.length)return;
  const teams=plannerTeams();
  const excluded=state.mode==='Alliance War'?excludedWarChars():new Set();
  const {combo,conflicts}=MSFPlanner.chooseBest(defs.map(d=>d.counters),teams,excluded,state.planLocks);
  if(!combo.length){
    els.results.innerHTML='<div class="attack-card">No usable counter combination could be built'+(excluded.size?' after excluding your saved War-defense characters.':'')+'</div>';
    els.resultsPanel.classList.remove('hidden');
    return;
  }
  const noun=state.mode==='Alliance War'?'Attack':'Room',ct=Object.keys(conflicts).length;
  const lockCount=Object.keys(state.planLocks).length;
  let html=`<div class="summary"><span class="pill">${defs.length} ${noun}${defs.length===1?'':'s'}</span><span class="pill ${ct?'warn':'ok'}">${ct?`⚠ ${ct} conflict token${ct===1?'':'s'}`:'✓ No detected conflicts'}</span>${state.mode==='Cosmic Crucible'?`<span class="pill">${lockCount} locked choice${lockCount===1?'':'s'}</span>`:''}${state.mode==='Alliance War'&&state.defenses.length?`<span class="pill">Defense: ${state.defenses.length} teams / ${excluded.size} characters</span>`:''}</div>`;
  if(state.mode==='Cosmic Crucible')html+=`<div class="plan-help">Click any counter below to lock that team for a room. Other unlocked rooms will recalculate automatically, and counters that reuse a locked character will be unavailable.</div>`;
  const conflictSet=new Set(Object.keys(conflicts));
  defs.forEach((d,i)=>{
    const c=combo[i],locked=state.planLocks[i]===c;
    const bad=[...MSFPlanner.expandedTokens(c,teams)].filter(x=>conflictSet.has(x));
    const alts=d.counters.slice().sort((a,b)=>b.score-a.score||a.display.localeCompare(b.display)).slice(0,14);
    html+=`<article class="attack-card"><div class="attack-head"><div><div class="eyebrow">${noun.toUpperCase()} ${i+1}</div><h3>${esc(d.variant)}</h3></div><div class="rating">${esc(c.rating)}</div></div><div class="selected-counter"><strong>Selected counter:</strong> ${esc(c.display)} ${locked?'<span class="locked-tag">LOCKED</span>':'<span class="auto-tag">AUTO</span>'}${bad.length?`<div class="conflict">Conflict: ${bad.map(x=>esc(title(x))).join(', ')}</div>`:''}</div>${c.notes?`<div class="strategy"><strong>Strategy</strong><br>${esc(c.notes)}</div>`:''}<details class="alternatives" open><summary>Counter choices</summary>${alts.map(a=>{
      const blockedByDefense=[...MSFPlanner.expandedTokens(a,teams)].some(x=>excluded.has(x));
      const blocked=counterBlockedByLocks(a,i);
      const disabled=blockedByDefense||blocked.length>0;
      const ai=d.counters.indexOf(a);
      const selected=a===c;
      const isLocked=state.planLocks[i]===a;
      const reason=blocked.length?`<div class="counter-block-reason">Already used: ${blocked.map(x=>esc(title(x))).join(', ')}</div>`:(blockedByDefense?'<div class="counter-block-reason">Character is on your War defense</div>':'');
      return `<button type="button" class="alt counter-choice ${selected?'selected':''} ${isLocked?'locked':''}" data-room="${i}" data-counter="${ai}" ${disabled?'disabled':''}><div class="alt-title">${selected?'●':'○'} ${esc(a.display)} ${esc(a.rating)} ${isLocked?'<span class="locked-tag">LOCKED</span>':''}</div>${a.notes?`<div class="alt-strategy"><strong>Strategy:</strong> ${esc(a.notes)}</div>`:''}${reason}</button>`;
    }).join('')}</details></article>`;
  });
  if(ct)html+='<article class="attack-card"><h3>Detected conflicts</h3>'+Object.entries(conflicts).sort().map(([t,idxs])=>`<div class="conflict">• ${esc(title(t))} — ${noun}s ${idxs.map(i=>i+1).join(', ')}</div>`).join('')+'</article>';
  els.results.innerHTML=html;
  els.results.querySelectorAll('.counter-choice:not(:disabled)').forEach(btn=>btn.onclick=()=>setCounterLock(Number(btn.dataset.room),Number(btn.dataset.counter)));
  els.resultsPanel.classList.remove('hidden');
  if(scroll)els.resultsPanel.scrollIntoView({behavior:'smooth',block:'start'});
}
function title(s){return s.replace(/\b\w/g,c=>c.toUpperCase())}
function renderDefenseCount(){els.defenseCount.textContent=`${state.defenses.length}/12`;}
function openDefense(){state.editDefense=null;renderSaved();clearDefenseEditor();els.dialog.showModal();}
function renderSaved(){els.saved.innerHTML=state.defenses.length?state.defenses.map((d,i)=>`<button type="button" class="saved-item ${state.editDefense===i?'active':''}" data-i="${i}"><span><strong>${esc(d.name||`Defense ${i+1}`)}</strong><br><small>${d.members.map(esc).join(', ')}</small></span><span>›</span></button>`).join(''):'<div class="muted">No saved War defenses yet.</div>';els.saved.querySelectorAll('button').forEach(b=>b.onclick=()=>editDefense(Number(b.dataset.i)));}
function clearDefenseEditor(){els.defName.value='';els.teamTemplate.value='';[...els.members.querySelectorAll('.member-select')].forEach(x=>x.value='');els.defMsg.textContent='';els.defMsg.className='message';els.templateMsg.textContent='Choose a team to name the defense and start from that template; all five character slots remain editable.';}
function editDefense(i){state.editDefense=i;const d=state.defenses[i];els.defName.value=d.name||'';els.teamTemplate.value=state.teamDirectory[d.name]!==undefined?d.name:'';[...els.members.querySelectorAll('.member-select')].forEach((x,n)=>setMemberValue(x,d.members[n]||''));els.templateMsg.textContent='Editing saved defense. You can replace any character slot.';renderSaved();}
function saveDefense(){const name=els.defName.value.trim()||'Custom Defense',members=[...els.members.querySelectorAll('.member-select')].map(x=>x.value.trim());if(members.some(x=>!x))return msg('All five character slots must be filled.',true);const known=new Map(state.characters.map(c=>[String(c).toLowerCase(),String(c)]));for(let i=0;i<members.length;i++){const canonical=known.get(members[i].toLowerCase());if(!canonical)return msg(`${members[i]} is not in the current MSF character directory. Choose a character from the dropdown.`,true);members[i]=canonical;}const folded=members.map(x=>x.toLowerCase());if(new Set(folded).size!==5)return msg('A defense cannot contain the same character twice.',true);const used={};state.defenses.forEach((d,i)=>{if(i!==state.editDefense)d.members.forEach(c=>used[c.toLowerCase()]=d.name)});const clash=members.find(c=>used[c.toLowerCase()]);if(clash)return msg(`${clash} is already on ${used[clash.toLowerCase()]}.`,true);if(state.editDefense===null&&state.defenses.length>=12)return msg('Alliance War allows a maximum of 12 saved defenses.',true);const item={name,members};if(state.editDefense===null){state.defenses.push(item);state.editDefense=state.defenses.length-1}else state.defenses[state.editDefense]=item;if(state.teamDirectory[name]!==undefined){state.teams[name.toLowerCase()]=members.map(x=>x.toLowerCase());localStorage.setItem('msf-team-rosters',JSON.stringify(state.teams));}persistDefenses();renderSaved();msg('Defense saved. These characters are excluded from War offense plans.',false);clearResults();}
function deleteDefense(){if(state.editDefense===null)return;state.defenses.splice(state.editDefense,1);state.editDefense=null;persistDefenses();renderSaved();clearDefenseEditor();clearResults();}
function persistDefenses(){localStorage.setItem('msf-war-defenses',JSON.stringify(state.defenses));renderDefenseCount();}
function msg(t,error){els.defMsg.textContent=t;els.defMsg.className='message '+(error?'error':'success');}
function enrichCharactersFromRosters(){
  const names=new Map();
  const add=v=>{
    const s=String(v||'').trim();
    if(s&&!names.has(s.toLowerCase()))names.set(s.toLowerCase(),s);
  };
  state.characters.forEach(add);
  Object.values(state.publicRosters||{}).forEach(entry=>{
    const members=Array.isArray(entry)?entry:(entry&&Array.isArray(entry.members)?entry.members:[]);
    members.forEach(add);
  });
  Object.values(state.teams||{}).forEach(members=>{
    if(Array.isArray(members))members.forEach(add);
  });
  state.defenses.forEach(d=>(d.members||[]).forEach(add));
  state.characters=[...names.values()].sort((a,b)=>a.localeCompare(b,undefined,{sensitivity:'base'}));
}

function renderTeamTemplates(){const current=els.teamTemplate.value;els.teamTemplate.innerHTML='<option value=""></option>'+Object.keys(state.teamDirectory).sort((a,b)=>a.localeCompare(b,undefined,{sensitivity:'base'})).map(t=>`<option value="${esc(t)}">${esc(t)}</option>`).join('');if(current&&state.teamDirectory[current]!==undefined)els.teamTemplate.value=current;}
function setMemberValue(input,value){input.value=value||'';}

function closeCharacterMenus(except=null){
  document.querySelectorAll('.character-menu.open').forEach(m=>{
    if(m!==except)m.classList.remove('open');
  });
}

function characterMatches(query){
  const q=String(query||'').trim().toLowerCase();
  const names=[...new Set(state.characters)].sort((a,b)=>a.localeCompare(b,undefined,{sensitivity:'base'}));
  if(!q)return names;
  return names.filter(n=>n.toLowerCase().includes(q));
}

function populateCharacterMenu(input,menu){
  const matches=characterMatches(input.value);
  menu.innerHTML=matches.length
    ? matches.map(n=>`<button type="button" class="character-option" data-value="${esc(n)}">${esc(n)}</button>`).join('')
    : '<div class="character-empty">No matching character</div>';
  menu.querySelectorAll('.character-option').forEach(btn=>{
    btn.addEventListener('mousedown',e=>e.preventDefault());
    btn.addEventListener('click',()=>{
      input.value=btn.dataset.value||'';
      menu.classList.remove('open');
      input.focus();
    });
  });
}

function wireCharacterPicker(input,menu){
  const open=()=>{
    populateCharacterMenu(input,menu);
    closeCharacterMenus(menu);
    menu.classList.add('open');
  };
  input.addEventListener('focus',open);
  input.addEventListener('click',open);
  input.addEventListener('input',open);
  input.addEventListener('keydown',e=>{
    if(e.key==='Escape'){menu.classList.remove('open');input.blur();}
  });
  input.addEventListener('blur',()=>{
    setTimeout(()=>menu.classList.remove('open'),120);
  });
}

function renderCharacterDropdowns(){
  const current=[...els.members.querySelectorAll('.member-select')].map(x=>x.value);
  els.members.innerHTML='';
  for(let i=0;i<5;i++){
    const wrap=document.createElement('label');
    wrap.className='member-picker-label';
    wrap.innerHTML=`Character ${i+1}<div class="character-picker"><input class="member-select" type="text" autocomplete="off" spellcheck="false" placeholder="Choose character"><div class="character-menu"></div></div>`;
    els.members.appendChild(wrap);
    const input=wrap.querySelector('.member-select');
    const menu=wrap.querySelector('.character-menu');
    input.value=current[i]||'';
    wireCharacterPicker(input,menu);
  }
}

function useTeamTemplate(){
  const team=els.teamTemplate.value.trim();
  if(!team){els.templateMsg.textContent='Choose a Marvel Church team template first.';return;}
  els.defName.value=team;
  const saved=state.defenses.find(d=>(d.name||'').toLowerCase()===team.toLowerCase());
  const localCached=state.teams[team.toLowerCase()];
  const publicEntry=state.publicRosters[team]||state.publicRosters[team.toLowerCase()];
  const publicMembers=Array.isArray(publicEntry)?publicEntry:(publicEntry&&Array.isArray(publicEntry.members)?publicEntry.members:null);
  const members=saved?.members||(Array.isArray(publicMembers)&&publicMembers.length>=3&&publicMembers.length<=5?publicMembers:null)||(Array.isArray(localCached)&&localCached.length>=3&&localCached.length<=5?localCached:null);
  if(members){
    [...els.members.querySelectorAll('.member-select')].forEach((x,n)=>setMemberValue(x,members[n]||''));
    state.teams[team.toLowerCase()]=members.map(x=>String(x));
    localStorage.setItem('msf-team-rosters',JSON.stringify(state.teams));
    enrichCharactersFromRosters();
    const selected=[...members];
    renderCharacterDropdowns();
    [...els.members.querySelectorAll('.member-select')].forEach((x,n)=>setMemberValue(x,selected[n]||''));
    const missing=5-members.length;
    els.templateMsg.textContent=missing>0
      ? `Loaded ${members.length} known members for ${team}. Choose ${missing} more character${missing===1?'':'s'} to complete the defense.`
      : `Loaded ${team}. Edit any slot if your defense is modified.`;
    return;
  }
  els.templateMsg.textContent=`The bundled roster for ${team} is not available yet. Run the data refresh or choose the five characters manually.`;
}
async function loadCharacters(){
  try{
    const r=await fetch('data/characters.json',{cache:'no-store'});
    const payload=await r.json();
    if(!r.ok||!Array.isArray(payload.characters)||!payload.characters.length)throw new Error('No characters returned.');
    state.characters=payload.characters.map(String);
    enrichCharactersFromRosters();
    renderCharacterDropdowns();
    els.templateMsg.textContent=`Character dropdown loaded (${state.characters.length} characters). Choose a team template or build a custom defense.`;
  }catch(e){
    renderCharacterDropdowns();
    els.templateMsg.textContent=`Could not load the bundled character directory: ${e.message}`;
  }
}
renderCharacterDropdowns();
els.warMode.onclick=()=>setMode('Alliance War');els.ccMode.onclick=()=>setMode('Cosmic Crucible');els.addBtn.onclick=()=>{const max=state.mode==='Alliance War'?14:6;if(state.roomCount>=max)return;const p=selectedValues();state.roomCount++;renderRooms(p);clearResults();};els.removeBtn.onclick=()=>{if(state.roomCount<=1)return;const p=selectedValues();state.roomCount--;renderRooms(p.slice(0,-1));clearResults();};els.clearBtn.onclick=()=>renderRooms(),els.buildBtn.onclick=buildPlan;els.defenseBtn.onclick=openDefense;$('newDefense').onclick=()=>{state.editDefense=null;clearDefenseEditor();renderSaved();};$('saveDefense').onclick=saveDefense;$('deleteDefense').onclick=deleteDefense;els.useTemplate.onclick=useTeamTemplate;els.teamTemplate.onchange=()=>{const team=els.teamTemplate.value.trim();els.templateMsg.textContent=team?`${team} selected. Click Use Team to load its five members.`:'Choose a team template or select five characters.';};
Promise.all([
  fetch('data/counter-data.json',{cache:'no-store'}).then(r=>r.json()),
  fetch('data/team-directory.json',{cache:'no-store'}).then(r=>r.json()).catch(()=>({})),
  fetch('data/team-rosters.json',{cache:'no-store'}).then(r=>r.json()).catch(()=>({teams:{}})),
  fetch('data/data-status.json',{cache:'no-store'}).then(r=>r.json()).catch(()=>null)
]).then(([data,teamDirectory,rosters,status])=>{
  state.data=data;
  state.teamDirectory=teamDirectory||{};
  state.publicRosters=(rosters&&rosters.teams)||{};
  state.dataStatus=status;
  renderTeamTemplates();
  renderHeader();
  if(status&&status.display)els.source.textContent=status.display;
  renderRooms();
  try{enrichCharactersFromRosters();}catch(e){console.warn('Character roster enrichment failed:',e);}
  loadCharacters();
}).catch(e=>{els.season.textContent='Could not load counter data';els.source.textContent=e.message;});

document.addEventListener('click',e=>{if(!e.target.closest('.character-picker'))closeCharacterMenus();});
