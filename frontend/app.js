const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label = v => String(v).replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
const money = v => 'Rs '+new Intl.NumberFormat('en-PK',{maximumFractionDigits:2}).format((v||0)/100);
const pad2 = n => String(Math.max(0, n|0)).padStart(2, '0');
const date = v => v ? new Date(v*1000).toLocaleString('en-PK',{dateStyle:'medium',timeStyle:'short'}) : '—';

const paths={
  home:'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z',
  grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  bag:'M6 7h12l-1 13H7L6 7z M9 7V5a3 3 0 0 1 6 0v2',
  cart:'M6 7h12l-1 13H7L6 7z M9 7V5a3 3 0 0 1 6 0v2',
  orders:'M6 3h12v18l-3-2-3 2-3-2-3 2z M9 7h6 M9 11h6 M9 15h3',
  menu:'M4 3v7a3 3 0 0 0 6 0V3 M7 3v18 M19 3c-4 4-4 9 0 9v9 M19 3v9',
  stock:'m3 7 9-4 9 4-9 4z M3 7v10l9 4 9-4V7 M12 11v10',
  wallet:'M3 6h17v15H3z M3 6V3h14v3 M15 12h6v5h-6z',
  users:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M18 4a4 4 0 0 1 0 7 M22 21v-2a4 4 0 0 0-3-4',
  settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2',
  search:'M21 21l-4.35-4.35 M10.5 3a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15',
  sliders:'M4 6h16 M4 12h16 M4 18h16 M8 4v4 M16 10v4 M10 16v4',
  arrow:'M4 12h16 M14 6l6 6-6 6',
  back:'M15 18l-6-6 6-6',
  heart:'M12 20.5s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 7.5 3c0 5.6-7.5 10.2-7.5 10.2z',
  plus:'M12 5v14 M5 12h14',
  check:'m5 12 4 4 10-10',
  chart:'M4 20V4 M4 20h17 M8 16v-4 M13 16V7 M18 16V3',
  logout:'M9 3H3v18h6 M9 12h12 M17 8l4 4-4 4',
  bell:'M18 8a6 6 0 0 0-12 0v6l-2 3h16l-2-3z M10 21h4',
  close:'m6 6 12 12 M18 6 6 18',
  clock:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 7v5l3 2',
  download:'M12 3v12 M7 10l5 5 5-5 M4 17v4h16v-4',
  shield:'m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6z M8 12l3 3 5-6',
  hamburger:'M4 6h16 M4 12h16 M4 18h16',
  mail:'M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z M22 6l-10 7L2 6',
  printer:'M6 9V2h12v7 M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2 M6 14h12v8H6z'
};
const icon = name => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]||paths.grid}" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const brand = () => `<div class="brand"><span class="brand-mark"><img src="/ui/techleeq-logo.png" alt="Techleeq" width="28" height="28" style="display:block;border-radius:6px;object-fit:contain;"></span><div>Tech<span class="brand-accent">leeq</span><small>RESTAURANT WORKSPACE</small></div></div>`;
const badge = s => `<span class="badge ${esc(s)}">${esc(label(s||'pending'))}</span>`;

const state={
  token:sessionStorage.getItem('firres-token'),
  user:null,
  page:'dashboard',
  cart:[],
  category:'all',
  query:'',
  sort:'popular',
  favorites:new Set(JSON.parse(localStorage.getItem('firres-favs')||'[]')),
  mode:'cash',
  notes:'',
  preview:null,
  resourceTab:null,
  images:new Map(),
  cache:{},
  requestId:0
};
let spec, refreshTimer, toastTimer;

function saveFavorites(){
  try{localStorage.setItem('firres-favs',JSON.stringify([...state.favorites]))}catch{}
}

function categoryEmoji(name='', index=0){
  const n = name.toLowerCase();
  if(n.includes('fruit')||n.includes('fresh')) return '🍓';
  if(n.includes('drink')||n.includes('beverage')||n.includes('coffee')||n.includes('tea')||n.includes('juice')) return '🥤';
  if(n.includes('dessert')||n.includes('sweet')||n.includes('cake')||n.includes('ice')) return '🍰';
  if(n.includes('sushi')||n.includes('roll')||n.includes('sea')||n.includes('fish')) return '🍣';
  if(n.includes('salad')||n.includes('veg')||n.includes('bowl')) return '🥗';
  if(n.includes('bbq')||n.includes('grill')||n.includes('tikka')||n.includes('kebab')||n.includes('steak')) return '🍖';
  if(n.includes('pizza')||n.includes('pasta')) return '🍕';
  if(n.includes('combo')||n.includes('deal')) return '🍱';
  const palette = ['🍔','🍣','🥗','🍓','🥤','🍛','🍕','🍜'];
  return palette[index % palette.length];
}

function dishEmoji(item={}){
  const n = ((item.name||'')+' '+(item.description||'')).toLowerCase();
  if(n.includes('sushi')||n.includes('roll')||n.includes('salmon')) return '🍣';
  if(n.includes('coffee')||n.includes('latte')||n.includes('espresso')||n.includes('tea')) return '☕';
  if(n.includes('drink')||n.includes('juice')||n.includes('shake')||n.includes('Mojito')) return '🥤';
  if(n.includes('salad')||n.includes('green')||n.includes('avocado')) return '🥗';
  if(n.includes('burger')||n.includes('sandwich')) return '🍔';
  if(n.includes('pizza')) return '🍕';
  if(n.includes('fruit')||n.includes('berry')) return '🍓';
  if(n.includes('cake')||n.includes('dessert')||n.includes('sweet')) return '🍰';
  if(n.includes('chicken')||n.includes('tikka')||n.includes('grill')||n.includes('bbq')||n.includes('beef')) return '🍗';
  if(n.includes('rice')||n.includes('biryani')||n.includes('curry')) return '🍛';
  const list = ['🍣','🥗','🍛','🍗','🍔','🍜','🥘','☕'];
  return list[(item.id||0) % list.length];
}

function dishPrepTime(item={}){
  const mins = 15 + ((item.id||1)*5)%15;
  return `${mins}-${mins+10} min`;
}

function dishRating(item={}){
  return (4.5 + ((item.id||2)%5)*0.1).toFixed(1);
}

function toast(message){
  $('#toast').textContent=message;
  $('#toast').classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),4500);
}

async function api(path,options={}){
  const headers={...(state.token?{Authorization:'Bearer '+state.token}:{}),...(options.headers||{})};
  if(options.body && !(options.body instanceof FormData)){
    headers['Content-Type']='application/json';
    options.body=JSON.stringify(options.body);
  }
  const r=await fetch(path,{...options,headers});
  if(r.status===401 && path!='/auth/login'){
    logout(false);
    throw Error('Your session ended. Please sign in again.');
  }
  if(!r.ok){
    let data;
    try{data=await r.json()}catch{data={detail:'Request could not be completed'}}
    const d=data.detail;
    throw Error(Array.isArray(d)?d.map(e=>`${e.loc.slice(1).join(' › ')}: ${e.msg}`).join('\n'):typeof d==='string'?d:'Request could not be completed');
  }
  if(options.raw)return r;
  return r.status===204?null:r.json();
}

async function busy(button,task){
  if(button?.disabled)return;
  if(button)button.disabled=true;
  try{return await task()}catch(e){toast(e.message);throw e}finally{if(button)button.disabled=false}
}

function empty(title,text=''){
  return `<div class="empty">${icon('menu')}<strong>${esc(title)}</strong>${esc(text)}</div>`;
}

function errorBox(error){
  return `<div class="error-box" role="alert">${esc(error.message||error)}</div>`;
}

function modal(title,body,options={}){
  const dlg=$('#modal');
  dlg.classList.toggle('spotlight-dialog',!!options.spotlight);
  if(options.raw){
    $('#modal-body').innerHTML=body;
  }else{
    $('#modal-body').innerHTML=`<div class="modal-head"><h2>${esc(title)}</h2><button class="button ghost" data-close aria-label="Close dialog">${icon('close')}</button></div><div class="modal-content">${body}</div>`;
  }
  if(!dlg.open)dlg.showModal();
  $$('[data-close]',dlg).forEach(b=>b.onclick=()=>dlg.close());
}

function heading(title,sub,actions=''){
  return `<div class="page-heading"><div><h1>${esc(title)}</h1><p>${esc(sub)}</p></div><div class="row">${actions}</div></div>`;
}

function btn(text,action,secondary=false,ico='plus'){
  return `<button class="button ${secondary?'secondary':''}" data-action="${action}">${icon(ico)}${text}</button>`;
}

function searchBox(placeholder='Search here'){
  return `<div class="search">${icon('search')}<input id="search" type="search" aria-label="${esc(placeholder)}" placeholder="${esc(placeholder)}" value="${esc(state.query)}"></div>`;
}

function moneyKey(k){
  return /(^price$|^amount$|^cost$|^value$|^total$|_price$|_cost$|_cash$|_float$|^paid$|^tax$|^discount$|^charges$|^recoverable_tax$|^minimum_subtotal$|^manual_discount$)/.test(k);
}

function format(k,v){
  if(v===null||v===undefined)return '—';
  if(typeof v==='boolean')return v?'Yes':'No';
  if(moneyKey(k)||['net','applied','change','difference','net_sales','operating_profit','gross_profit','outstanding','credited','supplier_credit'].includes(k))return money(v);
  if(['created','opened','closed','starts_at','ends_at','effective_from','approved_at'].includes(k))return date(v);
  if(typeof v==='object')return Array.isArray(v)?`${v.length} entries`:'Configured';
  return String(v);
}

function table(rows,cols,actions){
  if(!rows?.length)return empty('Nothing here yet','New records will appear here as your team gets to work.');
  return `<div class="table-wrap"><table><thead><tr>${cols.map(k=>`<th>${esc(label(k))}</th>`).join('')}${actions?'<th></th>':''}</tr></thead><tbody>${rows.map((r,index)=>`<tr>${cols.map(k=>`<td>${['status','fiscal_status','role'].includes(k)?badge(r[k]):esc(format(k,r[k]))}</td>`).join('')}${actions?`<td><div class="row">${actions(r,index)}</div></td>`:''}</tr>`).join('')}</tbody></table></div>`;
}

async function logout(remote=true){
  clearInterval(refreshTimer);
  if(remote)try{await api('/auth/logout',{method:'POST'})}catch{}
  state.token=null;
  state.user=null;
  state.cart=[];
  state.preview=null;
  state.images.forEach(URL.revokeObjectURL);
  state.images.clear();
  sessionStorage.removeItem('firres-token');
  login();
}

function login(){
  clearInterval(refreshTimer);
  $('#app').innerHTML=`<main class="login">
    <section class="login-art">
      ${brand()}
      <div class="login-copy">
        <div class="eyebrow" style="color:var(--gold)">POWERED BY TECHLEEQ</div>
        <h1>Fresh dishes.<br>Effortless <em>orders.</em></h1>
        <p>From plated favourites to instant kitchen tickets and fiscal billing — your restaurant in one tactile workspace.</p>
        <div class="login-preview-cards" aria-hidden="true">
          <div class="login-mini-card">
            <div class="login-mini-plate">🍣</div>
            <div>
              <strong style="display:block;font-size:13px">Signature Platter</strong>
              <span class="login-mini-price">⏰ 20-30 min · ★ 4.8</span>
            </div>
          </div>
          <div class="login-mini-card">
            <div class="login-mini-plate">🥗</div>
            <div>
              <strong style="display:block;font-size:13px">Live Order Queue</strong>
              <span class="login-mini-price">Instant Kitchen Sync</span>
            </div>
          </div>
        </div>
      </div>
      <div class="login-foot">DESIGNED FOR SPEED, CLARITY &amp; GREAT SERVICE.</div>
    </section>
    <section class="login-form">
      <div class="login-inner">
        <div class="eyebrow">WELCOME BACK</div>
        <h1>Sign in</h1>
        <p>Enter your workspace credentials to start service.</p>
        <form id="login-form">
          <label class="field"><span>Username</span><input name="username" autocomplete="username" placeholder="Your username" required></label>
          <label class="field"><span>Password</span><input name="password" type="password" autocomplete="current-password" placeholder="Enter your password" required></label>
          <div id="login-error"></div>
          <button class="button wide">Sign in ${icon('arrow')}</button>
        </form>
        <p class="muted" style="font-size:11.5px;line-height:1.7;margin-top:26px;text-align:center">Need an account or password reset?<br>Ask your restaurant manager.</p>
      </div>
    </section>
  </main>`;
  $('#login-form').onsubmit=async e=>{
    e.preventDefault();
    const b=$('button',e.target);
    b.disabled=true;
    $('#login-error').innerHTML='';
    try{
      const formData = new FormData(e.target);
      const payload = {
        username: (formData.get('username') || '').trim(),
        password: formData.get('password') || ''
      };
      const result=await api('/auth/login',{method:'POST',body:payload});
      state.token=result.access_token;
      sessionStorage.setItem('firres-token',state.token);
      await boot();
    }catch(err){
      $('#login-error').innerHTML=errorBox(err);
    }finally{
      b.disabled=false;
    }
  };
}

const navigation=[
  ['dashboard','Overview','home',['manager']],
  ['pos','Order Menu','bag',['manager','cashier']],
  ['orders','Orders','orders',['manager','cashier']],
  ['menu','Menu Studio','menu',['manager']],
  ['inventory','Inventory','stock',['manager','entry_clerk']],
  ['expenses','Expenses','wallet',['manager','entry_clerk']],
  ['reports','Reports','chart',['manager']],
  ['team','Team','users',['manager']],
  ['shifts','Cash Shifts','clock',['manager','cashier']],
  ['settings','Settings','settings',['manager']]
];

async function boot(){
  try{
    state.user=await api('/auth/me');
    spec=await api('/openapi.json');
    if(state.user.role.endsWith('_display'))return displayBoard();
    state.page=state.user.role==='manager'?'dashboard':state.user.role==='cashier'?'pos':'inventory';
    shell();
    await navigate(state.page);
  }catch(e){
    if(!state.user)login();
    toast(e.message);
  }
}

function updateDockBadge(){
  const count = state.cart.reduce((a,l)=>a+l.quantity,0);
  const b = $('#dock-bag-count');
  if(b){
    b.textContent = count;
    b.style.display = count > 0 ? 'grid' : 'none';
  }
}

function shell(){
  const nav=navigation.filter(n=>n[3].includes(state.user.role));
  const initials = esc(state.user.username.slice(0,2).toUpperCase());
  const canPos = ['manager','cashier'].includes(state.user.role);
  $('#app').innerHTML=`<div class="shell">
    <aside class="sidebar">
      ${brand()}
      <div class="nav-caption">WORKSPACE</div>
      <nav class="nav">${nav.map(([id,name,ico])=>`<button data-nav="${id}">${icon(ico)}${name}</button>`).join('')}</nav>
      <div class="sidebar-bottom">
        <div class="profile">
          <span class="avatar">${initials}</span>
          <div style="flex:1;min-width:0">
            <h3 style="overflow:hidden;text-overflow:ellipsis">${esc(state.user.username)}</h3>
            <small>${esc(label(state.user.role))}</small>
          </div>
          <button class="button ghost" id="logout" aria-label="Sign out">${icon('logout')}</button>
        </div>
      </div>
    </aside>
    <main class="workspace">
      <header class="topbar">
        <div class="row">
          <button class="button ghost mobile-menu" id="mobile-menu" aria-label="Open navigation">${icon('hamburger')}</button>
          <span class="crumb">Techleeq <span style="padding:0 8px">/</span> <strong id="breadcrumb">Overview</strong></span>
        </div>
        <div class="top-actions">
          <a href="mailto:info@techleeq.com" class="top-contact" title="Support: info@techleeq.com">${icon('mail')}<span>info@techleeq.com</span></a>
          <span class="date">${new Date().toLocaleDateString('en-PK',{weekday:'short',day:'numeric',month:'short',year:'numeric'})}</span>
          <span class="live">Live service</span>
          ${state.user.role==='manager'?`<button class="button ghost" id="notifications" aria-label="Low stock notifications">${icon('bell')}</button>`:''}
          <span class="top-avatar" title="${esc(state.user.username)} (${esc(label(state.user.role))})">${initials}</span>
        </div>
      </header>
      <div class="content" id="content"></div>
      <nav class="bottom-dock" aria-label="Quick navigation">
        <button data-dock="${state.user.role==='manager'?'dashboard':nav[0][0]}" aria-label="Home">${icon('home')}</button>
        <button data-dock="${state.user.role==='manager'?'menu':canPos?'pos':nav[0][0]}" aria-label="Categories">${icon('grid')}</button>
        ${canPos?`<button class="dock-center-bag" data-dock="pos" aria-label="Order bag">${icon('bag')}<span class="dock-badge" id="dock-bag-count" style="display:none">0</span></button>`:''}
        <button data-dock="${canPos?'orders':nav[0][0]}" aria-label="Orders">${icon('heart')}</button>
        <button id="dock-bell" aria-label="Alerts">${icon('bell')}</button>
      </nav>
    </main>
  </div>`;
  $$('[data-nav]').forEach(b=>b.onclick=()=>navigate(b.dataset.nav));
  $$('[data-dock]').forEach(b=>b.onclick=()=>navigate(b.dataset.dock));
  $('#dock-bell').onclick=()=>state.user.role==='manager'?notifications():navigate(canPos?'orders':nav[0][0]);
  $('#logout').onclick=()=>logout();
  $('#mobile-menu').onclick=()=>$('.sidebar').classList.toggle('open');
  if($('#notifications'))$('#notifications').onclick=notifications;
  updateDockBadge();
}

async function navigate(page){
  clearInterval(refreshTimer);
  state.page=page;
  state.query='';
  state.category='all';
  state.resourceTab=null;
  $('.sidebar')?.classList.remove('open');
  $$('[data-nav]').forEach(b=>b.classList.toggle('active',b.dataset.nav===page));
  $$('[data-dock]').forEach(b=>b.classList.toggle('active',b.dataset.dock===page));
  $('#breadcrumb').textContent=navigation.find(n=>n[0]===page)?.[1]||label(page);
  $('#content').innerHTML='<div class="loading">Getting your workspace ready…</div>';
  const id=++state.requestId;
  try{
    if(page==='dashboard')await dashboard(id);
    else if(page==='pos'||page==='menu')await menuPage();
    else if(page==='orders')await ordersPage();
    else await resourcePage(page);
  }catch(e){
    if(id===state.requestId)$('#content').innerHTML=errorBox(e)+btn('Try again','retry',true,'arrow');
    $('[data-action=retry]')?.addEventListener('click',()=>navigate(page));
  }
}

async function dashboard(id){
  const [report,orders,ops]=await Promise.all([api('/reports/period?period=today'),api('/orders'),api('/reports/operations')]);
  if(id!==state.requestId)return;
  const r=report.report||report;
  state.cache.orders=orders;
  const stats=[
    ['Net sales',r.net_sales,'wallet','After discounts & refunds'],
    ['Orders served',r.orders,'orders','Recognized in today’s service'],
    ['Operating profit',r.operating_profit,'chart','Sales less costs & expenses'],
    ['Expenses',r.expenses,'stock','Recorded for this period']
  ];
  const trends=ops.daily_net_sales||ops.daily_sales_trend||ops.daily_trends||ops.sales_trend||ops.daily_sales||[];
  const data=Array.isArray(trends)?trends:Object.entries(trends).map(([day,v])=>({date:day,...(typeof v==='object'?v:{net_sales:v})}));
  const recent=data.slice(-7);
  const max=Math.max(1,...recent.map(x=>x.net_sales||x.sales||0));
  $('#content').innerHTML=heading('A fresh day. A clear picture.','Here’s what’s happening across your counter and kitchen today.',btn('New order','new-order',false,'plus'))+`
    <section class="hero">
      <div>
        <div class="eyebrow">DAILY SERVICE AT A GLANCE</div>
        <h2>Great food starts with a smooth flow.</h2>
        <p>Keep the kitchen moving and every guest order right on time.</p>
      </div>
      <button class="button" data-action="orders">View live orders ${icon('arrow')}</button>
    </section>
    <div class="stats">${stats.map(([title,value,ico,note])=>`<section class="stat"><div class="stat-title">${title}<span class="stat-icon">${icon(ico)}</span></div><div class="stat-value">${title==='Orders served'?(value||0):money(value)}</div><small>${note}</small></section>`).join('')}</div>
    ${r.costs_complete===false?'<div class="notice warn"><span style="font-size:16px;flex-shrink:0">💡</span><span><strong>Provisional profit:</strong> Some items have incomplete ingredient costs. Profit is provisional until recipes and stock costs are recorded.</span></div>':''}
    <div class="grid-two">
      <section class="panel">
        <div class="panel-head"><div><h2>Sales rhythm</h2><small>Net sales across recorded trading days</small></div>${badge('all_time')}</div>
        ${recent.length?`<div class="chart">${recent.map(x=>`<div class="bar-group"><div class="bar" style="height:${Math.max(4,(x.net_sales||x.sales||0)/max*100)}%" title="${esc(money(x.net_sales||x.sales))}"></div><small>${esc(x.date||x.day)}</small></div>`).join('')}</div>`:empty('Your story starts with the first sale','Daily sales will build this view automatically.')}
      </section>
      <section class="panel">
        <div class="panel-head"><div><h2>Guests’ favourites</h2><small>Today’s most-ordered dishes</small></div>${icon('menu')}</div>
        ${(r.best_selling||[]).slice(0,4).map((item,i)=>`<div class="rank"><span class="rank-index">0${i+1}</span><div class="rank-info"><div class="row between"><h3>${esc(item.name)}</h3><small>${item.quantity} sold</small></div><div class="rank-track"><i style="width:${Math.min(100,item.quantity/Math.max(1,r.best_selling[0].quantity)*100)}%"></i></div></div></div>`).join('')||empty('Favourites are on their way','Confirmed sales will appear here.')}
      </section>
    </div>
    <section class="panel section-space">
      <div class="panel-head"><div><h2>Latest orders</h2><small>Live counter &amp; kitchen queue</small></div><button class="text-button" data-action="orders">View all orders →</button></div>
      ${table(orders.slice(-5).reverse(),['code','created_by','created','total','status'],o=>`<button class="button ghost small" data-order="${o.id}">View ${icon('arrow')}</button>`)}
    </section>`;
  $('[data-action=new-order]').onclick=()=>navigate('pos');
  $$('[data-action=orders]').forEach(b=>b.onclick=()=>navigate('orders'));
  bindOrderDetails();
}

async function imageSource(url){
  if(!url)return '';
  if(!url.startsWith('/menu/images/'))return /^https?:\/\//i.test(url)?url:'';
  if(state.images.has(url))return state.images.get(url);
  const r=await api(url,{raw:true});
  const src=URL.createObjectURL(await r.blob());
  state.images.set(url,src);
  return src;
}

async function hydrateImages(){
  await Promise.allSettled($$('img[data-image]').map(async img=>{
    const src=await imageSource(img.dataset.image);
    if(src)img.src=src;
    else img.remove();
    img.onerror=()=>img.remove();
  }));
}

function foodImage(item, showChip=false){
  const emoji = dishEmoji(item);
  return `<div class="food-image">
    ${item.image_url?`<img data-image="${esc(item.image_url)}" alt="${esc(item.name)}">`:`<div class="food-plate-art"><span class="food-plate-emoji" aria-hidden="true">${emoji}</span></div>`}
    ${showChip?`<span class="food-price-chip">${money(item.price)}</span>`:''}
  </div>`;
}

function isScheduledNow(row){
  const now = Date.now()/1000;
  return row.active!==false && (row.starts_at||0)<=now && (!row.ends_at || now<row.ends_at);
}

function comboSummary(combo, items=[]){
  if(!combo?.components?.length) return 'House combo';
  return combo.components.map(c=>{
    const dish = items.find(i=>i.id===c.item_id);
    return `${c.quantity} × ${dish?.name||('Item #'+c.item_id)}`;
  }).join(' · ');
}

function enrichCombo(combo, items=[]){
  const firstDish = items.find(i=>i.id===combo.components?.[0]?.item_id && i.image_url);
  return {
    ...combo,
    image_url: combo.image_url || firstDish?.image_url || null,
    description: combo.description || comboSummary(combo, items)
  };
}

async function menuPage(){
  const isManager=state.page==='menu';
  const [items,allCategories,allCombos,allPromos]=await Promise.all([
    api(isManager?'/management/menu/items':'/menu/items'),
    api('/menu/categories'),
    api('/menu/combos'),
    api('/menu/promotions').catch(()=>[])
  ]);
  const categories = isManager ? allCategories : allCategories.filter(c=>c.active!==false);
  const rawCombos = isManager
    ? allCombos
    : allCombos.filter(c=>isScheduledNow(c) && (c.components||[]).every(comp=>items.some(i=>i.id===comp.item_id && i.active!==false && i.available!==false)));
  const combos = rawCombos.map(c=>enrichCombo(c, items));
  const activePromos = (allPromos||[]).filter(isScheduledNow);

  state.cache.items=items;
  state.cache.categories=categories;
  state.cache.combos=combos;
  state.cache.promotions=activePromos;

  const headerActions = isManager
    ? btn('Preview POS','preview-pos',true,'bag')+btn('Add category','category',true)+btn('Add dish','add-item')
    : (state.user.role==='manager'?btn('Design menu','design-menu',true,'menu'):'')+btn('Live orders','orders',true,'orders');

  $('#content').innerHTML=heading(
    isManager?'Crafted for your menu.':'Order & Menu',
    isManager?'Design categories, dishes, photographs, combos and promotions that appear immediately on the cashier’s Order Menu.':'Select dishes and combos from the menu designed by your manager to build and confirm guest orders.',
    headerActions
  )+`<div class="${isManager?'':'pos-layout'}">
    <section>
      <div class="toolbar">
        <div class="search-bar-row">
          ${searchBox('Search here')}
          <button type="button" class="filter-square-btn" id="cycle-sort-btn" title="Change sort order" aria-label="Filter and sort dishes">${icon('sliders')}</button>
        </div>
        ${isManager?btn('Combos & offers','offers',true,'menu'):`<button type="button" class="button secondary small" id="reload-menu" title="Sync latest menu from manager">${icon('clock')}Sync menu</button>`}
      </div>
      ${!isManager && activePromos.length ? `<div class="promo-strip" aria-label="Active promotions">${activePromos.map(p=>`<span class="promo-pill"><strong>OFFER</strong>${esc(p.name)} · ${p.kind==='percent'?(p.value/100)+'% off':money(p.value)+' off'}${p.minimum_subtotal?' (Min '+money(p.minimum_subtotal)+')':''}</span>`).join('')}</div>` : ''}
      <div class="tabs" id="categories">
        <button class="active" data-category="all"><span class="cat-emoji">🍽️</span>Food <small>(${items.length})</small></button>
        ${categories.map((c,idx)=>`<button data-category="${c.id}"><span class="cat-emoji">${categoryEmoji(c.name,idx)}</span>${esc(c.name)}${c.active===false?' (Hidden)':''}</button>`).join('')}
        ${combos.length?`<button data-category="combos"><span class="cat-emoji">🍱</span>Combos <small>(${combos.length})</small></button>`:''}
        ${state.favorites.size?`<button data-category="favorites"><span class="cat-emoji">❤️</span>Favourites</button>`:''}
      </div>
      <div class="category-section-head">
        <h2 id="active-category-heading">Category</h2>
        <select id="sort-select" class="sort-pill-select" aria-label="Sort dishes">
          <option value="popular" ${state.sort==='popular'?'selected':''}>Most Popular ▾</option>
          <option value="price_asc" ${state.sort==='price_asc'?'selected':''}>Price: Low to High ▾</option>
          <option value="price_desc" ${state.sort==='price_desc'?'selected':''}>Price: High to Low ▾</option>
          <option value="name" ${state.sort==='name'?'selected':''}>Name: A–Z ▾</option>
        </select>
      </div>
      <div class="menu-grid" id="menu-grid"></div>
    </section>
    ${isManager?'':'<aside class="panel cart" id="cart"></aside>'}
  </div>`;

  $('#search').oninput=e=>{state.query=e.target.value;renderMenu()};
  $('#sort-select').onchange=e=>{state.sort=e.target.value;renderMenu()};
  $('#cycle-sort-btn').onclick=()=>{
    const order=['popular','price_asc','price_desc','name'];
    state.sort=order[(order.indexOf(state.sort)+1)%order.length];
    $('#sort-select').value=state.sort;
    renderMenu();
  };
  $$('[data-category]').forEach(b=>b.onclick=()=>{
    state.category=b.dataset.category;
    $$('[data-category]').forEach(x=>x.classList.toggle('active',x===b));
    const catObj = state.cache.categories.find(c=>String(c.id)===state.category);
    $('#active-category-heading').textContent = state.category==='all'?'Category':state.category==='combos'?'House Combos':state.category==='favorites'?'Favourite Dishes':catObj?.name||'Category';
    renderMenu();
  });
  if(isManager){
    $('[data-action=preview-pos]').onclick=()=>navigate('pos');
    $('[data-action=add-item]').onclick=()=>itemForm();
    $('[data-action=category]').onclick=()=>operation('/menu/categories','post',{},()=>menuPage(),'New category');
    $('[data-action=offers]').onclick=()=>resourcePage('offers');
  }else{
    if($('[data-action=design-menu]'))$('[data-action=design-menu]').onclick=()=>navigate('menu');
    if($('#reload-menu'))$('#reload-menu').onclick=()=>menuPage();
    $('[data-action=orders]').onclick=()=>navigate('orders');
    renderCart();
  }
  renderMenu();
}

function addToCart(item, isCombo=false, qty=1, notes=''){
  const key=(isCombo?'combo:':'item:')+item.id;
  const line=state.cart.find(l=>l.key===key);
  if(line){
    line.quantity+=qty;
    if(notes && !line.notes) line.notes=notes;
  }else{
    state.cart.push({
      key,
      id:item.id,
      combo:isCombo,
      name:item.name,
      price:item.price,
      image_url:item.image_url,
      quantity:qty,
      notes:notes||''
    });
  }
  state.preview=null;
  updateDockBadge();
  renderCart();
  previewCart();
}

function openDishSpotlight(item, isCombo=false){
  const isManager=state.page==='menu';
  const favKey=(isCombo?'combo:':'item:')+item.id;
  let qty=1;
  const catName=isCombo?'House Combo':(state.cache.categories?.find(c=>c.id===item.category_id)?.name||'Signature Dish');
  const desc=item.description||`Freshly prepared ${item.name.toLowerCase()} crafted to order with signature house ingredients and balanced flavours.`;
  const emoji=dishEmoji(item);

  modal(item.name, `<div class="dish-spotlight">
    <div class="spotlight-stage">
      <div class="spotlight-top-nav">
        <button type="button" class="circle-icon-btn" data-close aria-label="Back">${icon('back')}</button>
        <span class="badge">${esc(catName)}</span>
      </div>
      <div class="spotlight-plate-wrap">
        ${item.image_url?`<img data-image="${esc(item.image_url)}" alt="${esc(item.name)}">`:`<div class="food-plate-art"><span class="food-plate-emoji" aria-hidden="true">${emoji}</span></div>`}
      </div>
    </div>
    <div class="spotlight-sheet">
      <div class="spotlight-price-pill">${money(item.price)}</div>
      <div class="food-accent-bar"></div>
      <h2>${esc(item.name)}</h2>
      <p class="spotlight-desc">${esc(desc)}</p>
      <div class="spotlight-time-badge">⏰ Time: ${dishPrepTime(item)}</div>
      ${isManager?`
        <div class="row" style="justify-content:center;gap:10px;margin-top:8px">
          <button type="button" class="button secondary" id="spot-photo">${icon('menu')}Photograph</button>
          <button type="button" class="button" id="spot-edit">Edit Dish</button>
        </div>
      `:`
        <div class="spotlight-controls-row">
          <div class="quantity" style="padding:6px 8px;border-radius:14px;background:var(--surface);box-shadow:var(--shadow-sm)">
            <button type="button" id="spot-minus" aria-label="Decrease quantity">−</button>
            <span id="spot-qty" style="min-width:30px;font-size:13.5px">${pad2(qty)}</span>
            <button type="button" class="qty-plus" id="spot-plus" aria-label="Increase quantity">+</button>
          </div>
          <div class="spotlight-meta-pills">
            <button type="button" class="meta-pill ${state.favorites.has(favKey)?'liked':''}" id="spot-fav" aria-label="Favourite">♥</button>
            <span class="meta-pill"><span style="color:#f5b400">★</span> ${dishRating(item)}</span>
          </div>
        </div>
        <input id="spot-note" class="cart-note" style="background:var(--surface);margin-bottom:16px" placeholder="Add special kitchen instructions…">
        <button type="button" class="button wide" id="spot-add" ${item.active===false||item.available===false?'disabled':''}>
          Add To Cart ${icon('bag')}
        </button>
      `}
    </div>
  </div>`, {raw:true, spotlight:true});

  hydrateImages();

  if(isManager){
    $('#spot-edit').onclick=()=>{
      $('#modal').close();
      isCombo
        ? operation('/menu/combos/{ident}','put',item,()=>menuPage(),'Edit combo')
        : itemForm(item);
    };
    $('#spot-photo').onclick=()=>{
      $('#modal').close();
      photoDialog(item);
    };
  }else{
    $('#spot-minus').onclick=()=>{if(qty>1){qty--;$('#spot-qty').textContent=pad2(qty)}};
    $('#spot-plus').onclick=()=>{qty++;$('#spot-qty').textContent=pad2(qty)};
    $('#spot-fav').onclick=e=>{
      if(state.favorites.has(favKey))state.favorites.delete(favKey);
      else state.favorites.add(favKey);
      saveFavorites();
      e.currentTarget.classList.toggle('liked',state.favorites.has(favKey));
    };
    $('#spot-add').onclick=()=>{
      const note = $('#spot-note')?.value?.trim()||'';
      addToCart(item, isCombo, qty, note);
      $('#modal').close();
      toast(`${qty} × ${item.name} added to order`);
    };
  }
}

function renderMenu(){
  const isManager=state.page==='menu';
  const combos=state.category==='combos';
  const favOnly=state.category==='favorites';
  const source=combos?state.cache.combos:state.cache.items;
  let items=source.filter(x=>{
    const favKey=(combos?'combo:':'item:')+x.id;
    const catMatch = state.category==='all' || combos || (favOnly ? state.favorites.has(favKey) : String(x.category_id)===state.category);
    return catMatch && x.name.toLowerCase().includes(state.query.toLowerCase());
  });
  if(state.sort==='price_asc') items=[...items].sort((a,b)=>(a.price||0)-(b.price||0));
  else if(state.sort==='price_desc') items=[...items].sort((a,b)=>(b.price||0)-(a.price||0));
  else if(state.sort==='name') items=[...items].sort((a,b)=>String(a.name).localeCompare(String(b.name)));

  $('#menu-grid').innerHTML=items.map(item=>`
    <article class="food-card" data-spotlight="${item.id}" data-combo="${combos}">
      ${foodImage(item, true)}
      <div class="food-accent-bar"></div>
      <div class="food-body">
        <h3>${esc(item.name)}</h3>
        <p>${esc(item.description||state.cache.categories.find(c=>c.id===item.category_id)?.name||'House specialty')}</p>
        <div class="food-bottom">
          <span class="food-price">${money(item.price)}</span>
          ${isManager
            ? `<button class="button secondary small" data-edit="${item.id}" data-combo="${combos}">Edit</button>`
            : `<button class="add-button" data-add="${item.id}" data-combo="${combos}" aria-label="Add ${esc(item.name)}">+</button>`
          }
        </div>
        ${item.active===false||item.available===false?'<div style="margin-top:9px">'+badge('unavailable')+'</div>':''}
      </div>
    </article>`).join('')||`<div style="grid-column:1/-1">${empty('No dishes found',isManager?'Add your first dish and upload a photograph.':'Try another category or search.')}</div>`;

  $$('[data-spotlight]').forEach(card=>card.onclick=e=>{
    if(e.target.closest('[data-add],[data-edit]'))return;
    const isCombo=card.dataset.combo==='true';
    const item=(isCombo?state.cache.combos:state.cache.items).find(x=>x.id===+card.dataset.spotlight);
    if(item)openDishSpotlight(item,isCombo);
  });

  $$('[data-add]').forEach(b=>b.onclick=e=>{
    e.stopPropagation();
    const combo=b.dataset.combo==='true';
    const item=(combo?state.cache.combos:state.cache.items).find(x=>x.id===+b.dataset.add);
    addToCart(item, combo, 1);
  });

  $$('[data-edit]').forEach(b=>b.onclick=e=>{
    e.stopPropagation();
    b.dataset.combo==='true'
      ? operation('/menu/combos/{ident}','put',state.cache.combos.find(x=>x.id===+b.dataset.edit),()=>menuPage(),'Edit combo')
      : itemForm(state.cache.items.find(x=>x.id===+b.dataset.edit));
  });

  hydrateImages();
}

function basket(){
  return {
    lines:state.cart.map(l=>({[l.combo?'combo_id':'item_id']:l.id,quantity:l.quantity,notes:l.notes})),
    payment_mode:state.mode,
    notes:state.notes
  };
}

let previewSequence=0;
async function previewCart(){
  const sequence=++previewSequence;
  if(!state.cart.length){
    state.preview=null;
    return renderCart();
  }
  try{
    const p=await api('/orders/preview',{method:'POST',body:basket()});
    if(sequence!==previewSequence)return;
    state.preview=p;
    state.previewError=null;
  }catch(e){
    if(sequence!==previewSequence)return;
    state.preview=null;
    state.previewError=e.message;
  }
  if($('#cart'))renderCart();
}

function renderCart(){
  updateDockBadge();
  const target=$('#cart');
  if(!target)return;
  const p=state.preview;
  const totalCount=state.cart.reduce((a,l)=>a+l.quantity,0);

  target.innerHTML=`
    <div class="cart-header-top">
      <button type="button" class="circle-icon-btn" id="cart-orders-shortcut" title="View active orders" aria-label="View active orders">${icon('back')}</button>
      ${state.cart.length?`<button type="button" class="text-button" id="clear-cart">Clear all</button>`:`<span class="badge">${totalCount} items</span>`}
    </div>
    <div class="cart-title-row">
      <h2>My order</h2>
      <small>${totalCount} ${totalCount===1?'item':'items'} · Counter</small>
    </div>
    <div class="cart-list">
      ${state.cart.map((l,i)=>{
        const refItem = (l.combo?state.cache.combos:state.cache.items)?.find(x=>x.id===l.id) || l;
        const unitPrice = refItem?.price ?? l.price ?? 0;
        const imgUrl = refItem?.image_url ?? l.image_url;
        return `<div class="cart-line">
          <div class="cart-line-main">
            <div class="cart-thumb">
              ${imgUrl?`<img data-image="${esc(imgUrl)}" alt="${esc(l.name)}">`:`<span class="cart-thumb-emoji">${dishEmoji(refItem)}</span>`}
            </div>
            <div class="cart-item-info">
              <h3>${esc(l.name)}</h3>
              <span class="cart-item-price">${money(unitPrice)}</span>
            </div>
            <div class="quantity">
              <button data-qty="${i}" data-delta="-1" aria-label="Remove one ${esc(l.name)}">−</button>
              <span>${pad2(l.quantity)}</span>
              <button class="qty-plus" data-qty="${i}" data-delta="1" aria-label="Add one ${esc(l.name)}">+</button>
            </div>
          </div>
          <input class="cart-note" data-note="${i}" value="${esc(l.notes)}" placeholder="Special instructions…" aria-label="Instructions for ${esc(l.name)}">
        </div>`;
      }).join('')||empty('Your order bag is empty','Tap any dish card or + button to add items.')}
    </div>
    <label class="field">
      <span>Payment method</span>
      <select id="payment-mode">
        ${['cash','card','mixed'].map(m=>`<option value="${m}" ${state.mode===m?'selected':''}>${m==='mixed'?'Split cash / card':label(m)}</option>`).join('')}
      </select>
    </label>
    <div class="totals">
      <div><span>Subtotal</span><span>${p?money(p.subtotal??p.net+p.discount):'—'}</span></div>
      <div><span>Discount</span><span>${p?(p.discount?'-'+money(p.discount):money(0)):'—'}</span></div>
      <div><span>Tax</span><span>${p?money(p.tax):'—'}</span></div>
      <div class="grand-total"><span>Total</span><span>${p?money(p.total):'—'}</span></div>
    </div>
    ${state.previewError&&state.cart.length?errorBox(state.previewError):''}
    <button class="button wide" id="confirm-order" ${!p||!state.cart.length?'disabled':''}>Confirm Order</button>
    <small style="display:block;text-align:center;margin-top:10px">Payment is recorded right after confirmation.</small>`;

  hydrateImages();

  $('#cart-orders-shortcut').onclick=()=>navigate('orders');
  if($('#clear-cart'))$('#clear-cart').onclick=()=>{
    state.cart=[];
    state.preview=null;
    state.previewError=null;
    renderCart();
  };
  $$('[data-qty]').forEach(b=>b.onclick=()=>{
    const i=+b.dataset.qty;
    state.cart[i].quantity+=+b.dataset.delta;
    if(state.cart[i].quantity<=0)state.cart.splice(i,1);
    state.preview=null;
    renderCart();
    previewCart();
  });
  $$('[data-note]').forEach(input=>input.oninput=()=>state.cart[+input.dataset.note].notes=input.value);
  $('#payment-mode').onchange=e=>{
    state.mode=e.target.value;
    state.preview=null;
    previewCart();
  };
  $('#confirm-order').onclick=async e=>{
    await busy(e.currentTarget,async()=>{
      const order=await api('/orders',{method:'POST',body:basket()});
      state.cart=[];
      state.preview=null;
      state.previewError=null;
      renderCart();
      toast('Order '+order.code+' confirmed');
      await orderDetail(order.id);
    }).catch(()=>{});
  };
}

async function itemForm(item){
  await operation(item?'/menu/items/{ident}':'/menu/items',item?'put':'post',item||{},async saved=>{await menuPage();await photoDialog(saved)},item?'Edit dish':'Add a dish',{exclude:['image_url']});
  if(item){
    const tools=document.createElement('div');
    tools.className='photo-tools';
    tools.innerHTML=`<button type="button" class="button secondary small" id="manage-photo">${icon('menu')}Manage photograph</button><small>Upload, replace or remove this dish’s picture.</small>`;
    $('.modal-content').prepend(tools);
    $('#manage-photo').onclick=()=>photoDialog(item);
  }
}

async function photoDialog(item){
  modal('A picture worth ordering',`<p class="muted" style="font-size:13px;margin-bottom:18px">${esc(item.name)} · JPEG, PNG or WebP · up to 5 MB</p><div id="photo-preview">${foodImage(item)}</div><form id="photo-form"><label class="field" style="margin-top:20px"><span>Choose a photograph</span><input type="file" name="file" accept="image/jpeg,image/png,image/webp" required></label><div id="photo-error"></div><div class="modal-footer">${item.image_url?'<button type="button" class="button danger" id="remove-photo">Remove photo</button>':''}<button class="button">Save photograph</button></div></form>`);
  hydrateImages();
  $('#photo-form').onsubmit=async e=>{
    e.preventDefault();
    try{
      await busy($('button[type!=button]',e.target)||$('button:last-child',e.target),async()=>{
        await api(`/menu/items/${item.id}/image`,{method:'POST',body:new FormData(e.target)});
        $('#modal').close();
        toast('Photograph saved');
        await menuPage();
      });
    }catch(err){
      $('#photo-error').innerHTML=errorBox(err);
    }
  };
  if($('#remove-photo'))$('#remove-photo').onclick=async e=>{
    await busy(e.currentTarget,async()=>{
      await api(`/menu/items/${item.id}/image`,{method:'DELETE'});
      $('#modal').close();
      await menuPage();
      toast('Photograph removed');
    }).catch(()=>{});
  };
}

async function ordersPage(){
  const orders=await api('/orders');
  orders.sort((a,b)=>(b.created||0)-(a.created||0) || (b.id||0)-(a.id||0));
  state.cache.orders=orders;
  $('#content').innerHTML=heading('Every order, in its place.','First in, first served. From the counter to the kitchen.',btn('New order','new-order'))+`
    <div class="toolbar">
      ${searchBox('Search order code…')}
      <select id="status-filter" style="width:170px">
        <option value="">All statuses</option>
        ${['queued','preparing','ready','collected','cancelled'].map(s=>`<option value="${s}">${label(s)}</option>`).join('')}
      </select>
      <button class="button secondary" id="refresh-orders">${icon('clock')}Refresh</button>
    </div>
    <section class="panel" id="order-table"></section>`;
  const render=()=>{
    const sorted=[...orders].sort((a,b)=>(b.created||0)-(a.created||0) || (b.id||0)-(a.id||0));
    $('#order-table').innerHTML=table(
      sorted.filter(o=>(o.code.toLowerCase().includes(state.query.toLowerCase())||(o.created_by||'').toLowerCase().includes(state.query.toLowerCase()))&&(!$('#status-filter').value||o.status===$('#status-filter').value)),
      ['code','created_by','created','total','paid','status','fiscal_status'],
      o=>`<button class="button secondary small" data-order="${o.id}">Open ${icon('arrow')}</button>`
    );
    bindOrderDetails();
  };
  $('#search').oninput=e=>{state.query=e.target.value;render()};
  $('#status-filter').onchange=render;
  $('#refresh-orders').onclick=()=>ordersPage();
  $('[data-action=new-order]').onclick=()=>navigate('pos');
  render();
  refreshTimer=setInterval(async()=>{
    if($('#modal').open)return;
    try{
      const next=await api('/orders');
      next.sort((a,b)=>(b.created||0)-(a.created||0) || (b.id||0)-(a.id||0));
      orders.splice(0,orders.length,...next);
      render();
    }catch{}
  },10000);
}

function bindOrderDetails(){
  $$('[data-order]').forEach(b=>b.onclick=()=>orderDetail(+b.dataset.order));
}

async function printOrderReceipt(id){
  try{
    const response=await api(`/orders/${id}/receipt`,{raw:true});
    const html=await response.text();
    let iframe=document.getElementById('receipt-print-frame');
    if(!iframe){
      iframe=document.createElement('iframe');
      iframe.id='receipt-print-frame';
      iframe.style.position='fixed';
      iframe.style.right='0';
      iframe.style.bottom='0';
      iframe.style.width='0';
      iframe.style.height='0';
      iframe.style.border='0';
      iframe.style.visibility='hidden';
      document.body.appendChild(iframe);
    }
    const doc=iframe.contentWindow.document;
    doc.open();
    doc.write(html);
    doc.close();
    iframe.contentWindow.focus();
    setTimeout(()=>{
      try{
        iframe.contentWindow.print();
      }catch{
        const popup=window.open('about:blank','_blank');
        if(popup){popup.opener=null;popup.document.write(html);popup.document.close()}
      }
    },250);
  }catch(e){
    toast(e.message||'Failed to load receipt');
  }
}

async function orderDetail(id){
  try{
    const [o,p]=await Promise.all([api(`/orders/${id}`),api(`/orders/${id}/payments`)]);
    const manager=state.user.role==='manager';
    const next={queued:'preparing',preparing:'ready',ready:'collected'}[o.status];
    const payments=p.payments||[];
    modal('Order '+o.code,`
      <div class="detail-grid">
        <div><small>Order status</small><p>${badge(o.status)}</p></div>
        <div><small>Payment</small><p>${badge(p.status||p.payment_status)}</p></div>
        <div><small>Fiscal invoice</small><p>${badge(o.fiscal_status)}</p></div>
        <div><small>Created by</small><p>${esc(o.created_by||'—')}</p></div>
      </div>
      ${o.fiscal_reference?`<div class="notice" style="background:var(--emerald-soft);color:var(--emerald)"><strong>${o.authority==='FBR'?'FBR Invoice #':'Fiscal Reference'}:</strong> ${esc(o.fiscal_reference)}</div>`:''}
      ${o.fiscal_error?`<div class="error-box">${esc(o.fiscal_error)}</div>`:''}
      ${table(o.lines,['name','quantity','net','tax','total'])}
      <div class="totals">
        <div><span>Discount</span><span>${money(o.discount)}</span></div>
        <div class="grand-total"><span>Total</span><span>${money(o.total)}</span></div>
        <div><span>Balance due</span><span>${money(p.outstanding)}</span></div>
      </div>
      ${o.notes?`<p class="notice">${esc(o.notes)}</p>`:''}
      <div class="detail-actions">
        ${p.outstanding>0&&o.status!=='cancelled'?btn('Take payment','pay',false,'wallet'):''}
        ${next?btn('Mark '+label(next),'next',false,'check'):''}
        ${btn('Print Receipt','receipt',true,'printer')}
        ${manager&&o.status!=='cancelled'?btn('Cancel order','cancel',true,'close'):''}
        ${manager&&payments.length?btn('Refund','refund',true,'wallet'):''}
        ${manager?btn('Revise order','revision',true,'orders')+btn('Returned items','returned-items',true,'stock')+btn('Submit invoice','submit',true,'shield'):''}
      </div>
      ${payments.length?`<div class="section-space"><h3>Payments</h3>${table(payments,['id','method','applied','change','created'])}</div>`:''}`);
    const doOp=(path,method='post',initial={},title)=>operation(path,method,{id,...initial},()=>orderDetail(id),title);
    $('[data-action=pay]')?.addEventListener('click',()=>doOp('/orders/{ident}/payments','post',{amount:p.outstanding,method:o.payment_mode==='card'?'card':'cash'},'Record payment'));
    $('[data-action=next]')?.addEventListener('click',async e=>{
      await busy(e.currentTarget,async()=>{
        await api(`/orders/${id}/status`,{method:'POST',body:{status:next}});
        toast('Order marked '+next);
        await orderDetail(id);
      }).catch(()=>{if(manager)doOp('/orders/{ident}/status','post',{status:next},'Authorize status change')});
    });
    $('[data-action=receipt]').onclick=async()=>{
      await printOrderReceipt(id);
    };
    $('[data-action=cancel]')?.addEventListener('click',()=>doOp('/orders/{ident}/cancel','post',{},'Cancel & reconcile order'));
    $('[data-action=refund]')?.addEventListener('click',()=>doOp('/orders/{ident}/refunds','post',{payment_id:payments[0]?.id},'Refund payment'));
    $('[data-action=revision]')?.addEventListener('click',()=>doOp('/orders/{ident}/revision','post',{},'Revise & replace order'));
    $('[data-action=returned-items]')?.addEventListener('click',()=>doOp('/orders/{ident}/returned-items','post',{},'Record returned quantities'));
    $('[data-action=submit]')?.addEventListener('click',async e=>{
      await busy(e.currentTarget,async()=>{
        const result=await api(`/fiscal/orders/${id}/submit`,{method:'POST'});
        toast('Fiscal status: '+result.status);
        await orderDetail(id);
      }).catch(()=>{});
    });
  }catch(e){toast(e.message)}
}

const groups={
  inventory:{title:'A well-stocked kitchen.',sub:'Everything you need, right when you need it.',tabs:[['Stock items','/inventory/items',['code','name','unit','quantity','value','threshold']],['Purchases','/inventory/invoices',['id','supplier_id','invoice_reference','total','paid','outstanding']],['Suppliers','/suppliers',['name','phone','active']],['Categories','/inventory/categories',['name','active']],['Adjustments','/inventory/adjustments',['id','stock_id','quantity','reason','status']],['Movements','/inventory/movements',['stock_id','quantity','value','kind','created']],['Low stock','/inventory/low-stock',['name','quantity','reserved','available','threshold']]]},
  expenses:{title:'Every rupee, accounted for.',sub:'A clear view of what keeps your restaurant running.',tabs:[['Expenses','/expenses',['id','category_id','payee','amount','paid','payment_status','created']],['Categories','/expenses/categories',['name','active']]]},
  team:{title:'The people behind the service.',sub:'The right access for every member of your team.',tabs:[['Team members','/users',['username','role','active']]]},
  shifts:{title:'Start clear. Close balanced.',sub:'Track your float, cash movements and shift reconciliation.',tabs:[['Cash shifts','/shifts',['id','cashier_id','opened','closed','opening_float','expected_cash','difference']]]},
  settings:{title:'Make it your restaurant.',sub:'Your identity, billing rules and government connections.',tabs:[['Restaurant','/settings/restaurant'],['Province & tax','/settings/tax'],['Fiscal connections','/fiscal/connectors',['authority','pos_id','auto_submit','mode','enabled']],['Submissions','/fiscal/submissions'],['Activity','/audit',['user_id','action','record_id','created']]]},
  offers:{title:'A little more to love.',sub:'Thoughtful combinations and offers worth coming back for.',tabs:[['Combos','/menu/combos',['name','price','active','starts_at','ends_at']],['Promotions','/menu/promotions',['name','kind','value','priority','active','starts_at','ends_at']],['Categories','/menu/categories',['name','position','active']]]}
};
const managerOnly=new Set(['/expenses/categories']);

async function resourcePage(page,tabIndex=0){
  clearInterval(refreshTimer);
  if(page==='reports')return reportsPage();
  const group=groups[page];
  state.resourceTab={page,tabIndex};
  const [name,path,cols]=group.tabs[tabIndex];
  const data=await api(path);
  const manager=state.user.role==='manager';
  const canCreate=!!spec.paths[path]?.post&&(manager||!managerOnly.has(path));
  const activeTaxRule = (path === '/settings/tax' && Array.isArray(data))
    ? (data.slice().sort((a,b)=>(b.effective_from||0)-(a.effective_from||0))[0] || null)
    : null;
  const canPutTax=path==='/settings/tax'&&manager;
  const canEdit=!!spec.paths[path+'/{ident}']?.put&&(manager||!managerOnly.has(path));
  $('#content').innerHTML=heading(
    group.title,
    group.sub,
    `${canCreate?btn('Add '+(name==='Purchases'?'purchase':name==='Team members'?'team member':name==='Stock items'?'stock item':name.replace(/s$/,'').toLowerCase()),'create'):''}${canPutTax?btn(activeTaxRule?'Edit tax rule':'Configure tax rule','create-tax',false,'settings'):''}${page==='shifts'?btn('Open shift','open-shift'):''}${page==='inventory'&&tabIndex===0?btn('Stock count','stock-count',true,'stock'):''}`
  )+`<div class="tabs">${group.tabs.map(([n],i)=>`<button data-tab="${i}" class="${i===tabIndex?'active':''}">${n}</button>`).join('')}</div>${path==='/settings/tax'?'<div class="notice">Active tax rule applies to newly placed orders. You can customize the tax rate, province, card payment rate, tax inclusion, and NTN registration at any time.</div>':''}${path==='/fiscal/connectors'?'<div class="notice">For FBR, only your numeric <strong>FBR POS ID</strong> is required. Turn on <strong>Auto-submit every confirmed order</strong> to send orders to FBR automatically when confirmed and print the FBR Invoice # &amp; QR code on every receipt.</div>':''}<section class="panel" id="resource-body"></section>`;
  $$('[data-tab]').forEach(b=>b.onclick=()=>resourcePage(page,+b.dataset.tab));
  const refresh=()=>resourcePage(page,tabIndex);
  $('[data-action=create]')?.addEventListener('click',()=>operation(path,'post',path==='/fiscal/connectors'?{authority:'FBR',transport:'local',environment_prefix:'FISCAL_FBR',enabled:true,auto_submit:true}:{},refresh,'Add '+name));
  $('[data-action=create-tax]')?.addEventListener('click',()=>operation(
    '/settings/tax',
    'put',
    activeTaxRule || {province:'islamabad',tax_bps:1600,discount_before_tax:true,inclusive:false,source:'FBR Statutory Rate',effective_from:Math.floor(Date.now()/1000)},
    refresh,
    activeTaxRule ? 'Edit active tax rule' : 'Configure province & tax'
  ));
  $('[data-action=open-shift]')?.addEventListener('click',()=>operation('/shifts/open','post',{},refresh,'Open a cash shift'));
  $('[data-action=stock-count]')?.addEventListener('click',()=>operation('/inventory/counts','post',{},refresh,'Record a stock count'));
  if(path==='/fiscal/submissions'){renderFiscal(data,refresh);return}
  if(path==='/settings/tax'){
    const rule = activeTaxRule;
    if(rule){
      const isAuto = !!rule.auto_submit;
      $('#resource-body').innerHTML=`
        <div class="panel-head">
          <div>
            <h2>Active tax rule</h2>
            <small style="color:var(--muted)">Authority: <strong>${esc(rule.authority||'FBR')}</strong> · Province: <strong>${esc((rule.province||'').toUpperCase())}</strong></small>
          </div>
          <div style="display:flex;gap:8px;align-items:center;">
            <button class="button ${isAuto?'secondary':''}" data-action="toggle-auto-fbr" style="${isAuto?'border-color:var(--success,#107c41);color:var(--success,#107c41);':''}">${icon('sliders')}${isAuto ? 'FBR Auto-Send: ON' : 'FBR Auto-Send: OFF'}</button>
            ${btn('Edit tax rule','edit-tax-rule',true,'settings')}
          </div>
        </div>
        <div class="detail-grid">
          <div><small>Province</small><p style="text-transform:capitalize"><strong>${esc((rule.province||'').replace(/_/g,' '))}</strong></p></div>
          <div><small>Tax authority</small><p><strong>${esc(rule.authority||'FBR')}</strong></p></div>
          <div><small>Standard sales tax rate</small><p><strong>${((rule.tax_bps||0)/100).toFixed(2)}%</strong> (${rule.tax_bps} bps)</p></div>
          <div><small>Card payment tax rate</small><p>${rule.card_tax_bps!==null&&rule.card_tax_bps!==undefined?((rule.card_tax_bps/100).toFixed(2)+'% ('+rule.card_tax_bps+' bps)'):'Standard rate applies'}</p></div>
          <div><small>Pricing mode</small><p>${rule.inclusive?'Tax Inclusive (included in menu prices)':'Tax Exclusive (added at checkout)'}</p></div>
          <div><small>Discount policy</small><p>${rule.discount_before_tax?'Discount applied before tax':'Discount applied after tax'}</p></div>
          <div><small>FBR auto-submission</small><p>${isAuto ? '<strong style="color:var(--success,#107c41)">● Enabled (Orders auto-sent to FBR)</strong>' : '<strong style="color:var(--muted)">○ Disabled (Do not send to FBR)</strong>'}</p></div>
          <div><small>NTN / Registration #</small><p>${esc(rule.registration||'Not configured')}</p></div>
          <div><small>Legal source / Reference</small><p>${esc(rule.source||'Official statutory rate')}</p></div>
          <div><small>Effective date</small><p>${rule.effective_from?new Date(rule.effective_from*1000).toLocaleString():'Immediate / Active'}</p></div>
        </div>`;
      $('[data-action=toggle-auto-fbr]')?.addEventListener('click', async e => {
        await busy(e.currentTarget, async () => {
          const updated = {
            province: rule.province || 'islamabad',
            tax_bps: rule.tax_bps || 1600,
            discount_before_tax: rule.discount_before_tax ?? true,
            card_tax_bps: rule.card_tax_bps ?? null,
            inclusive: !!rule.inclusive,
            source: rule.source || 'FBR Statutory Rate',
            effective_from: rule.effective_from || 0,
            registration: rule.registration || '',
            auto_submit: !isAuto
          };
          await api('/settings/tax', { method: 'PUT', body: updated });
          toast(isAuto ? 'FBR auto-submit turned OFF' : 'FBR auto-submit turned ON');
          refresh();
        });
      });
      $('[data-action=edit-tax-rule]')?.addEventListener('click',()=>operation(
        '/settings/tax',
        'put',
        rule,
        refresh,
        'Edit active tax rule'
      ));
    } else {
      $('#resource-body').innerHTML=`
        <div class="panel-head">
          <h2>Active tax rule</h2>
          ${btn('Configure tax rule','setup-tax-rule',true,'settings')}
        </div>
        ${empty('No active tax rule configured yet. Set up your restaurant tax rate and province.')}
      `;
      $('[data-action=setup-tax-rule]')?.addEventListener('click',()=>operation(
        '/settings/tax',
        'put',
        {province:'islamabad',tax_bps:1600,discount_before_tax:true,inclusive:false,auto_submit:false,source:'FBR Statutory Rate',effective_from:Math.floor(Date.now()/1000)},
        refresh,
        'Configure province & tax'
      ));
    }
    return;
  }
  if(!Array.isArray(data)){
    $('#resource-body').innerHTML=`<div class="panel-head"><h2>${name}</h2>${btn('Edit settings','edit-settings',true,'settings')}</div><div class="detail-grid">${Object.entries(data).filter(([k])=>!['id','tax_rules'].includes(k)).map(([k,v])=>`<div><small>${esc(label(k))}</small><p>${esc(format(k,v))}</p></div>`).join('')}</div>`;
    $('[data-action=edit-settings]').onclick=()=>operation(path,'put',data,refresh,'Edit '+name);
    return;
  }
  $('#resource-body').innerHTML=`<div class="panel-head"><h2>${name}</h2><small>${data.length} records</small></div>${table(data,cols||Object.keys(data[0]||{}).slice(0,6),(r,i)=>`<button class="button secondary small" data-record="${i}">${canEdit?'Manage':'View'} ${icon('arrow')}</button>`)}`;
  $$('[data-record]').forEach(b=>b.onclick=()=>recordDetail(data[+b.dataset.record],path,name,canEdit,refresh));
}

async function recordDetail(r,path,title,canEdit,refresh){
  const manager=state.user.role==='manager';
  const actions=[];
  const add=(text,p,method='post',initial={})=>actions.push({text,p,method,initial});
  if(canEdit)add('Edit',path+'/{ident}','put',r);
  if(path==='/users'){
    add('Reset password','/users/{ident}/password');
    if(manager && r.id !== state.user?.id){
      add('Delete member','/users/{ident}','delete');
    }
  }
  if(path==='/inventory/invoices'){add('Supplier payment',path+'/{ident}/payments');if(manager)add('Return items',path+'/{ident}/returns');}
  if(path==='/expenses'){add('Record payment',path+'/{ident}/payments');if(manager&&!r.reversed)add('Reverse expense',path+'/{ident}/reverse');}
  if(path==='/inventory/adjustments'&&manager&&r.status==='pending')add('Approve adjustment',path+'/{ident}/approve');
  if(path==='/shifts'&&!r.closed){add('Cash movement',path+'/{ident}/movements');add('Close shift',path+'/{ident}/close');}
  modal(title,`<div class="detail-grid">${Object.entries(r).filter(([k,v])=>typeof v!=='object'&&!['password','content'].includes(k)).map(([k,v])=>`<div><small>${esc(label(k))}</small><p>${esc(format(k,v))}</p></div>`).join('')}</div>${r.lines?table(r.lines,Object.keys(r.lines[0]||{}).filter(k=>!['returned_cost','returned_total'].includes(k)).slice(0,8)):''}<div class="detail-actions">${actions.map((a,i)=>`<button class="button ${i?'secondary':''}" data-record-action="${i}">${esc(a.text)}</button>`).join('')}${['/inventory/invoices','/expenses'].includes(path)?'<button class="button secondary" id="attachments">Receipts & attachments</button>':''}</div>`);
  $$('[data-record-action]').forEach(b=>b.onclick=()=>{
    const a=actions[+b.dataset.recordAction];
    operation(a.p,a.method,{...a.initial,id:r.id},refresh,a.text);
  });
  if($('#attachments'))$('#attachments').onclick=()=>attachments(path==='/expenses'?'expense':'purchase_invoice',r.id);
}

async function attachments(entity,id){
  const files=await api(`/attachments/${entity}/${id}/list`);
  modal('Receipts & attachments',`${files.map(f=>`<div class="row between" style="padding:12px 0"><span>${esc(f.name)}</span><button class="button secondary small" data-download="${f.id}" data-name="${esc(f.name)}">Download</button></div>`).join('')||empty('No receipts attached')}<form id="attachment-form"><label class="field"><span>Upload receipt · PDF, JPEG or PNG · up to 5 MB</span><input type="file" name="file" accept="application/pdf,image/jpeg,image/png" required></label><div class="modal-footer"><button class="button">Upload receipt</button></div></form>`);
  $$('[data-download]').forEach(b=>b.onclick=()=>download('/attachments/'+b.dataset.download,b.dataset.name));
  $('#attachment-form').onsubmit=async e=>{
    e.preventDefault();
    await busy($('button',e.target),async()=>{
      await api(`/attachments/${entity}/${id}`,{method:'POST',body:new FormData(e.target)});
      toast('Receipt attached');
      await attachments(entity,id);
    }).catch(()=>{});
  };
}

function renderFiscal(data,refresh){
  $('#resource-body').innerHTML=`<div class="panel-head"><h2>Invoice queue</h2>${btn('Process pending','process',true,'shield')}</div>${table(data.invoices,['order_id','authority','status'],r=>`<button class="button secondary small" data-fiscal="${r.order_id}">Review</button>`)}<h2 style="margin:25px 0 15px">Credit notes</h2>${table(data.credits,['id','order_id','status'],r=>`<button class="button secondary small" data-credit="${r.id}">Submit credit</button>`)}`;
  $('[data-action=process]').onclick=async e=>{
    await busy(e.currentTarget,async()=>{
      const r=await api('/fiscal/process-pending',{method:'POST'});
      toast(`${r.length} pending invoices processed`);
      await refresh();
    }).catch(()=>{});
  };
  $$('[data-fiscal]').forEach(b=>b.onclick=()=>operation('/fiscal/orders/{ident}/reconcile','post',{id:+b.dataset.fiscal},refresh,'Reconcile with authority'));
  $$('[data-credit]').forEach(b=>b.onclick=async()=>{
    try{
      const r=await api(`/fiscal/credits/${b.dataset.credit}/submit`,{method:'POST'});
      toast('Credit status: '+r.status);
      await refresh();
    }catch(e){toast(e.message)}
  });
}

async function reportsPage(period='today'){
  const r=await api('/reports/period?period='+period);
  $('#content').innerHTML=heading('The numbers behind the flavour.','Understand your service, your costs and your growth.',`<select id="report-period" aria-label="Report period">${['today','week','month'].map(p=>`<option value="${p}" ${p===period?'selected':''}>${label(p)}</option>`).join('')}</select>`)+`
    <div class="stats">${[['Net sales','net_sales'],['Gross profit','gross_profit'],['Operating profit','operating_profit'],['Tax collected','tax_collected']].map(([n,k])=>`<div class="stat"><div class="stat-title">${n}<span class="stat-icon">${icon('chart')}</span></div><div class="stat-value">${money(r[k])}</div><small>${label(period)} · Restaurant timezone</small></div>`).join('')}</div>
    ${r.costs_complete===false?'<div class="notice warn"><span style="font-size:16px;flex-shrink:0">💡</span><span><strong>Provisional profit:</strong> Some recipe or stock costs are missing. Recorded profit is provisional.</span></div>':''}
    <div class="grid-two">
      <section class="panel"><div class="panel-head"><h2>Best-selling dishes</h2></div>${table(r.best_selling,['name','quantity','net_sales'])}</section>
      <section class="panel"><div class="panel-head"><h2>Service summary</h2></div>${table(Object.entries(r).filter(([k])=>['orders','cost_of_sales','expenses','discounts','refunds','inventory_losses','outstanding'].includes(k)).map(([k,v])=>({metric:label(k),result:k==='orders'?v:money(v)})),['metric','result'])}</section>
    </div>
    <section class="panel section-space">
      <div class="panel-head"><div><h2>Take your records with you</h2><small>CSV exports for the selected reporting period</small></div>${icon('download')}</div>
      <div class="row wrap">${['order','payment','refund','expense','purchase_invoice','purchase_return','movement','shift'].map(k=>`<button class="button secondary small" data-export="${k}">${icon('download')}${label(k)}</button>`).join('')}</div>
    </section>`;
  $('#report-period').onchange=e=>reportsPage(e.target.value);
  $$('[data-export]').forEach(b=>b.onclick=()=>download(`/reports/export/${b.dataset.export}?start=${r.start}&end=${r.end}`,b.dataset.export+'.csv'));
}

async function download(path,name){
  try{
    const r=await api(path,{raw:true});
    const url=URL.createObjectURL(await r.blob());
    const a=document.createElement('a');
    a.href=url;
    a.download=name;
    a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){toast(e.message)}
}

async function notifications(){
  try{
    const rows=await api('/notifications');
    modal('A little heads-up from the kitchen',table(rows,['stock_id','message','active','read'],r=>`<button class="button secondary small" data-read="${r.id}">Acknowledge</button>`));
    $$('[data-read]').forEach(b=>b.onclick=async()=>{
      await api(`/notifications/${b.dataset.read}/read`,{method:'POST'});
      toast('Notification acknowledged');
      notifications();
    });
  }catch(e){toast(e.message)}
}

function resolve(schema){
  if(schema?.$ref)return spec.components.schemas[schema.$ref.split('/').pop()];
  if(schema?.anyOf){
    const candidate=schema.anyOf.find(x=>x.type!=='null');
    return {...resolve(candidate),nullable:schema.anyOf.some(x=>x.type==='null'),...Object.fromEntries(Object.entries(schema).filter(([k])=>k!=='anyOf'))};
  }
  return schema||{};
}

const friendly={
  pos_id:'FBR POS ID',auto_submit:'Auto-submit every confirmed order to FBR / authority',category_id:'Category',stock_id:'Ingredient / stock item',supplier_id:'Supplier',item_id:'Menu item',combo_id:'Combo',payment_id:'Original payment',invoice_reference:'Supplier invoice reference',tax_bps:'Standard tax rate (%)',card_tax_bps:'Card tax rate (%)',image_url:'Photograph URL',parent_item_id:'Variant of',starts_at:'Starts',ends_at:'Ends',effective_from:'Effective from',allow_shortage:'Authorize stock shortage',allow_unpaid:'Authorize unpaid preparation',environment_prefix:'Credential profile (optional if POS ID is set)',classification_code:'PCT / Service code (optional for FBR)',discount_before_tax:'Apply discount before calculating tax',recoverable_purchase_tax:'Purchase tax is recoverable',recoverable_expense_tax:'Expense tax is recoverable',source:'Official tax source',ntn:'NTN',registration:'Tax registration',line_index:'Invoice line (first line = 0)'
};

async function lookups(path){
  const data={};
  const sources={
    item_id:'/menu/items',
    stock_id:'/inventory/items',
    supplier_id:'/suppliers',
    category_id:path.startsWith('/menu')?'/menu/categories':path.startsWith('/expenses')?'/expenses/categories':'/inventory/categories',
    parent_item_id:'/menu/items',
    combo_id:'/menu/combos'
  };
  await Promise.allSettled(Object.entries(sources).map(async([k,p])=>{
    if(state.user.role==='cashier'&&['stock_id','supplier_id','category_id'].includes(k))return;
    data[k]=await api(p);
  }));
  return data;
}

function formField(key,raw,value,required,lookup,prefix=''){
  const s=resolve(raw),type=s.type,name=prefix?prefix+'.'+key:key;
  const id='field-'+name.replace(/[^\w]/g,'-');
  let title=friendly[key]||label(key),hint='';
  let input;
  if(type==='object'){
    if(s.properties)return `<fieldset class="field full" data-object="${esc(name)}"><legend>${esc(title)}</legend><div class="form-grid">${Object.entries(s.properties).map(([k,v])=>formField(k,v,value?.[k],s.required?.includes(k),lookup,name)).join('')}</div></fieldset>`;
    return `<label class="field full"><span>${esc(title)}</span><textarea id="${id}" data-map="${esc(name)}" placeholder="carton = 12">${esc(Object.entries(value||{}).map(([k,v])=>`${k} = ${v}`).join('\n'))}</textarea><small>One unit conversion per line, for example: carton = 12</small></label>`;
  }
  if(type==='array'){
    const arr=value||s.default||[];
    return `<div class="field full" data-array="${esc(name)}"><span>${esc(title)}</span><div class="field-array" data-array-items>${arr.map((v,i)=>arrayEntry(name,i,s.items,v,lookup)).join('')}</div><button class="button secondary small" type="button" data-add-row="${esc(name)}">+ Add ${esc(title.toLowerCase().replace(/s$/,''))}</button></div>`;
  }
  if(value===undefined)value=s.default;
  if(type==='boolean')input=`<input type="checkbox" id="${id}" data-field="${esc(name)}" data-type="boolean" ${value?'checked':''}>`;
  else if(lookup[key]?.length){
    input=`<select id="${id}" data-field="${esc(name)}" data-type="integer" ${required?'required':''}><option value="">${required?'Choose…':'None'}</option>${lookup[key].map(r=>`<option value="${r.id}" ${r.id===value?'selected':''}>${esc(r.name||r.username||r.code)}${r.unit?' · '+esc(r.unit):''}</option>`).join('')}</select>`;
  }
  else if(s.enum){
    input=`<select id="${id}" data-field="${esc(name)}" data-type="${type||'string'}">${s.enum.map(v=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(label(v))}</option>`).join('')}</select>`;
  }
  else if(['starts_at','ends_at','effective_from','created','purchased_at'].includes(key)){
    const local=value?new Date(value*1000-new Date(value*1000).getTimezoneOffset()*60000).toISOString().slice(0,16):'';
    input=`<input id="${id}" type="datetime-local" data-field="${esc(name)}" data-type="date" value="${local}" ${required?'required':''}>`;
    hint='Your device’s local time; saved as an exact instant.';
  }
  else if(type==='integer'||type==='number'){
    const monetary=moneyKey(key),rate=key.endsWith('_bps');
    const factor=monetary||rate?100:1;
    if(monetary){title+=' (Rs)';hint='Enter rupees, for example 350.00.'}
    if(key==='value'){title='Discount value (% or Rs)';hint='For percentage discounts enter 10 for 10%; for fixed discounts enter rupees.'}
    input=`<input id="${id}" type="number" data-field="${esc(name)}" data-type="${type}" data-factor="${factor}" step="${factor===100?'0.01':type==='integer'?'1':'any'}" ${s.minimum!==undefined?'min="'+s.minimum/factor+'"':''} ${s.maximum!==undefined?'max="'+s.maximum/factor+'"':''} value="${value===undefined||value===null?'':value/factor}" ${required?'required':''}>`;
  }
  else{
    const long=['description','notes','reason','authority_evidence','source'].includes(key);
    input=long?`<textarea id="${id}" data-field="${esc(name)}" data-type="string" ${required?'required':''}>${esc(value||'')}</textarea>`:`<input id="${id}" type="${key.includes('password')?'password':'text'}" data-field="${esc(name)}" data-type="string" value="${esc(value??'')}" ${required?'required':''} ${s.minLength?'minlength="'+s.minLength+'"':''} ${s.maxLength?'maxlength="'+s.maxLength+'"':''} autocomplete="${key.includes('password')?'new-password':'off'}">`;
  }
  return `<label class="field ${['description','notes','reason','authority_evidence','source'].includes(key)?'full':''}" for="${id}"><span>${esc(title)}${required?' *':''}</span>${input}${hint?`<small>${esc(hint)}</small>`:''}</label>`;
}

function arrayEntry(name,index,schema,value,lookup){
  const s=resolve(schema);
  return `<div class="array-entry" data-entry><div class="row between" style="margin-bottom:12px"><small>Entry ${index+1}</small><button type="button" class="button ghost small" data-remove-row>Remove</button></div><div class="form-grid">${s.type==='object'?Object.entries(s.properties).map(([k,v])=>formField(k,v,value?.[k],s.required?.includes(k),lookup,`${name}.${index}`)).join(''):formField(String(index),s,value,true,lookup,name)}</div></div>`;
}

function assign(object,path,value){
  const parts=path.split('.');
  let target=object;
  parts.forEach((part,i)=>{
    if(i===parts.length-1)target[part]=value;
    else{
      if(target[part]===undefined)target[part]=/^\d+$/.test(parts[i+1])?[]:{};
      target=target[part];
    }
  });
}

function readForm(form){
  const result={};
  $$('[data-array]',form).forEach(el=>assign(result,el.dataset.array,[]));
  $$('[data-field]',form).forEach(el=>{
    const type=el.dataset.type;
    let v=type==='boolean'?el.checked:el.value;
    if(type!=='boolean'&&v==='')return;
    if(type==='date')v=new Date(v).getTime()/1000;
    else if(type==='integer'||type==='number')v=Number(v)*(+el.dataset.factor||1);
    if(type==='integer')v=Math.round(v);
    assign(result,el.dataset.field,v);
  });
  $$('[data-map]',form).forEach(el=>{
    const obj={};
    for(const row of el.value.split('\n').filter(x=>x.trim())){
      const [key,v]=row.split('=');
      if(!key?.trim()||!Number.isFinite(+v)||+v<=0)throw Error('Conversions must look like carton = 12');
      obj[key.trim()]=+v;
    }
    assign(result,el.dataset.map,obj);
  });
  return result;
}

async function operation(path,method,initial={},onSave=()=>{},title='Save changes',options={}){
  const op=spec.paths[path]?.[method];
  if(!op)return toast('This action is unavailable.');
  const isDelete=method.toLowerCase()==='delete';
  const raw=op.requestBody?.content?.['application/json']?.schema;
  const s=resolve(raw);
  const lookup=await lookups(path);
  const required=s.required||[];
  const fields=Object.entries(s.properties||{}).filter(([k])=>!options.exclude?.includes(k));
  const url=path.replace('{ident}',initial.id);
  modal(title,`<form id="operation-form"><div class="form-grid">${fields.map(([k,v])=>formField(k,v,initial[k],required.includes(k),lookup)).join('')}</div>${isDelete?'<p style="color:#d93025;font-weight:600;margin:12px 0;">Are you sure you want to permanently delete this member? This action cannot be undone.</p>':(!fields.length?'<p class="muted">Confirm this action to update the record.</p>':'')}<div id="form-error"></div><div class="modal-footer"><button type="button" class="button secondary" id="form-cancel">Cancel</button><button class="button ${isDelete?'danger':''}" type="submit" ${isDelete?'style="background:#d93025;color:#fff;"':''}>${icon(isDelete?'logout':'check')}${isDelete?'Delete permanently':'Save changes'}</button></div></form>`);
  const form=$('#operation-form');
  $('#form-cancel').onclick=()=>$('#modal').close();
  function findSchema(name){
    let current=s;
    for(const part of name.split('.')){
      current=resolve(current);
      current=current.type==='array'?current.items:current.properties[part];
    }
    return resolve(current);
  }
  function bindArrays(){
    $$('[data-add-row]',form).forEach(b=>b.onclick=()=>{
      const name=b.dataset.addRow;
      const list=b.previousElementSibling;
      const index=list.children.length;
      list.insertAdjacentHTML('beforeend',arrayEntry(name,index,findSchema(name).items,{},lookup));
      bindArrays();
    });
    $$('[data-remove-row]',form).forEach(b=>b.onclick=()=>{
      const list=b.closest('[data-array-items]');
      b.closest('[data-entry]').remove();
      const parent=list.closest('[data-array]').dataset.array;
      [...list.children].forEach((entry,i)=>{
        $$('[data-field],[data-array],[data-add-row],[data-map]',entry).forEach(el=>{
          for(const key of ['field','array','addRow','map'])if(el.dataset[key])el.dataset[key]=el.dataset[key].replace(new RegExp('^'+parent.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\.\\d+'),parent+'.'+i);
        });
      });
      bindArrays();
    });
  }
  bindArrays();
  form.onsubmit=async e=>{
    e.preventDefault();
    $('#form-error').innerHTML='';
    const button=$('button[type=submit]',form);
    try{
      await busy(button,async()=>{
        const body=raw?readForm(form):undefined;
        if(body)for(const [key,field] of fields){
          if(resolve(field).nullable&&initial[key]!=null&&body[key]===undefined)body[key]=null;
        }
        if(body)for(const key of options.exclude||[])if(initial[key]!==undefined)body[key]=initial[key];
        const saved=await api(url,{method:method.toUpperCase(),body});
        $('#modal').close();
        toast(isDelete?'Deleted successfully':'Saved successfully');
        await onSave(saved);
      });
    }catch(error){
      if($('#form-error'))$('#form-error').innerHTML=errorBox(error);
    }
  };
}


let prepTicker, clockTicker;
state.kdsFilter = state.kdsFilter || 'all';

function formatKdsClock(){
  return new Date().toLocaleTimeString('en-PK', {hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true});
}

function prepBoardHtml(rows){
  state.lastKdsRows = rows || [];
  const received = Date.now();
  const allActive = [...(rows || [])].filter(r=>['queued','preparing'].includes(r.status))
    .sort((a,b)=>(b.elapsed_seconds||0)-(a.elapsed_seconds||0));
  
  const queued = allActive.filter(r=>r.status==='queued');
  const preparing = allActive.filter(r=>r.status==='preparing');
  const late = allActive.filter(r=>Math.floor((r.elapsed_seconds||0)/60)>=15);
  const totalItems = allActive.reduce((n,r)=>n+(r.lines||[]).reduce((m,l)=>m+(l.quantity||0),0),0);

  let filtered = allActive;
  if(state.kdsFilter === 'queued') filtered = queued;
  else if(state.kdsFilter === 'preparing') filtered = preparing;
  else if(state.kdsFilter === 'late') filtered = late;

  const ticket = r => {
    const mins = Math.floor((r.elapsed_seconds||0)/60);
    const lvl = mins>=20 ? 'late' : mins>=10 ? 'warn' : 'ok';
    const orderItemsCount = (r.lines||[]).reduce((m,l)=>m+(l.quantity||0),0);

    return `<article class="kds-ticket ${r.status} ${lvl}" data-elapsed="${r.elapsed_seconds||0}" data-received="${received}">
      <header class="kds-ticket-head">
        <div class="kds-code">#${esc(r.code)}</div>
        <div class="kds-badges">
          ${r.status==='preparing' ? '<span class="badge preparing">PREPARING</span>' : '<span class="badge queued">QUEUED</span>'}
          <span class="kds-timer ${lvl}">⏱ <span class="kds-timer-val">${mins}</span>m</span>
        </div>
      </header>
      <div class="kds-ticket-body">
        <ul class="kds-items">
          ${(r.lines||[]).map(l=>`
            <li class="kds-item">
              <div class="kds-qty ${l.quantity>1?'large':''}">${l.quantity}×</div>
              <div class="kds-item-details">
                <div class="kds-item-name">${esc(l.name)}</div>
                ${l.notes ? `<div class="kds-line-note">⚠️ <strong>Special:</strong> ${esc(l.notes)}</div>` : ''}
                ${(l.components||[]).length ? `<div class="kds-components">${l.components.map(c=>`<span class="kds-comp-chip">${c.quantity}× ${esc(c.name)}</span>`).join('')}</div>` : ''}
              </div>
            </li>
          `).join('')}
        </ul>
        ${r.notes ? `<div class="kds-order-note">📝 <strong>Order instructions:</strong> ${esc(r.notes)}</div>` : ''}
      </div>
      <footer class="kds-ticket-foot">
        <span>${orderItemsCount} item${orderItemsCount===1?'':'s'} to prepare</span>
        <span>${mins>=20 ? '⚠️ High Wait' : mins>=10 ? '⏳ In Progress' : '✅ Fresh Ticket'}</span>
      </footer>
    </article>`;
  };

  clearInterval(prepTicker);
  prepTicker = setInterval(()=>{
    $$('.kds-ticket').forEach(el=>{
      const secs = (+el.dataset.elapsed) + Math.floor((Date.now()-(+el.dataset.received))/1000);
      const mins = Math.floor(secs/60);
      const lvl = mins>=20 ? 'late' : mins>=10 ? 'warn' : 'ok';
      el.classList.remove('ok','warn','late');
      el.classList.add(lvl);
      const timer = $('.kds-timer', el);
      if(timer){
        timer.classList.remove('ok','warn','late');
        timer.classList.add(lvl);
      }
      const val = $('.kds-timer-val', el);
      if(val) val.textContent = mins;
    });
  }, 10000);

  return `
    <section class="kds-header-panel">
      <div class="kds-title-group">
        <h1>👨‍🍳 Kitchen Preparation Display</h1>
        <p>Sorted by wait time (First In, First Out) · Prioritize tickets with urgent amber and red timers.</p>
      </div>
      <div class="kds-stats-strip">
        <button type="button" class="kds-stat-chip ${state.kdsFilter==='all'?'active':''}" data-kds-filter="all">
          All Orders <strong>${allActive.length}</strong>
        </button>
        <button type="button" class="kds-stat-chip chip-queued ${state.kdsFilter==='queued'?'active':''}" data-kds-filter="queued">
          To Start <strong>${queued.length}</strong>
        </button>
        <button type="button" class="kds-stat-chip chip-preparing ${state.kdsFilter==='preparing'?'active':''}" data-kds-filter="preparing">
          In Progress <strong>${preparing.length}</strong>
        </button>
        ${late.length ? `
          <button type="button" class="kds-stat-chip chip-late ${state.kdsFilter==='late'?'active':''}" data-kds-filter="late">
            Urgent (&gt;15m) <strong>${late.length}</strong>
          </button>
        ` : ''}
        <div class="kds-stat-chip" style="cursor:default" title="Total dishes across all active tickets">
          Total Items <strong>${totalItems}</strong>
        </div>
      </div>
    </section>
    <div class="kds-grid">
      ${filtered.length ? filtered.map(ticket).join('') : `
        <div class="kds-empty">
          <span class="kds-empty-icon">👨‍🍳</span>
          <h2>All caught up!</h2>
          <p>${state.kdsFilter==='all' ? 'There are no pending tickets in the kitchen queue.' : 'No orders matching the "'+state.kdsFilter+'" filter.'}</p>
        </div>
      `}
    </div>
  `;
}

let displayAbort;
async function displayBoard(){
  const screen=state.user.role==='customer_display'?'customer':'preparation';
  $('#app').innerHTML=`
    <main class="board">
      <header class="board-header">
        ${brand()}
        <div class="row" style="gap:12px;flex-wrap:wrap">
          <div class="kds-clock" id="kds-live-clock">🕒 ${formatKdsClock()}</div>
          <span class="live" id="display-connection">Live updates</span>
          <button class="button secondary small" id="kds-fullscreen" title="Toggle Fullscreen">⛶ Fullscreen</button>
          <button class="button secondary small" id="display-logout">Sign out</button>
        </div>
      </header>
      <div id="display-content"></div>
    </main>
  `;

  clearInterval(clockTicker);
  clockTicker = setInterval(()=>{
    const clockEl = $('#kds-live-clock');
    if(clockEl) clockEl.innerHTML = '🕒 ' + formatKdsClock();
  }, 1000);

  $('#kds-fullscreen').onclick = () => {
    if(!document.fullscreenElement){
      document.documentElement.requestFullscreen().catch(()=>{});
    } else {
      document.exitFullscreen().catch(()=>{});
    }
  };

  $('#display-logout').onclick=()=>{
    clearInterval(clockTicker);
    clearInterval(prepTicker);
    displayAbort?.abort();
    logout();
  };

  function bindKdsControls(){
    $$('[data-kds-filter]').forEach(b=>{
      b.onclick = () => {
        state.kdsFilter = b.dataset.kdsFilter;
        render(state.lastKdsRows);
      };
    });
  }

  function render(rows){
    state.lastKdsRows = rows || [];
    if(screen==='customer'){
      $('#display-content').innerHTML = `
        <div class="board-columns">
          ${[['preparing','Freshly in the making'],['ready','Ready to enjoy']].map(([status,title])=>`
            <section class="board-column">
              <div class="eyebrow">${status==='ready'?'PLEASE COLLECT YOUR ORDER':'THANK YOU FOR YOUR PATIENCE'}</div>
              <h2>${title}</h2>
              <div class="tickets">
                ${rows.filter(r=>status==='preparing'?['queued','preparing'].includes(r.status):r.status==='ready').map(r=>`
                  <article class="ticket ${status}">
                    <h2>#${esc(r.code)}</h2>
                    <p>${label(r.status)}</p>
                  </article>
                `).join('')||`<div class="empty" style="grid-column:1/-1">${icon('menu')}<strong>All caught up</strong>No orders in this queue.</div>`}
              </div>
            </section>
          `).join('')}
        </div>
      `;
    } else {
      $('#display-content').innerHTML = prepBoardHtml(rows);
      bindKdsControls();
    }
  }

  try{render(await api('/displays/'+screen))}catch(e){toast(e.message)}
  async function connect(){
    if(!state.user?.role.endsWith('_display'))return;
    displayAbort=new AbortController();
    try{
      const response=await fetch(`/displays/${screen}/events`,{headers:{Authorization:'Bearer '+state.token},signal:displayAbort.signal});
      if(response.status===401||response.status===403){await logout(false);return}
      if(!response.ok)throw Error('Display disconnected');
      $('#display-connection').textContent='Live updates';
      const reader=response.body.getReader(),decoder=new TextDecoder();
      let buffer='';
      while(true){
        const {value,done}=await reader.read();
        if(done)break;
        buffer+=decoder.decode(value,{stream:true});
        let split;
        while((split=buffer.indexOf('\n\n'))>=0){
          const event=buffer.slice(0,split);
          buffer=buffer.slice(split+2);
          if(event.startsWith('data: '))render(JSON.parse(event.slice(6)));
        }
      }
    }catch(e){if(e.name==='AbortError')return}
    if(state.user?.role.endsWith('_display')){
      $('#display-connection').textContent='Reconnecting…';
      setTimeout(connect,3000);
    }
  }
  connect();
}

window.addEventListener('unhandledrejection',e=>{
  console.error(e.reason);
  toast(e.reason?.message||'Something went wrong. Please try again.');
});
if(state.token)boot();else login();
