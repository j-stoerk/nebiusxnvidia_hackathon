// Original, time-based canvas animation. All charts use the checked fixture.
// Media is separate from main's source history and included on gh-pages.
const canvas = document.querySelector('#film');
const ctx = canvas.getContext('2d');
const voice = document.querySelector('#voice');
const live = document.querySelector('#live');
const play = document.querySelector('#play');
const seek = document.querySelector('#seek');
const clock = document.querySelector('#clock');
const C = { bg:'#0c1420', ink:'#edf3fa', muted:'#9bafc5', line:'#27384d', teal:'#61d5c0', blue:'#7ebaff', gold:'#f2cb75', red:'#ef9290' };
const [timeline, data] = await Promise.all(['timeline.json','scenario.json'].map(p => fetch(p).then(r => r.json())));
// Small local blobs make seeking reliable even on preview servers without ranges.
await Promise.all([voice,live].map(async element=>{
  const blob=await fetch(element.getAttribute('src')).then(r=>r.blob());
  const ready=new Promise(resolve=>element.addEventListener('loadeddata',resolve,{once:true}));
  element.preload='auto';element.src=URL.createObjectURL(blob);element.load();await ready;
}));
const duration = timeline.duration;
let manualTime = 0;
let recording = false;
let recorder;
let audioContext;
let audioDestination;
let previousScene = '';
const clamp = x => Math.max(0, Math.min(1,x));
const ease = x => { x=clamp(x); return x*x*(3-2*x); };
const lerp = (a,b,t) => a+(b-a)*t;
const stamp = t => `${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;

function text(value,x,y,size=28,color=C.ink,align='left',weight=400) {
  ctx.fillStyle=color; ctx.font=`${weight} ${size}px "Segoe UI",Arial,sans-serif`;
  ctx.textAlign=align; ctx.fillText(value,x,y); ctx.textAlign='left';
}
function line(x1,y1,x2,y2,color=C.line,width=2,dash=[]) {
  ctx.beginPath();ctx.setLineDash(dash);ctx.strokeStyle=color;ctx.lineWidth=width;
  ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([]);
}
function rect(x,y,w,h,color) {ctx.fillStyle=color;ctx.fillRect(x,y,w,h);}
function dot(x,y,r,color) {ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();}
function alpha(a,draw) {ctx.save();ctx.globalAlpha=clamp(a);draw();ctx.restore();}
function arrow(x1,y1,x2,y2,color=C.teal) {
  line(x1,y1,x2,y2,color,3);
  const a=Math.atan2(y2-y1,x2-x1);
  line(x2,y2,x2-14*Math.cos(a-.45),y2-14*Math.sin(a-.45),color,3);
  line(x2,y2,x2-14*Math.cos(a+.45),y2-14*Math.sin(a+.45),color,3);
}
function header(scene,index,t) {
  text('CHARGEWISE',80,65,22,C.teal,'left',600);
  text(`${String(index+1).padStart(2,'0')} / 09`,1520,65,19,C.muted,'right');
  alpha(ease(t/1.2),()=>text(scene.title,80,138,45,C.ink,'left',600));
  line(80,173,1520,173);
}
function footer(label='Synthetic four-van fixture · times UTC · EUR') {
  text(label,80,844,16,C.muted);text('Julius Störk · Talha · Umar Khan',1520,844,16,C.muted,'right');
}
function axes({x=180,y=690,w=1190,h=410,max=24,start=6,end=20}={}) {
  for(let kw=0;kw<=max;kw+=4){
    const py=y-kw/max*h;line(x,py,x+w,py);text(String(kw),x-22,py+7,19,C.muted,'right');
  }
  line(x,y,x+w,y,C.muted);line(x,y,x,y-h,C.muted);
  text('kW',x-48,y-h-28,21,C.muted);
  for(let hr=start;hr<=end;hr+=2){const px=x+(hr-start)/(end-start)*w;text(`${String(hr).padStart(2,'0')}:00`,px,y+38,19,C.muted,'center');}
  return {x,y,w,h,max,start,end};
}
function curve(values,box,color,progress=1,fill=false) {
  const {x,y,w,h,max}=box;const n=values.length;
  ctx.save();ctx.beginPath();ctx.rect(x-3,y-h-5,w*clamp(progress)+6,h+10);ctx.clip();
  ctx.beginPath();ctx.moveTo(x,y);
  values.forEach((v,i)=>{const py=y-v/max*h;ctx.lineTo(x+i/n*w,py);ctx.lineTo(x+(i+1)/n*w,py);});
  if(fill){ctx.lineTo(x+w,y);ctx.closePath();ctx.globalAlpha=.16;ctx.fillStyle=color;ctx.fill();ctx.globalAlpha=1;}
  else{ctx.strokeStyle=color;ctx.lineWidth=4;ctx.stroke();}
  ctx.restore();
}
function van(x,y,color,label,energy=18) {
  ctx.strokeStyle=color;ctx.lineWidth=3;ctx.strokeRect(x,y,130,59);
  ctx.strokeRect(x+130,y+15,42,44);dot(x+34,y+66,11,color);dot(x+143,y+66,11,color);
  text(label,x+86,y-24,23,C.ink,'center',600);text(`${energy} kWh`,x+86,y+115,22,color,'center');
}
function plug(x,y,label,color=C.blue) {
  ctx.strokeStyle=color;ctx.lineWidth=3;ctx.strokeRect(x,y,77,102);
  line(x+20,y+24,x+57,y+24,color,4);line(x+77,y+45,x+107,y+45,color,3);line(x+107,y+45,x+107,y+95,color,3);
  text(label,x+39,y+140,20,C.muted,'center');
}
function flow(x1,y1,x2,y2,t,color=C.teal) {
  line(x1,y1,x2,y2,C.line,3);
  for(let i=0;i<4;i++){const p=(t*.22+i/4)%1;dot(lerp(x1,x2,p),lerp(y1,y2,p),5,color);}
}
function problem(t) {
  alpha(ease(t/2),()=>{text('Ready by departure.',800,275,62,C.ink,'center',600);text('Using the connection you already have.',800,330,31,C.muted,'center');});
  plug(755,431,'Shared site');
  [300,1130].forEach((x,i)=>{van(x,490,i?C.gold:C.teal,i?'Afternoon vans':'Morning vans',i?48:36);flow(x+(i?0:172),515,i?832:755,475,t);});
  alpha(ease((t-6)/2),()=>text('A planning decision, before buying more infrastructure.',800,738,29,C.ink,'center'));
  footer('Planning simulation · no physical chargers controlled');
}
function roster(t) {
  const progress=ease((t-1)/3);
  [270,630,990,1350].forEach((x,i)=>alpha(ease((t-i*.5)/1.4),()=>van(x-86,315,i<2?C.teal:C.gold,`VAN-0${i+1}`,i<2?18:24)));
  plug(458,570,'CH-01 · 11 kW');plug(1065,570,'CH-02 · 11 kW');
  [356,716,1076,1436].forEach((x,i)=>flow(x-86,447,i%2?1103:496,570,progress*6+t,i<2?C.teal:C.gold));
  text('06:00–12:00',450,250,24,C.teal,'center');text('14:00–20:00',1170,250,24,C.gold,'center');
  alpha(ease((t-8)/2),()=>text('Fixed plugs   ·   90% efficiency   ·   battery & connector limits',800,768,27,C.muted,'center'));
  footer();
}
function area(t) {
  const b=axes({x:180,y:670,w:880,h:380,max:24,start:14,end:20});
  const morph=ease((t-4)/5);const high=[22,22,22,22,22,22,22,22,22,15.333333,0,0,0,0,0,0,0,0,0,0,0,0,0,0];
  // Both endpoints contain exactly 53 1/3 grid kWh; interpolation preserves area.
  const values=high.map(v=>lerp(v,80/9,morph));
  curve(values,b,C.teal,ease(t/3),true);curve(values,b,C.teal,ease(t/3));
  text('height × width',1170,350,30,C.muted,'center');text('= energy',1170,402,37,C.teal,'center',600);
  alpha(ease((t-5)/2),()=>{text('48 kWh',1170,516,44,C.gold,'center',600);text('battery energy',1170,551,23,C.muted,'center');text('÷ 0.90',1170,602,31,C.ink,'center');text('53.33 kWh',1170,658,40,C.teal,'center',600);});
  text('Same area. A lower peak.',620,765,31,C.ink,'center');footer();
}
function bound(t) {
  const b=axes({x:180,y:680,w:870,h:380,max:16,start:14,end:20});
  const power=lerp(4,80/9,ease((t-1)/6));
  curve(Array(24).fill(power),b,C.teal,1,true);curve(Array(24).fill(power),b,C.teal);
  const y=b.y-(80/9)/b.max*b.h;line(b.x,y,b.x+b.w,y,C.gold,2,[8,7]);
  text('53.33 kWh',1280,342,42,C.teal,'center',600);line(1158,365,1402,365,C.muted);
  text('6 hours',1280,413,35,C.ink,'center');
  alpha(ease((t-4)/3),()=>{text('8.89 kW',1280,508,57,C.gold,'center',600);text('minimum shared power',1280,553,23,C.muted,'center');});
  alpha(ease((t-10)/2),()=>{text('Feasible at the bound.',620,762,31,C.teal,'center');text('Allocations independently checked',1280,654,22,C.muted,'center');});
  footer('Afternoon energy bound · fixed two-port configuration · synthetic fixture');
}
function comparison(t) {
  const b=axes();const morph=ease((t-4)/5);
  const values=data.profile.baseline.map((v,i)=>lerp(v,data.profile.optimized[i],morph));
  curve(data.profile.baseline,b,C.red,1);ctx.save();ctx.globalAlpha=.12;curve(data.profile.baseline,b,C.red,1,true);ctx.restore();
  curve(values,b,C.teal,1,true);curve(values,b,C.teal);
  text('FCFS · EDF · LLF',220,230,26,C.red);text('22 kW',580,230,26,C.red,'left',600);
  text('OR-Tools',910,230,26,C.teal);text(`${lerp(22,80/9,morph).toFixed(2)} kW`,1270,230,31,C.teal,'left',600);
  alpha(ease((t-8)/2),()=>{text('59.6% lower peak',800,773,34,C.ink,'center',600);});
  footer('All four policies meet the same 84 battery kWh · identical physical constraints');
}
function cost(t) {
  const amount=ease((t-2)/5);const x=[480,1090];const scale=1.22;const base=712;
  const m=data.metrics;
  ['baseline','optimized'].forEach((key,i)=>{
    const v=m[key],d=v.demand_cost_eur*scale*amount,e=v.energy_cost_eur*scale*amount;
    rect(x[i]-120,base-d,240,d,C.blue);rect(x[i]-120,base-d-e,240,e,C.gold);
    text(`€${(v.cost_eur*amount).toFixed(2)}`,x[i],base-d-e-28,43,C.ink,'center',600);
    text(i?'Optimized':'FCFS / EDF / LLF',x[i],763,27,C.muted,'center');
  });
  rect(280,790,14,14,C.blue);text('Demand component',305,804,20,C.blue);
  rect(1000,790,14,14,C.gold);text('Energy component',1025,804,20,C.gold);
  alpha(ease((t-8)/3),()=>{text('€21.47 → €24.09',800,322,24,C.gold,'center');text('energy cost',800,354,20,C.muted,'center');text('€334.40 → €135.11',800,436,24,C.blue,'center');text('demand cost',800,468,20,C.muted,'center');});
  footer('Illustrative €15.20/kW/month · zero prior peak · partial-period calculation, not an annual bill');
}
function liveScene(t) {
  // Native 16:9 screen recording; no stretched or re-created application UI.
  if(live.readyState>=2)ctx.drawImage(live,0,0,1600,900);
  rect(790,8,790,35,C.bg);
  text('RECORDED LIVE · NVIDIA Nemotron on Nebius Token Factory',1560,33,18,C.teal,'right',600);
}
function forecast(t) {
  const vals=[.00704179,.00571989,.00498822];const labels=['Ridge baseline','TimesFM 2.5','Chronos Small'];
  vals.forEach((v,i)=>{
    const x=330+i*460,w=190,h=v/.008*340*ease((t-i*.5)/3);
    rect(x-w/2,670-h,w,h,i===2?C.teal:i===1?C.blue:C.muted);
    text(`€${v.toFixed(5)}`,x,670-h-25,31,C.ink,'center');text(labels[i],x,716,25,C.muted,'center');
  });
  text('Price MAE / kWh · 37 held-out historical days',800,242,27,C.muted,'center');
  alpha(ease((t-6)/2),()=>text('29.2% less price error ≠ a large charging-cost gain',800,782,28,C.gold,'center'));
  footer('Exploratory 2019 German prices · pretraining overlap unknown · synthetic charging replay');
}
function close(t) {
  const nodes=[['LLM proposes',300,C.blue],['Solver plans',800,C.gold],['Validator checks',1300,C.teal]];
  nodes.forEach(([label,x,color],i)=>alpha(ease((t-i*.7)/2),()=>{dot(x,356,17,color);text(label,x,425,32,color,'center',600);}));
  arrow(335,356,765,356,C.muted);arrow(835,356,1265,356,C.muted);
  alpha(ease((t-3)/2),()=>{text('Every departure. Less shared power.',800,565,49,C.ink,'center',600);text('Explore the editable app, source and evidence.',800,630,29,C.muted,'center');});
  text('j-stoerk.github.io/nebiusxnvidia_hackathon',800,731,25,C.teal,'center');
  footer('Original animation · synthetic narration · replaceable team voice tracks');
}
const drawScene={problem,roster,area,bound,comparison,cost,live:liveScene,forecast,close};

function captions(scene,t) {
  const words=scene.text.split(/\s+/);const chunks=[];
  for(let i=0;i<words.length;i+=13)chunks.push(words.slice(i,i+13).join(' '));
  const index=Math.min(chunks.length-1,Math.floor(clamp(t/scene.voice_duration)*chunks.length));
  if(t>scene.voice_duration+.1)return;
  rect(110,865,1380,32,C.bg);text(chunks[index],800,889,21,C.ink,'center');
}
function sceneAt(time) {
  let i=timeline.scenes.findIndex(s=>time>=s.start&&time<s.end);
  if(i<0)i=timeline.scenes.length-1;
  return [timeline.scenes[i],i];
}
function draw(time) {
  const [scene,i]=sceneAt(time),t=time-scene.start;
  rect(0,0,1600,900,C.bg);
  if(scene.id!=='live')header(scene,i,t);
  drawScene[scene.id](t);captions(scene,t);
  rect(0,897,1600*time/duration,3,C.teal);
  if(scene.id!==previousScene){
    previousScene=scene.id;
    if(scene.id!=='live')live.pause();
  }
  if(scene.id==='live'){
    const target=Math.min(Math.max(0,t),live.duration||0);
    if(Math.abs(live.currentTime-target)>.25)live.currentTime=target;
    if(!voice.paused&&live.paused&&target<live.duration)live.play().catch(()=>{});
    if(voice.paused)live.pause();
  }
  seek.value=time/duration*100;clock.textContent=`${stamp(time)} / ${stamp(duration)}`;
}
function frame() {
  const time=voice.paused?manualTime:Math.min(voice.currentTime,duration);
  draw(time);
  if(recording&&voice.currentTime>=duration-.06){recorder.stop();recording=false;voice.pause();}
  requestAnimationFrame(frame);
}
play.disabled=false;play.textContent='Play';
play.addEventListener('click',async()=>{
  if(!voice.paused){manualTime=voice.currentTime;voice.pause();play.textContent='Play';return;}
  if(manualTime>=duration-.1)manualTime=0;
  voice.currentTime=manualTime;
  try{await voice.play();play.textContent='Pause';}catch{document.querySelector('#status').textContent='Audio unavailable. Use the position slider, or download the complete film.';}
});
seek.addEventListener('input',()=>{manualTime=Number(seek.value)/100*duration;voice.currentTime=manualTime;draw(manualTime);});
document.querySelector('#fullscreen').addEventListener('click',()=>document.documentElement.requestFullscreen?.());
voice.addEventListener('ended',()=>{manualTime=duration;play.textContent='Replay';if(recording){recorder.stop();recording=false;}});
window.seekFilm=time=>{manualTime=time;voice.currentTime=time;draw(time);};
window.filmReady=true;
// Optional authoring path: browser media recording, including the narration.
if(new URLSearchParams(location.search).has('render'))document.querySelector('#render').style.display='block';
document.querySelector('#render').addEventListener('click',async()=>{
  audioContext ||= new AudioContext();
  if(!audioDestination){
    audioDestination=audioContext.createMediaStreamDestination();
    const source=audioContext.createMediaElementSource(voice);source.connect(audioDestination);source.connect(audioContext.destination);
  }
  await audioContext.resume();voice.currentTime=0;manualTime=0;
  live.currentTime=0;await live.play();live.pause(); // Unlock video playback in this user gesture.
  const stream=canvas.captureStream(30);
  audioDestination.stream.getAudioTracks().forEach(track=>stream.addTrack(track));
  recorder=new MediaRecorder(stream,{mimeType:'video/webm;codecs=vp9,opus',videoBitsPerSecond:4500000});
  const chunks=[];recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
  recorder.onstop=()=>{
    const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(chunks,{type:'video/webm'}));
    a.download='ChargeWise_Animated_Demo.webm';a.click();window.renderComplete=true;
  };
  document.body.classList.add('recording');recording=true;recorder.start(1000);await voice.play();
});
requestAnimationFrame(frame);
