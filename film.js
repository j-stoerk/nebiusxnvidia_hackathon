// Original architecture diagrams, driven by the narration clock. No API calls.
const canvas = document.querySelector('#film');
const ctx = canvas.getContext('2d');
const voice = document.querySelector('#voice');
const play = document.querySelector('#play');
const seek = document.querySelector('#seek');
const clock = document.querySelector('#clock');
const C = {bg:'#0c1420',ink:'#edf3fa',muted:'#9bafc5',line:'#304359',teal:'#61d5c0',blue:'#7ebaff',gold:'#f2cb75',red:'#ef9290'};
const [timeline,data] = await Promise.all(['timeline.json','scenario.json'].map(p=>fetch(p).then(r=>r.json())));
// A small audio blob permits seeking on preview servers without byte ranges.
const audioBlob = await fetch(voice.getAttribute('src')).then(r=>r.blob());
const audioReady = new Promise(resolve=>voice.addEventListener('loadeddata',resolve,{once:true}));
voice.preload='auto';voice.src=URL.createObjectURL(audioBlob);voice.load();await audioReady;
const duration=timeline.duration;
let manualTime=0,recording=false,recorder,audioContext,audioDestination;
const clamp=x=>Math.max(0,Math.min(1,x));
const ease=x=>{x=clamp(x);return x*x*(3-2*x);};
const stamp=t=>`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;

function text(value,x,y,size=28,color=C.ink,align='left',weight=400){
  ctx.fillStyle=color;ctx.font=`${weight} ${size}px "Segoe UI",Arial,sans-serif`;
  ctx.textAlign=align;ctx.fillText(value,x,y);ctx.textAlign='left';
}
function line(x1,y1,x2,y2,color=C.line,width=2,dash=[]){
  ctx.beginPath();ctx.setLineDash(dash);ctx.strokeStyle=color;ctx.lineWidth=width;
  ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([]);
}
function rect(x,y,w,h,color){ctx.fillStyle=color;ctx.fillRect(x,y,w,h);}
function dot(x,y,r,color){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();}
function alpha(a,draw){ctx.save();ctx.globalAlpha=clamp(a);draw();ctx.restore();}
function arrow(x1,y1,x2,y2,color=C.muted){
  line(x1,y1,x2,y2,color,2);
  const a=Math.atan2(y2-y1,x2-x1);
  line(x2,y2,x2-12*Math.cos(a-.45),y2-12*Math.sin(a-.45),color);
  line(x2,y2,x2-12*Math.cos(a+.45),y2-12*Math.sin(a+.45),color);
}
function flow(x1,y1,x2,y2,t,color=C.teal,delay=0){
  const p=ease((t-delay)/1.5);
  arrow(x1,y1,x1+(x2-x1)*p,y1+(y2-y1)*p,C.line);
  if(p<1)return;
  for(let i=0;i<3;i++){const s=((t-delay)*.22+i/3)%1;dot(x1+(x2-x1)*s,y1+(y2-y1)*s,4,color);}
}
function box(label,detail,x,y,w=330,h=115,color=C.blue,p=1){
  alpha(p,()=>{
    rect(x,y,w,h,C.bg);ctx.strokeStyle=color;ctx.lineWidth=2;ctx.strokeRect(x,y,w,h);
    text(label,x+w/2,y+h/2-4,w<250?22:27,color,'center',600);
    text(detail,x+w/2,y+h/2+31,w<250?17:20,C.muted,'center');
  });
}
function boundary(label,x,y,w,h,color=C.line){
  ctx.strokeStyle=color;ctx.setLineDash([7,7]);ctx.strokeRect(x,y,w,h);ctx.setLineDash([]);
  text(label,x+16,y-15,19,C.muted);
}
function footer(label='Architecture of the implemented application'){
  text(label,80,844,16,C.muted);text('Julius Störk · Talha · Umar Khan',1520,844,16,C.muted,'right');
}
function system(t){
  boundary('CPU application · one backend worker',580,270,460,510);
  box('React + Vite','Tailwind · Recharts',90,365,340,135,C.blue,ease(t/1.5));
  box('FastAPI','Scenario & workflow orchestration',630,310,360,115,C.gold,ease((t-1)/1.5));
  box('OR-Tools / SCIP','Physical charging schedule',630,480,360,115,C.gold,ease((t-2)/1.5));
  box('Independent validator','Check emitted allocations',630,650,360,100,C.teal,ease((t-3)/1.5));
  box('NVIDIA Nemotron','Nebius Token Factory',1140,310,350,130,C.teal,ease((t-4)/1.5));
  flow(430,397,630,367,t,C.blue,1);flow(810,425,810,480,t,C.gold,2);
  flow(810,595,810,650,t,C.teal,3);flow(990,367,1140,367,t,C.teal,4);
  flow(630,700,490,700,t,C.teal,5);flow(490,700,490,490,t,C.teal,5.5);flow(490,490,430,450,t,C.teal,6);
  alpha(ease((t-6)/2),()=>{text('HTTP / JSON',500,350,19,C.muted,'center');text('Inference only',1315,491,23,C.teal,'center');text('Checked plans return to the dashboard',260,650,23,C.ink,'center');});
  footer('Browser interface + CPU scheduling · separate remote model service');
}
function inputs(t){
  const sources=[['sessions.csv','Vehicles · windows · energy'],['prices.csv','UTC intervals · EUR/kWh'],['station.json / editor','Ports · site limit · tariff']];
  sources.forEach(([name,detail],i)=>{
    box(name,detail,90,270+i*160,350,110,C.blue,ease((t-i*.6)/1.5));
    flow(440,325+i*160,605,445,t,C.blue,1+i*.4);
  });
  box('Pandas + Pydantic','Schema, time & scenario checks',605,365,380,160,C.gold,ease((t-2)/2));
  flow(985,445,1150,445,t,C.teal,4);
  box('Browser workspace','Version v → v + 1',1150,365,350,160,C.teal,ease((t-4)/2));
  alpha(ease((t-5)/2),()=>{
    arrow(795,525,795,625,C.red);box('Reject invalid draft','Existing scenario is preserved',605,625,380,100,C.red);
    text('Atomic replacement',1325,585,25,C.teal,'center');text('In-memory state',1325,625,23,C.muted,'center');
  });
  footer('CSV uploads and complete editor drafts share the scenario contract');
}
function physics(t){
  const x=350,y=315,w=1110,cell=w/56;
  text('Power variables  p(vehicle, plug, time)',350,250,29,C.gold);
  data.power_by_vehicle.forEach((row,i)=>{
    text(`VAN-0${i+1}`,115,y+i*76+35,25,C.ink);
    text(i%2?'CH-02':'CH-01',245,y+i*76+35,21,C.muted);
    row.forEach((p,j)=>{
      rect(x+j*cell,y+i*76,cell-2,55,'#172536');
      alpha(ease((t-j*.03-i*.3)/2)*p/11,()=>rect(x+j*cell,y+i*76,cell-2,55,i<2?C.teal:C.blue));
    });
  });
  [6,8,10,12,14,16,18,20].forEach(hr=>text(`${String(hr).padStart(2,'0')}:00`,x+(hr-6)/14*w,655,19,C.muted,'center'));
  const cursor=x+clamp(t/11)*w;line(cursor,295,cursor,605,C.gold,2);
  alpha(ease((t-4)/2),()=>{
    text('Σ p(vehicle, plug, t) ≤ site limit',800,720,31,C.gold,'center');
    text('Delivered energy = Σ efficiency × power × interval',800,775,30,C.teal,'center');
  });
  footer('Actual checked synthetic fixture · fixed ports · rating, occupancy, efficiency & conservative taper');
}
function solve(t){
  text('Same validated inputs. Same physical constraints.',800,245,29,C.muted,'center');
  ['FCFS','EDF','LLF'].forEach((name,i)=>{
    box(name,['First come, first served','Earliest deadline first','Least laxity first'][i],145+i*460,300,390,120,C.blue,ease((t-i*.6)/1.6));
    alpha(ease((t-2-i*.6)/1.5),()=>text('✓ baseline complete',340+i*460,470,24,C.teal,'center'));
  });
  alpha(ease((t-4)/2),()=>{
    text('OR-Tools / SCIP',235,610,34,C.gold,'center',600);
    arrow(425,605,580,605,C.gold);
    text('1',620,580,35,C.gold,'center',600);text('Minimize unserved energy',680,580,34,C.ink);
    text('2',620,654,35,C.gold,'center',600);text('Minimize energy + demand cost',680,654,34,C.ink);
  });
  alpha(ease((t-8)/2),()=>text('Alternative: unserved energy → peak → cost',800,770,27,C.muted,'center'));
  footer('Real stage order: input checks → FCFS → EDF → LLF → optimization → validation');
}
function certify(t){
  box('Candidate allocations','Vehicle · plug · interval · kW',90,325,390,130,C.gold,ease(t/1.5));
  box('Inputs + delivered history','The independent reference',90,580,390,115,C.blue,ease((t-1)/1.5));
  flow(480,390,680,450,t,C.gold,1);flow(480,635,680,520,t,C.blue,2);
  box('Schedule validator','Check every emitted record',680,390,380,170,C.teal,ease((t-2)/2));
  const checks=['Windows & occupancy','Ports & connector compatibility','Power, energy & taper','Immutable delivery history'];
  checks.forEach((label,i)=>alpha(ease((t-3-i*.8)/1.5),()=>text(`✓ ${label}`,700,260+i*28,20,C.teal)));
  flow(1060,475,1210,475,t,C.teal,6);box('Metrics + dashboard','Publish the checked plan',1210,410,310,130,C.teal,ease((t-6)/2));
  alpha(ease((t-7)/2),()=>{
    arrow(870,560,870,665,C.red);text('Invalid → reject',870,710,29,C.red,'center');
    text('Feasible ≠ proven optimum',800,782,29,C.gold,'center');
  });
  footer('The validator certifies schedule constraints, not generated model prose');
}
function agent(t){
  boundary('Trusted server · key stays here',500,265,560,515);
  box('Question','React interface',70,325,310,110,C.blue,ease(t/1.5));
  box('Agent + credit ledger','Reserve before inference',555,295,450,100,C.gold,ease((t-1)/1.5));
  box('NVIDIA Nemotron','Nebius Token Factory',1170,295,350,130,C.teal,ease((t-2)/1.5));
  flow(380,380,555,345,t,C.blue,1);flow(1005,345,1170,345,t,C.teal,2);
  alpha(ease((t-4)/2),()=>{arrow(1345,425,1345,445,C.teal);arrow(1345,445,660,445,C.teal);arrow(660,445,660,480,C.teal);text('Tool-call JSON',1330,550,24,C.teal,'center');});
  box('Typed arguments','Declared schema',555,480,210,110,C.gold,ease((t-4)/2));
  box('Permission gate','Mutations opt-in',795,480,210,110,C.gold,ease((t-5)/2));
  flow(765,535,795,535,t,C.gold,5);
  box('Approved tools','Read state or call planner + validator',555,640,450,100,C.teal,ease((t-6)/2));
  flow(900,590,900,640,t,C.teal,6);
  flow(1005,690,1540,690,t,C.teal,7);flow(1540,690,1540,235,t,C.teal,7.5);
  flow(1540,235,1345,235,t,C.teal,8);flow(1345,235,1345,295,t,C.teal,8.5);
  alpha(ease((t-6)/2),()=>{
    text('get_state',80,560,23,C.muted);text('get_schedule',80,603,23,C.muted);
    text('optimize_schedule',80,646,23,C.muted);text('simulate_event',80,689,23,C.muted);
    text('Computed facts → model explanation',1320,720,23,C.teal,'center');
    text('Tool results',1320,645,20,C.muted,'center');
  });
  footer('Bounded tool loop · persistent local allowance · no inference calls to play this film');
}
function replan(t){
  const now=620;
  text('Delivered history',300,275,29,C.teal,'center');text('Future allocations',1100,275,29,C.gold,'center');
  for(let i=0;i<6;i++)rect(100+i*76,330,60,110,C.teal);
  const changed=ease((t-4)/4);
  for(let i=0;i<10;i++){
    rect(725+i*76,330,60,110,'#25364b');
    alpha(changed,()=>rect(725+i*76,330+(i%3)*10,60,110-(i%3)*10,C.blue));
  }
  line(now,245,now,485,C.ink);text('NOW',now,520,23,C.ink,'center');
  text('FROZEN',300,495,25,C.teal,'center',600);
  alpha(ease((t-2)/2),()=>{line(985,315,1195,315,C.red,5);text('Outage / price change',1090,245,25,C.red,'center');});
  ['Event','Constraints','OR-Tools','Validator','New version'].forEach((name,i)=>{
    const x=95+i*300;box(name,'',x,600,230,90,i===0?C.red:i===3?C.teal:C.gold,ease((t-2-i*.6)/1.5));
    if(i<4)flow(x+230,645,x+300,645,t,C.teal,3+i*.6);
  });
  alpha(ease((t-7)/2),()=>text('Duplicate event → no-op     ·     Stale version → HTTP 409',800,770,27,C.muted,'center'));
  footer('Workflow illustration · completed energy preserved · actual calculation stages streamed');
}
function capacity(t){
  text('Installed hardware',325,255,29,C.muted,'center');
  box('CH-01','11 kW · fixed binding',120,300,410,105,C.blue);
  box('CH-02','11 kW · fixed binding',120,440,410,105,C.blue,ease((t-1)/2));
  text('Physical lower bound',1040,255,29,C.gold,'center');
  alpha(ease((t-2)/3),()=>{
    text('48 kWh ÷ (0.90 × 6 h)',1040,365,43,C.ink,'center',600);
    text('Psite ≥ 8.89 kW',1040,455,47,C.gold,'center',600);
  });
  alpha(ease((t-5)/2),()=>{
    arrow(530,480,730,570,C.teal);arrow(1040,485,1040,570,C.teal);
    box('Feasible checked witness','2 installed plugs at 8.89 kW',620,595,750,110,C.teal);
    text('Lower bound + feasible witness = inspectable minimum',800,775,29,C.teal,'center');
  });
  footer('Synthetic fixture example · incomplete search remains unresolved, never a claimed proof');
}
function scope(t){
  box('Browser + CPU backend','Complete application',115,290,510,120,C.gold,ease(t/2));
  box('Nebius Token Factory','NVIDIA model inference',1030,290,440,120,C.teal,ease((t-1)/2));
  flow(625,350,1030,350,t,C.teal,1);
  boundary('Offline experiment · not connected to live scheduling',95,500,1390,160);
  ['Historical prices','TimesFM / Chronos','Optimizer replay'].forEach((name,i)=>{
    text(name,340+i*460,591,28,C.muted,'center');
    if(i<2)line(490+i*460,582,650+i*460,582,C.line,2,[6,6]);
  });
  alpha(ease((t-6)/2),()=>text('Next: the live application walkthrough',800,765,43,C.ink,'center',600));
  footer('Architecture explainer · synthetic narration · no physical charger control');
}
const scenes={system,inputs,physics,solve,certify,agent,replan,capacity,scope};

function captions(scene,t){
  const words=scene.text.split(/\s+/),chunks=[];
  for(let i=0;i<words.length;i+=13)chunks.push(words.slice(i,i+13).join(' '));
  const index=Math.min(chunks.length-1,Math.floor(clamp(t/scene.voice_duration)*chunks.length));
  if(t>scene.voice_duration+.1)return;
  rect(80,862,1440,35,C.bg);text(chunks[index],800,889,20,C.ink,'center');
}
function draw(time){
  let index=timeline.scenes.findIndex(s=>time>=s.start&&time<s.end);
  if(index<0)index=timeline.scenes.length-1;
  const scene=timeline.scenes[index],t=time-scene.start;
  rect(0,0,1600,900,C.bg);
  text('CHARGEWISE · ARCHITECTURE',80,65,21,C.teal,'left',600);
  text(`${String(index+1).padStart(2,'0')} / 09`,1520,65,19,C.muted,'right');
  alpha(ease(t/1.2),()=>text(scene.title,80,138,44,C.ink,'left',600));line(80,173,1520,173);
  scenes[scene.id](t);captions(scene,t);rect(0,897,1600*time/duration,3,C.teal);
  seek.value=time/duration*100;clock.textContent=`${stamp(time)} / ${stamp(duration)}`;
}
function frame(){
  draw(voice.paused?manualTime:Math.min(voice.currentTime,duration));
  if(recording&&voice.currentTime>=duration-.06){recorder.stop();recording=false;voice.pause();}
  requestAnimationFrame(frame);
}
play.disabled=false;play.textContent='Play';
play.addEventListener('click',async()=>{
  if(!voice.paused){manualTime=voice.currentTime;voice.pause();play.textContent='Play';return;}
  if(manualTime>=duration-.1)manualTime=0;
  voice.currentTime=manualTime;
  try{await voice.play();play.textContent='Pause';}catch{document.querySelector('#status').textContent='Audio unavailable. Use the position slider or download the film.';}
});
seek.addEventListener('input',()=>{manualTime=Number(seek.value)/100*duration;voice.currentTime=manualTime;draw(manualTime);});
document.querySelector('#fullscreen').addEventListener('click',()=>document.documentElement.requestFullscreen?.());
voice.addEventListener('ended',()=>{manualTime=duration;play.textContent='Replay';if(recording){recorder.stop();recording=false;}});
window.seekFilm=time=>{manualTime=time;voice.currentTime=time;draw(time);};
window.filmReady=true;
// Optional authoring export records these diagrams and the narration together.
if(new URLSearchParams(location.search).has('render'))document.querySelector('#render').style.display='block';
document.querySelector('#render').addEventListener('click',async()=>{
  audioContext ||= new AudioContext();
  if(!audioDestination){
    audioDestination=audioContext.createMediaStreamDestination();
    const source=audioContext.createMediaElementSource(voice);source.connect(audioDestination);source.connect(audioContext.destination);
  }
  await audioContext.resume();voice.currentTime=0;manualTime=0;
  const stream=canvas.captureStream(30);
  audioDestination.stream.getAudioTracks().forEach(track=>stream.addTrack(track));
  recorder=new MediaRecorder(stream,{mimeType:'video/webm;codecs=vp9,opus',videoBitsPerSecond:4500000});
  const chunks=[];recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
  recorder.onstop=()=>{
    const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(chunks,{type:'video/webm'}));
    a.download='ChargeWise_Architecture_Explainer.webm';a.click();window.renderComplete=true;
  };
  document.body.classList.add('recording');recording=true;recorder.start(1000);await voice.play();
});
requestAnimationFrame(frame);
