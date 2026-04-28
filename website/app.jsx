// app.jsx — Speedy: OS-level trade-on-highlight cursor
// The user's "computer" — desktop with multiple host apps, Speedy lives in the system layer

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "triggerStyle": "chip",
  "marketType": "auto",
  "showTickerTail": true,
  "activeApp": "browser",
  "wallpaper": "dawn",
  "hotkeyMode": "hold",
  "alwaysOn": false
}/*EDITMODE-END*/;

// Hotkey: ⌃ (Control) — "hold" = held during selection, "arm" = press once to arm next selection
const HOTKEY_LABEL = "⌃";
const HOTKEY_NAME = "Control";

// ─── Mock market data ────────────────────────────────────────────────────────
const MARKETS = [
  { id:"fed-cut-may", type:"prediction", title:"Fed cuts rates at May 7 meeting?", venue:"Polymarket",
    yesPrice:0.62, yesChange:0.04, volume:"$8.4M", yesPct:62,
    keywords:["fed","rate cut","rate decision","fomc","may meeting","powell","cut rates","rates"]},
  { id:"fed-50bp-2026", type:"prediction", title:"≥50bp of cuts by year-end?", venue:"Polymarket",
    yesPrice:0.41, yesChange:-0.02, volume:"$2.1M", yesPct:41,
    keywords:["50 basis points","year-end","by december","two cuts","cumulative"]},
  { id:"spx", type:"stock", title:"S&P 500 ETF", venue:"NYSE", ticker:"SPY",
    price:564.18, change:0.82, changePct:0.15,
    keywords:["s&p","s&p 500","stock market","equities","index","spy"]},
  { id:"nvda", type:"stock", title:"NVIDIA Corp", venue:"NASDAQ", ticker:"NVDA",
    price:142.86, change:-1.24, changePct:-0.86,
    keywords:["nvidia","nvda","chip","gpu","ai chip"]},
  { id:"btc-perp", type:"perp", title:"BTC-PERP", venue:"Hyperliquid", ticker:"BTC",
    price:71240, change:1820, changePct:2.62, funding:0.0042,
    keywords:["bitcoin","btc","crypto","digital asset"]},
  { id:"eth-perp", type:"perp", title:"ETH-PERP", venue:"Hyperliquid", ticker:"ETH",
    price:3284, change:52, changePct:1.61, funding:0.0028,
    keywords:["ethereum","eth","ether"]},
  { id:"gold", type:"commodity", title:"Gold Futures", venue:"COMEX", ticker:"GC",
    price:2718.40, change:18.20, changePct:0.67,
    keywords:["gold","precious metal","bullion","safe haven"]},
  { id:"oil", type:"commodity", title:"WTI Crude", venue:"NYMEX", ticker:"CL",
    price:68.42, change:-0.86, changePct:-1.24,
    keywords:["oil","crude","wti","energy","petroleum"]},
  { id:"dxy", type:"stock", title:"Dollar Index", venue:"ICE", ticker:"DXY",
    price:104.62, change:-0.18, changePct:-0.17,
    keywords:["dollar","dxy","greenback","usd","currency"]},
];

function matchMarket(text, filter="auto"){
  if(!text||!text.trim()) return null;
  const t=text.toLowerCase();
  let best=null,bs=0;
  for(const m of MARKETS){
    if(filter!=="auto"&&m.type!==filter) continue;
    let s=0; for(const k of m.keywords) if(t.includes(k)) s+=k.length;
    if(s>bs){bs=s;best=m;}
  }
  return best;
}
function allMatches(text, filter="auto"){
  if(!text||!text.trim()) return [];
  const t=text.toLowerCase();
  return MARKETS
    .filter(m=>filter==="auto"||m.type===filter)
    .map(m=>{let s=0;for(const k of m.keywords) if(t.includes(k)) s+=k.length; return {m,s};})
    .filter(x=>x.s>0).sort((a,b)=>b.s-a.s).map(x=>x.m);
}

// ─── Format helpers ─────────────────────────────────────────────────────────
const fmtPrice=p=>p>=1000?p.toLocaleString(undefined,{maximumFractionDigits:0})
  :p.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const fmtCents=p=>`${Math.round(p*100)}¢`;
const fmtPct=n=>`${n>=0?"+":""}${n.toFixed(2)}%`;

// ─── Speedy "system" theme — OS-level UI, lives above everything ────────────
const SPEEDY = {
  ink: "#0e0e10",
  surface: "rgba(28,28,30,0.78)",     // dark glass like Spotlight/Raycast
  surfaceSolid: "#1c1c1e",
  border: "rgba(255,255,255,0.08)",
  borderStrong: "rgba(255,255,255,0.14)",
  text: "#f5f5f7",
  textSoft: "rgba(245,245,247,0.62)",
  textFaint: "rgba(245,245,247,0.36)",
  accent: "oklch(0.72 0.22 295)",      // electric violet — Speedy brand
  pos: "oklch(0.78 0.20 142)",
  neg: "oklch(0.70 0.22 25)",
  selBg: "oklch(0.72 0.22 295 / 0.32)",
};

// ─── Wallpapers ─────────────────────────────────────────────────────────────
const WALLPAPERS = {
  dawn: "linear-gradient(135deg, oklch(0.42 0.16 280) 0%, oklch(0.55 0.18 25) 50%, oklch(0.62 0.16 60) 100%)",
  dusk: "linear-gradient(160deg, oklch(0.22 0.08 270) 0%, oklch(0.32 0.14 290) 50%, oklch(0.45 0.20 320) 100%)",
  graphite: "linear-gradient(180deg, #1a1a1c 0%, #2a2a2e 100%)",
};

// ─── Selection hook (works across "host app" surfaces) ──────────────────────
function useSystemSelection(scopeRef, isArmedRef){
  const [state,setState]=React.useState({text:"",rect:null,isSelecting:false,liveText:"",liveRect:null,armed:false});
  React.useEffect(()=>{
    const scope=scopeRef.current; if(!scope) return;
    let dragging=false;
    let dragArmed=false;
    const onDown=(e)=>{
      // only inside a [data-host-app] surface
      const host=e.target.closest("[data-host-app]");
      if(!host) return;
      dragging=true;
      dragArmed=isArmedRef.current(e); // capture armed state at drag start
      const sel=window.getSelection(); sel.removeAllRanges();
      setState(s=>({...s,text:"",rect:null,isSelecting:true,liveText:"",liveRect:null,armed:dragArmed}));
    };
    const onMove=(e)=>{
      if(!dragging) return;
      // Update armed state live during drag (so user can press hotkey mid-selection)
      const liveArmed=dragArmed||isArmedRef.current(e);
      const sel=window.getSelection(); if(!sel||sel.rangeCount===0) return;
      const txt=sel.toString();
      const r=sel.getRangeAt(0);
      const rects=r.getClientRects();
      const last=rects[rects.length-1];
      setState(s=>({...s,liveText:txt,liveRect:last?{x:e.clientX,y:e.clientY,end:last}:null,isSelecting:true,armed:liveArmed}));
    };
    const onUp=(e)=>{
      if(!dragging) return; dragging=false;
      const finalArmed=dragArmed||isArmedRef.current(e);
      const sel=window.getSelection();
      const txt=sel?sel.toString().trim():"";
      if(!txt||!finalArmed){setState({text:"",rect:null,isSelecting:false,liveText:"",liveRect:null,armed:false}); return;}
      const r=sel.getRangeAt(0);
      const rects=r.getClientRects();
      const last=rects[rects.length-1];
      const bounding=r.getBoundingClientRect();
      setState({text:txt,rect:{end:last,bounding,mouseX:e.clientX,mouseY:e.clientY},isSelecting:false,liveText:"",liveRect:null,armed:true});
    };
    const onDocDown=(e)=>{
      // click outside any host app and outside speedy UI -> clear
      if(!e.target.closest("[data-host-app]")&&!e.target.closest("[data-speedy]")){
        setState({text:"",rect:null,isSelecting:false,liveText:"",liveRect:null});
      }
    };
    document.addEventListener("mousedown",onDown,true);
    window.addEventListener("mousemove",onMove);
    window.addEventListener("mouseup",onUp);
    document.addEventListener("mousedown",onDocDown);
    return ()=>{
      document.removeEventListener("mousedown",onDown,true);
      window.removeEventListener("mousemove",onMove);
      window.removeEventListener("mouseup",onUp);
      document.removeEventListener("mousedown",onDocDown);
    };
  },[scopeRef,isArmedRef]);
  const clear=React.useCallback(()=>{
    const s=window.getSelection(); if(s) s.removeAllRanges();
    setState({text:"",rect:null,isSelecting:false,liveText:"",liveRect:null,armed:false});
  },[]);
  return [state,clear];
}

// ─── Market type badge ───────────────────────────────────────────────────────
function MarketTypeBadge({type,small}){
  const labels={prediction:"PRED",stock:"STOCK",perp:"PERP",commodity:"COMM"};
  const colors={prediction:"oklch(0.72 0.22 295)",stock:"oklch(0.70 0.18 220)",perp:"oklch(0.74 0.20 50)",commodity:"oklch(0.70 0.16 80)"};
  return <span style={{display:"inline-flex",alignItems:"center",background:colors[type],color:"#0e0e10",
    fontFamily:"'JetBrains Mono',monospace",fontSize:small?8.5:9,fontWeight:700,
    padding:small?"2px 4px":"2px 5px",borderRadius:3,letterSpacing:"0.04em"}}>{labels[type]}</span>;
}

// ─── Live ticker tail (BOLD IDEA) — follows cursor while dragging ────────────
function TickerTail({liveText,liveRect}){
  if(!liveText||!liveRect) return null;
  const market=matchMarket(liveText);
  return (
    <div data-speedy style={{position:"fixed",left:liveRect.x+14,top:liveRect.y+14,
      pointerEvents:"none",zIndex:99998}}>
      <div style={{
        background:SPEEDY.surfaceSolid,color:SPEEDY.text,
        padding:"6px 11px",borderRadius:999,
        fontFamily:"'JetBrains Mono',monospace",fontSize:11,fontWeight:500,
        whiteSpace:"nowrap",display:"flex",alignItems:"center",gap:8,
        boxShadow:`0 6px 20px rgba(0,0,0,0.32), 0 0 0 0.5px ${SPEEDY.borderStrong}`,
      }}>
        {market?(<>
          <span style={{width:6,height:6,borderRadius:"50%",background:SPEEDY.accent,animation:"pulse 1.2s infinite"}}/>
          <span style={{color:SPEEDY.textFaint}}>match →</span>
          <span style={{fontWeight:600}}>{market.ticker||"PRED"}</span>
          <span style={{color:SPEEDY.textSoft,maxWidth:200,overflow:"hidden",textOverflow:"ellipsis"}}>{market.title}</span>
        </>):(<>
          <span style={{width:6,height:6,borderRadius:"50%",background:SPEEDY.textFaint}}/>
          <span style={{color:SPEEDY.textFaint}}>scanning…</span>
        </>)}
      </div>
    </div>
  );
}

// ─── Trade panel ─────────────────────────────────────────────────────────────
function TradePanel({market,onClose,onSwap,alternates}){
  const isPred=market.type==="prediction";
  const [side,setSide]=React.useState(isPred?"yes":"buy");
  const [size,setSize]=React.useState(100);
  const [stage,setStage]=React.useState("entry");
  const [showSwap,setShowSwap]=React.useState(false);
  React.useEffect(()=>{setSide(isPred?"yes":"buy");},[market.id]);
  const sideOpts=isPred
    ?[{v:"yes",label:`Yes ${fmtCents(market.yesPrice)}`,color:SPEEDY.pos},
      {v:"no",label:`No ${fmtCents(1-market.yesPrice)}`,color:SPEEDY.neg}]
    :[{v:"buy",label:market.type==="perp"?"Long":"Buy",color:SPEEDY.pos},
      {v:"sell",label:market.type==="perp"?"Short":"Sell",color:SPEEDY.neg}];
  const sideColor=sideOpts.find(s=>s.v===side)?.color||SPEEDY.accent;
  const submit=()=>{
    setStage("confirming");
    setTimeout(()=>setStage("done"),700);
    setTimeout(()=>onClose(),2100);
  };
  const shares=isPred
    ?Math.floor(size/(side==="yes"?market.yesPrice:(1-market.yesPrice))*100)/100
    :(size/market.price).toFixed(market.price>1000?4:2);

  return (
    <div data-speedy style={{
      width:300,
      background:SPEEDY.surface,
      backdropFilter:"blur(40px) saturate(180%)",
      WebkitBackdropFilter:"blur(40px) saturate(180%)",
      border:`0.5px solid ${SPEEDY.borderStrong}`,
      borderRadius:14,
      boxShadow:`inset 0 1px 0 rgba(255,255,255,0.06), 0 24px 60px rgba(0,0,0,0.45), 0 8px 20px rgba(0,0,0,0.25)`,
      overflow:"hidden",fontFamily:"'Inter',system-ui,sans-serif",color:SPEEDY.text,
    }}>
      {/* Speedy attribution bar */}
      <div style={{
        padding:"7px 12px",borderBottom:`0.5px solid ${SPEEDY.border}`,
        display:"flex",alignItems:"center",justifyContent:"space-between",
        fontSize:10,color:SPEEDY.textFaint,
        fontFamily:"'JetBrains Mono',monospace",letterSpacing:"0.04em",
      }}>
        <div style={{display:"flex",alignItems:"center",gap:6}}>
          <SpeedyMark size={11}/>
          <span>SPEEDY</span>
        </div>
        <span>⌘⏎ confirm  ·  esc</span>
      </div>

      {/* Market info */}
      <div style={{padding:"11px 14px 10px",borderBottom:`0.5px solid ${SPEEDY.border}`,position:"relative"}}>
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",gap:8}}>
          <div style={{display:"flex",alignItems:"center",gap:6}}>
            <MarketTypeBadge type={market.type}/>
            <span style={{fontFamily:"'JetBrains Mono',monospace",fontSize:10,color:SPEEDY.textFaint,letterSpacing:"0.04em",textTransform:"uppercase"}}>{market.venue}</span>
          </div>
          {alternates.length>1&&(
            <button onClick={()=>setShowSwap(s=>!s)} style={{
              appearance:"none",border:0,background:"transparent",color:SPEEDY.textSoft,
              fontSize:11,cursor:"pointer",padding:"2px 6px",borderRadius:5,
              display:"flex",alignItems:"center",gap:3,fontFamily:"inherit",
            }}>swap <svg width="9" height="9" viewBox="0 0 9 9" fill="none"><path d="M1.5 3l3 3 3-3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg></button>
          )}
        </div>
        <div style={{marginTop:7,fontWeight:600,fontSize:13.5,lineHeight:1.25,letterSpacing:"-0.01em"}}>
          {market.ticker?<>
            <span>{market.ticker}</span>
            <span style={{color:SPEEDY.textFaint,fontWeight:400,marginLeft:6,fontSize:12}}>{market.title}</span>
          </>:market.title}
        </div>
        <div style={{marginTop:8,display:"flex",alignItems:"baseline",gap:8,fontFamily:"'JetBrains Mono',monospace"}}>
          {isPred?<>
            <span style={{fontSize:22,fontWeight:600,letterSpacing:"-0.01em"}}>{fmtCents(market.yesPrice)}</span>
            <span style={{fontSize:11,color:market.yesChange>=0?SPEEDY.pos:SPEEDY.neg}}>
              {market.yesChange>=0?"▲":"▼"} {Math.abs(market.yesChange*100).toFixed(0)}¢
            </span>
            <span style={{fontSize:10,color:SPEEDY.textFaint,marginLeft:"auto"}}>vol {market.volume}</span>
          </>:<>
            <span style={{fontSize:22,fontWeight:600,letterSpacing:"-0.01em"}}>${fmtPrice(market.price)}</span>
            <span style={{fontSize:11,color:market.change>=0?SPEEDY.pos:SPEEDY.neg}}>
              {market.change>=0?"▲":"▼"} {fmtPct(market.changePct)}
            </span>
          </>}
        </div>
        {showSwap&&(
          <div style={{position:"absolute",top:"calc(100% + 4px)",left:8,right:8,
            background:SPEEDY.surfaceSolid,border:`0.5px solid ${SPEEDY.borderStrong}`,
            borderRadius:10,boxShadow:`0 12px 32px rgba(0,0,0,0.5)`,padding:4,zIndex:5}}>
            {alternates.map(alt=>(
              <button key={alt.id} onClick={()=>{onSwap(alt);setShowSwap(false);}} style={{
                appearance:"none",border:0,
                background:alt.id===market.id?`${SPEEDY.accent}30`:"transparent",
                color:SPEEDY.text,padding:"7px 8px",width:"100%",textAlign:"left",
                borderRadius:6,cursor:"pointer",display:"flex",alignItems:"center",gap:8,
                fontFamily:"inherit",fontSize:12}}>
                <MarketTypeBadge type={alt.type} small/>
                <span style={{fontWeight:500}}>{alt.ticker||""}</span>
                <span style={{color:SPEEDY.textSoft,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{alt.title}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {stage==="entry"&&(
        <div style={{padding:"12px 14px"}}>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:6,
            background:"rgba(255,255,255,0.05)",padding:3,borderRadius:9}}>
            {sideOpts.map(opt=>(
              <button key={opt.v} onClick={()=>setSide(opt.v)} style={{
                appearance:"none",border:0,
                background:side===opt.v?opt.color:"transparent",
                color:side===opt.v?"#0e0e10":SPEEDY.textSoft,
                padding:"8px 10px",borderRadius:6,cursor:"pointer",
                fontFamily:"inherit",fontSize:12.5,fontWeight:600,
                letterSpacing:"-0.005em",transition:"all 0.12s"}}>{opt.label}</button>
            ))}
          </div>
          <div style={{marginTop:12}}>
            <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",
              fontSize:10.5,color:SPEEDY.textSoft,
              textTransform:"uppercase",letterSpacing:"0.06em",fontWeight:500,marginBottom:6}}>
              <span>Size</span>
              <span style={{fontFamily:"'JetBrains Mono',monospace",color:SPEEDY.textFaint,textTransform:"none",letterSpacing:0}}>≈ {shares} {isPred?"shares":"sh"}</span>
            </div>
            <div style={{display:"flex",alignItems:"center",
              border:`0.5px solid ${SPEEDY.border}`,borderRadius:9,
              background:"rgba(0,0,0,0.25)",padding:"0 10px"}}>
              <span style={{color:SPEEDY.textFaint,fontSize:14,fontFamily:"'JetBrains Mono',monospace"}}>$</span>
              <input type="number" value={size} onChange={e=>setSize(Number(e.target.value)||0)}
                style={{appearance:"none",border:0,background:"transparent",flex:1,padding:"8px 6px",outline:"none",
                  color:SPEEDY.text,fontFamily:"'JetBrains Mono',monospace",fontSize:16,fontWeight:600,letterSpacing:"-0.01em"}}/>
            </div>
            <div style={{display:"flex",gap:4,marginTop:6}}>
              {[25,100,500,1000].map(s=>(
                <button key={s} onClick={()=>setSize(s)} style={{
                  appearance:"none",border:`0.5px solid ${SPEEDY.border}`,
                  background:size===s?SPEEDY.text:"transparent",
                  color:size===s?SPEEDY.ink:SPEEDY.textSoft,
                  padding:"5px 8px",borderRadius:6,cursor:"pointer",
                  fontFamily:"'JetBrains Mono',monospace",fontSize:11,fontWeight:500,flex:1}}>${s}</button>
              ))}
            </div>
          </div>
          <button onClick={submit} style={{
            marginTop:12,appearance:"none",border:0,width:"100%",
            background:sideColor,color:"#0e0e10",padding:"11px 14px",borderRadius:9,
            fontFamily:"inherit",fontSize:13,fontWeight:600,letterSpacing:"-0.01em",cursor:"pointer",
            display:"flex",alignItems:"center",justifyContent:"center",gap:6,transition:"filter 0.1s"}}
            onMouseEnter={e=>e.target.style.filter="brightness(1.08)"}
            onMouseLeave={e=>e.target.style.filter="brightness(1)"}>
            <span>{sideOpts.find(s=>s.v===side)?.label.split(" ")[0]} ${size}</span>
            <span style={{opacity:0.55,fontSize:11}}>⌘⏎</span>
          </button>
        </div>
      )}

      {stage==="confirming"&&(
        <div style={{padding:"36px 14px",textAlign:"center"}}>
          <div style={{width:28,height:28,borderRadius:"50%",
            border:`2px solid ${SPEEDY.border}`,borderTopColor:sideColor,
            animation:"spin 0.7s linear infinite",margin:"0 auto 10px"}}/>
          <div style={{fontSize:12,color:SPEEDY.textSoft,fontFamily:"'JetBrains Mono',monospace"}}>routing order…</div>
        </div>
      )}

      {stage==="done"&&(
        <div style={{padding:"26px 14px",textAlign:"center"}}>
          <div style={{width:34,height:34,borderRadius:"50%",
            background:`${SPEEDY.pos}25`,display:"flex",alignItems:"center",justifyContent:"center",margin:"0 auto 10px"}}>
            <svg width="17" height="17" viewBox="0 0 16 16" fill="none">
              <path d="M3 8.5l3.5 3.5L13 5" stroke={SPEEDY.pos} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div style={{fontSize:13,fontWeight:600,marginBottom:2}}>Filled</div>
          <div style={{fontSize:11,color:SPEEDY.textSoft,fontFamily:"'JetBrains Mono',monospace"}}>
            {sideOpts.find(s=>s.v===side)?.label.split(" ")[0]} ${size} · {market.ticker||market.title.slice(0,20)}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Kbd pill ────────────────────────────────────────────────────────────────
function Kbd({children}){
  return <span style={{
    display:"inline-flex",alignItems:"center",justifyContent:"center",
    minWidth:18,height:18,padding:"0 5px",
    background:"rgba(255,255,255,0.14)",
    border:"0.5px solid rgba(255,255,255,0.22)",
    borderRadius:4,
    fontFamily:"'JetBrains Mono',monospace",fontSize:10.5,fontWeight:600,
    color:"#fff",lineHeight:1,
    boxShadow:"inset 0 -1px 0 rgba(0,0,0,0.18)",
  }}>{children}</span>;
}

// ─── Speedy mark ─────────────────────────────────────────────────────────────
function SpeedyMark({size=14}){
  return (
    <div style={{
      width:size,height:size,borderRadius:size*0.28,
      background:SPEEDY.accent,
      display:"flex",alignItems:"center",justifyContent:"center",
      color:"#0e0e10",fontWeight:800,fontSize:size*0.62,
      fontFamily:"'JetBrains Mono',monospace",
      boxShadow:`0 0 0 0.5px rgba(0,0,0,0.3), 0 1px 2px rgba(0,0,0,0.3)`,
    }}>S</div>
  );
}

// ─── Trigger styles (system-overlay versions) ────────────────────────────────
function TriggerChip({market,anchor,onOpen}){
  const x=(anchor.end?.right||0)+8;
  const y=(anchor.end?.top||0)-4;
  return (
    <div data-speedy style={{position:"fixed",left:x,top:y,zIndex:99999,
      animation:"chipIn 0.16s cubic-bezier(0.2,0.9,0.3,1.2) backwards"}}>
      <button onClick={onOpen} style={{
        appearance:"none",border:0,
        background:SPEEDY.surfaceSolid,color:SPEEDY.text,
        padding:"6px 10px 6px 6px",borderRadius:999,cursor:"pointer",
        display:"flex",alignItems:"center",gap:7,
        fontFamily:"'Inter',sans-serif",fontSize:12,fontWeight:500,
        boxShadow:`0 6px 18px rgba(0,0,0,0.4), 0 0 0 0.5px ${SPEEDY.borderStrong}`,
      }}>
        <SpeedyMark size={18}/>
        <span style={{fontFamily:"'JetBrains Mono',monospace",fontSize:11}}>
          trade {market.ticker||market.title.slice(0,16)}
        </span>
        <span style={{fontSize:10,color:SPEEDY.textFaint,fontFamily:"'JetBrains Mono',monospace",
          padding:"1px 5px",border:`0.5px solid ${SPEEDY.border}`,borderRadius:4,marginLeft:2}}>⏎</span>
      </button>
    </div>
  );
}

function TriggerPopover({market,anchor,onClose,onSwap,alternates}){
  const endRight=anchor.end?.right||0;
  const endTop=anchor.end?.bottom||0;
  const W=300;
  let x=endRight-60;
  if(x+W>window.innerWidth-16) x=window.innerWidth-W-16;
  if(x<16) x=16;
  const y=endTop+10;
  return (
    <div data-speedy style={{position:"fixed",left:x,top:y,zIndex:99999,
      animation:"popIn 0.22s cubic-bezier(0.2,0.9,0.3,1.05) backwards"}}>
      <TradePanel market={market} onClose={onClose} onSwap={onSwap} alternates={alternates}/>
    </div>
  );
}

function TriggerCursorBadge({market,anchor,onOpen}){
  const x=(anchor.mouseX||0)+14;
  const y=(anchor.mouseY||0)+14;
  const isPred=market.type==="prediction";
  return (
    <div data-speedy style={{position:"fixed",left:x,top:y,zIndex:99999,
      animation:"cursorIn 0.18s cubic-bezier(0.2,0.9,0.3,1) backwards"}}>
      <div style={{display:"flex",flexDirection:"column",alignItems:"flex-start"}}>
        <div style={{width:1,height:8,background:SPEEDY.accent,marginLeft:10,opacity:0.5}}/>
        <button onClick={onOpen} style={{
          appearance:"none",padding:0,
          background:SPEEDY.surfaceSolid,
          border:`0.5px solid ${SPEEDY.borderStrong}`,
          borderLeft:`2px solid ${SPEEDY.accent}`,
          borderRadius:8,cursor:"pointer",textAlign:"left",
          boxShadow:`0 8px 22px rgba(0,0,0,0.4)`,
          minWidth:150,padding:"7px 11px",
          display:"flex",flexDirection:"column",gap:2,
        }}>
          <div style={{display:"flex",alignItems:"center",gap:5,fontSize:9,color:SPEEDY.textFaint,
            fontFamily:"'JetBrains Mono',monospace",letterSpacing:"0.06em",textTransform:"uppercase"}}>
            <span style={{width:5,height:5,borderRadius:"50%",background:SPEEDY.accent}}/>
            <span>speedy · detected</span>
          </div>
          <div style={{fontFamily:"'Inter',sans-serif",fontSize:12.5,fontWeight:600,color:SPEEDY.text}}>
            {market.ticker||market.title.slice(0,24)}
          </div>
          <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:10.5,
            color:isPred?SPEEDY.text:(market.change>=0?SPEEDY.pos:SPEEDY.neg)}}>
            {isPred?`${fmtCents(market.yesPrice)} yes`:`$${fmtPrice(market.price)} ${fmtPct(market.changePct)}`}
          </div>
          <div style={{marginTop:3,fontSize:9.5,color:SPEEDY.textSoft,fontFamily:"'JetBrains Mono',monospace"}}>tap to trade ↵</div>
        </button>
      </div>
    </div>
  );
}

// ─── Host apps (the user's actual computer) ──────────────────────────────────
const ARTICLE_BODY=[
  "Federal Reserve Chair Jerome Powell told reporters Thursday that the central bank remains \"meaningfully data-dependent\" heading into its May 7 meeting, leaving traders to parse mixed signals about whether policymakers will deliver the rate cut markets have been pricing in for weeks.",
  "Speaking after a panel at the IMF spring meetings, Powell stopped short of guiding expectations in either direction. \"We have time, and we intend to use it.\" The remarks landed in a market already nervous about Friday's PCE print.",
  "Prediction markets immediately pulled back. The probability of a May rate cut, which had pushed above 70% on Tuesday, slid to the low 60s in afternoon trading. Two-year Treasury yields rose four basis points; the dollar firmed against most G10 peers.",
  "Equities were less sure what to do with it. The S&P 500 closed roughly flat. Nvidia gave back early gains to finish modestly lower, while gold extended its run, settling above $2,700 an ounce for the third straight session.",
  "Crypto, as ever, marched to its own drum. Bitcoin pushed back through $71,000 in the hours after Powell's remarks, with traders citing the prospect of looser policy as a tailwind. Ether tracked higher in sympathy.",
];

function BrowserApp({active}){
  return (
    <AppFrame active={active} appId="browser" title="The Ledger">
      {/* Browser chrome */}
      <div style={{padding:"8px 10px",borderBottom:"0.5px solid rgba(0,0,0,0.08)",
        display:"flex",alignItems:"center",gap:8,background:"#fafaf7",flexShrink:0}}>
        <div style={{display:"flex",gap:4}}>
          {["#ff5f57","#febc2e","#28c840"].map(c=>(
            <div key={c} style={{width:11,height:11,borderRadius:"50%",background:c,
              border:"0.5px solid rgba(0,0,0,0.08)"}}/>
          ))}
        </div>
        <div style={{display:"flex",gap:3,marginLeft:6,color:"rgba(0,0,0,0.4)"}}>
          <span style={{fontSize:14}}>‹</span><span style={{fontSize:14}}>›</span>
        </div>
        <div style={{flex:1,height:24,background:"#fff",border:"0.5px solid rgba(0,0,0,0.1)",
          borderRadius:6,display:"flex",alignItems:"center",padding:"0 10px",
          fontSize:11,color:"rgba(0,0,0,0.55)",fontFamily:"'JetBrains Mono',monospace"}}>
          <span style={{opacity:0.5,marginRight:4}}>🔒</span>theledger.com/markets/powell-may-fed
        </div>
      </div>

      {/* Article */}
      <div data-host-app="browser" style={{
        padding:"40px 56px 60px",overflow:"auto",flex:1,background:"#fffdf7",
        cursor:"text",
      }}>
        <div style={{maxWidth:560,margin:"0 auto"}}>
          <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:10,
            letterSpacing:"0.12em",color:"oklch(0.55 0.20 25)",textTransform:"uppercase",fontWeight:600,marginBottom:14}}>
            MARKETS · MONETARY POLICY
          </div>
          <h1 style={{fontFamily:"'Source Serif 4',Georgia,serif",fontSize:30,fontWeight:600,
            lineHeight:1.12,letterSpacing:"-0.02em",margin:"0 0 14px",color:"#1a1814",textWrap:"balance"}}>
            Powell signals patience as Fed weighs May rate decision
          </h1>
          <div style={{display:"flex",gap:8,fontFamily:"'Inter',sans-serif",fontSize:11.5,
            color:"rgba(26,24,20,0.62)",marginBottom:24,paddingBottom:12,
            borderBottom:"0.5px solid rgba(0,0,0,0.1)"}}>
            <span style={{fontWeight:500,color:"#1a1814"}}>Maya Chen</span>
            <span style={{color:"rgba(0,0,0,0.3)"}}>·</span>
            <span>April 24, 2026 · 4 min read</span>
          </div>
          {ARTICLE_BODY.map((p,i)=>(
            <p key={i} style={{fontFamily:"'Source Serif 4',Georgia,serif",
              fontSize:15,lineHeight:1.65,margin:"0 0 16px",color:"#1a1814",textWrap:"pretty"}}>{p}</p>
          ))}
        </div>
      </div>
    </AppFrame>
  );
}

function MessagesApp({active}){
  const messages=[
    {from:"Sam",me:false,text:"did u see the powell presser",time:"3:42 PM"},
    {from:"me",me:true,text:"yeah lol \"we have time\"",time:"3:43 PM"},
    {from:"Sam",me:false,text:"polymarket already moved. May cut probability dropped from 71 → 62 in like 20 mins",time:"3:43 PM"},
    {from:"Sam",me:false,text:"NVDA tanked too, btc up tho",time:"3:44 PM"},
    {from:"me",me:true,text:"yeah I'm thinking gold runs more here",time:"3:45 PM"},
    {from:"Sam",me:false,text:"degen. fade the Fed and just buy gold",time:"3:45 PM"},
  ];
  return (
    <AppFrame active={active} appId="messages" title="Messages">
      <div style={{padding:"10px 14px",borderBottom:"0.5px solid rgba(0,0,0,0.08)",
        background:"#f5f5f7",fontSize:13,fontWeight:600,color:"#1a1814",flexShrink:0,
        display:"flex",alignItems:"center",gap:8}}>
        <div style={{width:24,height:24,borderRadius:"50%",
          background:"linear-gradient(135deg, oklch(0.7 0.18 50), oklch(0.62 0.22 295))"}}/>
        <span>Sam</span>
      </div>
      <div data-host-app="messages" style={{padding:"16px 14px",overflow:"auto",flex:1,
        background:"#fff",cursor:"text",display:"flex",flexDirection:"column",gap:8}}>
        {messages.map((m,i)=>(
          <div key={i} style={{display:"flex",justifyContent:m.me?"flex-end":"flex-start"}}>
            <div style={{
              maxWidth:"75%",padding:"7px 11px",borderRadius:14,
              background:m.me?"#007aff":"#e9e9eb",color:m.me?"#fff":"#1a1814",
              fontFamily:"-apple-system,sans-serif",fontSize:13.5,lineHeight:1.35,
            }}>{m.text}</div>
          </div>
        ))}
      </div>
    </AppFrame>
  );
}

function NotesApp({active}){
  return (
    <AppFrame active={active} appId="notes" title="Notes">
      <div style={{padding:"8px 14px",borderBottom:"0.5px solid rgba(0,0,0,0.08)",
        background:"#fffce8",fontSize:11,color:"rgba(0,0,0,0.5)",flexShrink:0,
        fontFamily:"-apple-system,sans-serif"}}>April 24, 2026 · 3:51 PM</div>
      <div data-host-app="notes" style={{padding:"22px 28px",overflow:"auto",flex:1,
        background:"#fffce8",cursor:"text"}}>
        <h2 style={{fontFamily:"-apple-system,sans-serif",fontSize:17,fontWeight:700,
          margin:"0 0 12px",color:"#1a1814"}}>thoughts post-Powell</h2>
        <ul style={{fontFamily:"-apple-system,sans-serif",fontSize:13.5,lineHeight:1.6,
          color:"#1a1814",paddingLeft:18,margin:0}}>
          <li style={{marginBottom:6}}>"data-dependent" = no commitment. May rate cut feels less certain</li>
          <li style={{marginBottom:6}}>polymarket already at 62¢ on Yes — fair value or overshoot?</li>
          <li style={{marginBottom:6}}>gold continues to be the trade if real yields stall</li>
          <li style={{marginBottom:6}}>NVDA weakness might be more about chip cycle than rates tbh</li>
          <li style={{marginBottom:6}}>bitcoin shrugged it off — ETH followed</li>
          <li style={{marginBottom:6}}>watch DXY for confirmation, dollar firmed today but limited</li>
        </ul>
      </div>
    </AppFrame>
  );
}

function AppFrame({active,appId,title,children}){
  return (
    <div style={{
      width:"100%",height:"100%",
      background:"#fff",borderRadius:11,overflow:"hidden",
      boxShadow:active
        ?"0 0 0 0.5px rgba(0,0,0,0.18), 0 24px 56px rgba(0,0,0,0.32), 0 8px 20px rgba(0,0,0,0.18)"
        :"0 0 0 0.5px rgba(0,0,0,0.14), 0 8px 24px rgba(0,0,0,0.22)",
      display:"flex",flexDirection:"column",
      transition:"box-shadow 0.2s, transform 0.2s, opacity 0.2s",
      opacity:active?1:0.92,
    }}>
      {children}
    </div>
  );
}

// ─── Menu bar (system chrome) ────────────────────────────────────────────────
function MenuBar({activeApp}){
  const appNames={browser:"Safari",messages:"Messages",notes:"Notes"};
  const [time,setTime]=React.useState("");
  React.useEffect(()=>{
    const tick=()=>{
      const d=new Date();
      const h=d.getHours()%12||12;
      const m=String(d.getMinutes()).padStart(2,"0");
      const ap=d.getHours()>=12?"PM":"AM";
      setTime(`${h}:${m} ${ap}`);
    };
    tick(); const id=setInterval(tick,30000); return ()=>clearInterval(id);
  },[]);
  return (
    <div style={{
      position:"fixed",top:0,left:0,right:0,height:26,zIndex:90,
      background:"rgba(0,0,0,0.32)",
      backdropFilter:"blur(20px) saturate(160%)",
      WebkitBackdropFilter:"blur(20px) saturate(160%)",
      display:"flex",alignItems:"center",
      padding:"0 14px",
      fontFamily:"-apple-system,sans-serif",fontSize:13,color:"#fff",
      borderBottom:"0.5px solid rgba(255,255,255,0.08)",
    }}>
      <span style={{fontSize:14,marginRight:14}}></span>
      <span style={{fontWeight:700,marginRight:18}}>{appNames[activeApp]||"Finder"}</span>
      <span style={{opacity:0.85,marginRight:14}}>File</span>
      <span style={{opacity:0.85,marginRight:14}}>Edit</span>
      <span style={{opacity:0.85,marginRight:14}}>View</span>
      <span style={{opacity:0.85}}>Window</span>
      <div style={{flex:1}}/>
      {/* Speedy menu bar item — the bold idea: it's always here */}
      <div style={{display:"flex",alignItems:"center",gap:5,marginRight:16,
        padding:"2px 7px",borderRadius:5,
        background:"rgba(255,255,255,0.08)",
        border:"0.5px solid rgba(255,255,255,0.12)",
        fontFamily:"'JetBrains Mono',monospace",fontSize:10.5,letterSpacing:"0.04em"}}>
        <SpeedyMark size={11}/>
        <span style={{opacity:0.85}}>SPEEDY</span>
        <span style={{opacity:0.5,marginLeft:4}}>·</span>
        <span style={{opacity:0.7}}>⌃ to trade</span>
      </div>
      <span style={{opacity:0.85,marginRight:12,fontFamily:"'JetBrains Mono',monospace",fontSize:11}}>$4,820.16</span>
      <span style={{opacity:0.85,fontFamily:"-apple-system,sans-serif"}}>{time}</span>
    </div>
  );
}

// ─── Dock ────────────────────────────────────────────────────────────────────
function Dock({activeApp,onPick}){
  const apps=[
    {id:"browser",label:"Safari",color:"linear-gradient(160deg, #4ba3ff, #0066cc)",glyph:"S"},
    {id:"messages",label:"Messages",color:"linear-gradient(160deg, #5dd968, #1e9533)",glyph:"💬"},
    {id:"notes",label:"Notes",color:"linear-gradient(160deg, #ffe27a, #f5b800)",glyph:"📝"},
  ];
  return (
    <div style={{
      position:"fixed",bottom:8,left:"50%",transform:"translateX(-50%)",
      display:"flex",gap:8,padding:"8px 10px",zIndex:80,
      background:"rgba(255,255,255,0.16)",
      backdropFilter:"blur(30px) saturate(180%)",
      WebkitBackdropFilter:"blur(30px) saturate(180%)",
      border:"0.5px solid rgba(255,255,255,0.18)",
      borderRadius:18,
      boxShadow:"0 12px 30px rgba(0,0,0,0.3)",
    }}>
      {apps.map(a=>(
        <button key={a.id} onClick={()=>onPick(a.id)} style={{
          appearance:"none",border:0,padding:0,cursor:"pointer",
          width:44,height:44,borderRadius:10,background:a.color,
          display:"flex",alignItems:"center",justifyContent:"center",
          color:"#fff",fontWeight:700,fontSize:20,
          boxShadow:activeApp===a.id?"0 6px 14px rgba(0,0,0,0.3), 0 0 0 1.5px rgba(255,255,255,0.4)":"0 4px 10px rgba(0,0,0,0.25)",
          transform:activeApp===a.id?"translateY(-2px)":"none",
          transition:"all 0.15s",
          fontFamily:"-apple-system,sans-serif",
        }}>{a.glyph}</button>
      ))}
      <div style={{width:1,background:"rgba(255,255,255,0.2)",margin:"4px 2px"}}/>
      <div style={{
        width:44,height:44,borderRadius:10,background:SPEEDY.accent,
        display:"flex",alignItems:"center",justifyContent:"center",
        color:"#0e0e10",fontWeight:800,fontSize:22,
        fontFamily:"'JetBrains Mono',monospace",
        boxShadow:"0 4px 10px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.3)",
      }}>S</div>
    </div>
  );
}

// ─── App ─────────────────────────────────────────────────────────────────────
function App(){
  const [t,setTweak]=useTweaks(TWEAK_DEFAULTS);
  const desktopRef=React.useRef(null);

  // Hotkey state
  const [hotkeyHeld,setHotkeyHeld]=React.useState(false);
  const [armed,setArmed]=React.useState(false); // for "arm" mode
  const [showHotkeyHint,setShowHotkeyHint]=React.useState(false);

  // isArmed: returns true if Speedy should activate for the current selection
  const isArmedRef=React.useRef(()=>false);
  isArmedRef.current=(e)=>{
    if(t.alwaysOn) return true;
    if(t.hotkeyMode==="hold") return e?.ctrlKey||hotkeyHeld;
    // "arm" mode: must have pressed hotkey beforehand
    return armed;
  };

  React.useEffect(()=>{
    const onDown=(e)=>{
      if(e.key===HOTKEY_NAME||e.ctrlKey){
        if(!hotkeyHeld) setHotkeyHeld(true);
      }
      if(e.key===" "&&e.ctrlKey&&t.hotkeyMode==="arm"){
        e.preventDefault(); setArmed(a=>!a);
      }
    };
    const onUp=(e)=>{
      if(e.key===HOTKEY_NAME) setHotkeyHeld(false);
    };
    window.addEventListener("keydown",onDown);
    window.addEventListener("keyup",onUp);
    return ()=>{window.removeEventListener("keydown",onDown);window.removeEventListener("keyup",onUp);};
  },[hotkeyHeld,t.hotkeyMode]);

  const [sel,clearSel]=useSystemSelection(desktopRef,isArmedRef);
  const [chipExpanded,setChipExpanded]=React.useState(false);
  const [overrideMarket,setOverrideMarket]=React.useState(null);

  // After Speedy fires, disarm (one-shot in arm mode)
  React.useEffect(()=>{
    if(sel.text&&t.hotkeyMode==="arm") setArmed(false);
  },[sel.text,t.hotkeyMode]);

  React.useEffect(()=>{setChipExpanded(false);setOverrideMarket(null);},[sel.text]);

  const matched=sel.text?matchMarket(sel.text,t.marketType):null;
  const market=overrideMarket||matched;
  const alternates=sel.text?allMatches(sel.text,t.marketType):[];

  React.useEffect(()=>{
    const onKey=(e)=>{
      if(e.key==="Escape") clearSel();
      if(e.key==="Enter"&&sel.text&&market&&t.triggerStyle==="chip"&&!chipExpanded){
        e.preventDefault(); setChipExpanded(true);
      }
    };
    window.addEventListener("keydown",onKey);
    return ()=>window.removeEventListener("keydown",onKey);
  },[sel.text,market,t.triggerStyle,chipExpanded,clearSel]);

  React.useEffect(()=>{
    let s=document.getElementById("__sel");
    if(!s){s=document.createElement("style");s.id="__sel";document.head.appendChild(s);}
    s.textContent=`::selection{background:${SPEEDY.selBg};color:#0e0e10;}`;
  },[]);

  const showTrigger=sel.text&&market&&!sel.isSelecting;

  return (
    <div ref={desktopRef} style={{
      width:"100vw",height:"100vh",overflow:"hidden",position:"relative",
      background:WALLPAPERS[t.wallpaper]||WALLPAPERS.dawn,
      fontFamily:"-apple-system,'Inter',sans-serif",
    }}>
      <MenuBar activeApp={t.activeApp}/>

      {/* Desktop — 3 windows arranged */}
      <div style={{position:"absolute",inset:"26px 0 0 0"}}>
        {/* Browser — primary */}
        <div style={{position:"absolute",
          left:"50%",top:"50%",transform:"translate(-50%,-50%)",
          width:780,height:560,
          zIndex:t.activeApp==="browser"?30:10,
          opacity:1,
          transition:"all 0.25s cubic-bezier(0.3,0.9,0.4,1)",
        }} onMouseDownCapture={()=>setTweak("activeApp","browser")}>
          <BrowserApp active={t.activeApp==="browser"}/>
        </div>
        {/* Messages — peeks from left */}
        <div style={{position:"absolute",
          left:24,top:60,
          width:380,height:430,
          zIndex:t.activeApp==="messages"?30:11,
          transform:t.activeApp==="messages"?"none":"rotate(-1.5deg)",
          transition:"all 0.25s cubic-bezier(0.3,0.9,0.4,1)",
        }} onMouseDownCapture={()=>setTweak("activeApp","messages")}>
          <MessagesApp active={t.activeApp==="messages"}/>
        </div>
        {/* Notes — peeks from right */}
        <div style={{position:"absolute",
          right:32,bottom:90,
          width:340,height:380,
          zIndex:t.activeApp==="notes"?30:12,
          transform:t.activeApp==="notes"?"none":"rotate(1.2deg)",
          transition:"all 0.25s cubic-bezier(0.3,0.9,0.4,1)",
        }} onMouseDownCapture={()=>setTweak("activeApp","notes")}>
          <NotesApp active={t.activeApp==="notes"}/>
        </div>
      </div>

      <Dock activeApp={t.activeApp} onPick={(id)=>setTweak("activeApp",id)}/>

      {/* No-match feedback */}
      {sel.text&&!market&&!sel.isSelecting&&(
        <div data-speedy style={{position:"fixed",
          left:(sel.rect?.end?.right||100)+8,top:(sel.rect?.end?.top||100)-4,zIndex:99999,
          background:SPEEDY.surfaceSolid,color:SPEEDY.textSoft,
          border:`0.5px solid ${SPEEDY.borderStrong}`,
          padding:"6px 10px",borderRadius:8,
          fontFamily:"'JetBrains Mono',monospace",fontSize:11,
          animation:"chipIn 0.15s ease-out backwards",
          boxShadow:"0 6px 16px rgba(0,0,0,0.35)",
          display:"flex",alignItems:"center",gap:6,
        }}>
          <SpeedyMark size={11}/>
          <span>no market match</span>
        </div>
      )}

      {/* Live ticker tail during drag — only when armed */}
      {t.showTickerTail&&sel.isSelecting&&sel.liveText&&sel.armed&&(
        <TickerTail liveText={sel.liveText} liveRect={sel.liveRect}/>
      )}

      {/* Triggers */}
      {showTrigger&&t.triggerStyle==="chip"&&!chipExpanded&&(
        <TriggerChip market={market} anchor={sel.rect} onOpen={()=>setChipExpanded(true)}/>
      )}
      {showTrigger&&t.triggerStyle==="chip"&&chipExpanded&&(
        <TriggerPopover market={market} anchor={sel.rect} alternates={alternates}
          onSwap={(m)=>setOverrideMarket(m)} onClose={clearSel}/>
      )}
      {showTrigger&&t.triggerStyle==="popover"&&(
        <TriggerPopover market={market} anchor={sel.rect} alternates={alternates}
          onSwap={(m)=>setOverrideMarket(m)} onClose={clearSel}/>
      )}
      {showTrigger&&t.triggerStyle==="cursor"&&!chipExpanded&&(
        <TriggerCursorBadge market={market} anchor={sel.rect} onOpen={()=>setChipExpanded(true)}/>
      )}
      {showTrigger&&t.triggerStyle==="cursor"&&chipExpanded&&(
        <TriggerPopover market={market} anchor={sel.rect} alternates={alternates}
          onSwap={(m)=>setOverrideMarket(m)} onClose={clearSel}/>
      )}

      {/* Hint pill — first-load instructions */}
      {!sel.text&&!sel.isSelecting&&(
        <div data-speedy style={{
          position:"fixed",top:42,left:"50%",transform:"translateX(-50%)",zIndex:80,
          padding:"8px 14px",
          background:"rgba(0,0,0,0.46)",
          backdropFilter:"blur(20px)",
          WebkitBackdropFilter:"blur(20px)",
          border:"0.5px solid rgba(255,255,255,0.12)",
          borderRadius:999,
          fontFamily:"'JetBrains Mono',monospace",fontSize:11,color:"rgba(255,255,255,0.85)",
          display:"flex",alignItems:"center",gap:10,
          boxShadow:"0 6px 18px rgba(0,0,0,0.25)",
          animation:"chipIn 0.4s ease-out backwards",
        }}>
          <SpeedyMark size={12}/>
          {t.alwaysOn?(
            <span>highlight any text — Speedy is always on</span>
          ):t.hotkeyMode==="hold"?(
            <><span>hold</span><Kbd>{HOTKEY_LABEL}</Kbd><span>and highlight any text</span></>
          ):(
            <><span>press</span><Kbd>{HOTKEY_LABEL}</Kbd><Kbd>Space</Kbd><span>to arm, then highlight</span></>
          )}
        </div>
      )}

      {/* Live armed indicator — shows when hotkey is held or Speedy is armed */}
      {(hotkeyHeld||(armed&&t.hotkeyMode==="arm"))&&!sel.text&&(
        <div data-speedy style={{
          position:"fixed",top:42,left:"50%",transform:"translateX(-50%)",zIndex:81,
          padding:"8px 14px",
          background:SPEEDY.accent,color:"#0e0e10",
          borderRadius:999,
          fontFamily:"'JetBrains Mono',monospace",fontSize:11,fontWeight:600,letterSpacing:"0.04em",
          display:"flex",alignItems:"center",gap:8,
          boxShadow:"0 6px 22px rgba(0,0,0,0.35), 0 0 0 0.5px rgba(0,0,0,0.2)",
          animation:"chipIn 0.15s ease-out backwards",
        }}>
          <span style={{width:6,height:6,borderRadius:"50%",background:"#0e0e10",animation:"pulse 1.2s infinite"}}/>
          <span>SPEEDY ARMED · highlight to trade</span>
        </div>
      )}

      <TweaksPanel title="Tweaks">
        <TweakSection label="Activation"/>
        <TweakRadio label="Hotkey mode" value={t.alwaysOn?"off":t.hotkeyMode}
          options={[{value:"hold",label:"Hold ⌃"},{value:"arm",label:"⌃Space"},{value:"off",label:"Always"}]}
          onChange={v=>{
            if(v==="off"){setTweak("alwaysOn",true);}
            else{setTweak("alwaysOn",false);setTweak("hotkeyMode",v);}
          }}/>

        <TweakSection label="Speedy trigger"/>
        <TweakRadio label="On highlight" value={t.triggerStyle}
          options={[{value:"chip",label:"Chip"},{value:"popover",label:"Popover"},{value:"cursor",label:"Cursor"}]}
          onChange={v=>setTweak("triggerStyle",v)}/>
        <TweakToggle label="Live ticker tail (drag)" value={t.showTickerTail}
          onChange={v=>setTweak("showTickerTail",v)}/>

        <TweakSection label="Market filter"/>
        <TweakSelect label="Type" value={t.marketType}
          options={[
            {value:"auto",label:"Auto (any)"},
            {value:"prediction",label:"Prediction only"},
            {value:"stock",label:"Stocks only"},
            {value:"perp",label:"Perps only"},
            {value:"commodity",label:"Commodities only"},
          ]} onChange={v=>setTweak("marketType",v)}/>

        <TweakSection label="Desktop"/>
        <TweakRadio label="Active app" value={t.activeApp}
          options={[{value:"browser",label:"Browser"},{value:"messages",label:"Messages"},{value:"notes",label:"Notes"}]}
          onChange={v=>setTweak("activeApp",v)}/>
        <TweakRadio label="Wallpaper" value={t.wallpaper}
          options={[{value:"dawn",label:"Dawn"},{value:"dusk",label:"Dusk"},{value:"graphite",label:"Graphite"}]}
          onChange={v=>setTweak("wallpaper",v)}/>
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
