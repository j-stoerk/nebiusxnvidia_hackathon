// One persistent world: a request travels along the same rail as the camera follows.
// The export uses a deterministic clock and contains no audio or inference calls.
const canvas=document.querySelector('#film'),ctx=canvas.getContext('2d');
const play=document.querySelector('#play'),seek=document.querySelector('#seek'),clock=document.querySelector('#clock');
const [timeline,data,brand]=await Promise.all([
  fetch('timeline.json').then(r=>r.json()),fetch('scenario.json').then(r=>r.json()),fetch('brand.svg').then(r=>r.text())
]);
const logo=new Image();
logo.src=URL.createObjectURL(new Blob([brand.replaceAll('#183b4e','#e7f1f3').replaceAll('#008b8b','#50c5bc')],{type:'image/svg+xml'}));
await logo.decode();
const C={bg:'#0c1722',ink:'#ecf3f5',muted:'#9aafbf',line:'#294250',teal:'#50c5bc',gold:'#edbf70',blue:'#82afd2',red:'#ee968b'};
const D=timeline.duration;
const exporting=new URLSearchParams(location.search).has('export');
let position=0,playing=false,last=0;
const clamp=x=>Math.max(0,Math.min(1,x));
const ease=x=>{x=clamp(x);return x*x*(3-2*x);};
const mix=(a,b,p)=>a+(b-a)*p;
const phase=(t,a,b)=>ease((t-a)/(b-a));
const stamp=t=>`${Math.floor(t/60)}:${String(Math.floor(t%60)).padStart(2,'0')}`;
const route=[[-1200,350],[-680,350],[0,350],[600,350],[1220,350],[1220,810],[600,1050],[0,1050],[-680,1050],[-680,350]];
// Interpolated camera poses keep the entire map spatially coherent.
const views=[
  [0,0,40,1],[7,0,40,1],[12,-720,350,.87],[20,-640,350,.87],
  [26,600,350,.88],[36,600,350,.88],[42,600,340,.98],[50,600,340,.98],
  [56,1200,350,.96],[62,1200,350,.96],[68,420,-80,.8],[80,420,-80,.8],
  [86,600,1000,.88],[96,600,1000,.88],[102,-650,1020,.88],[110,-650,1020,.88],
  [120,100,390,.38],[124,100,390,.38]
];

function text(s,x,y,size=26,color=C.ink,align='left',weight=400){
  ctx.font=`${weight} ${size}px "Segoe UI",Arial,sans-serif`;ctx.fillStyle=color;
  const w=ctx.measureText(s).width,left=align==='center'?x-w/2:align==='right'?x-w:x;
  ctx.fillStyle=C.bg;ctx.fillRect(left-5,y-size*.88,w+10,size*1.16);ctx.fillStyle=color;
  ctx.textAlign=align;ctx.fillText(s,x,y);ctx.textAlign='left';
}
function line(x,y,X,Y,color=C.line,width=2,dash=[]){
  ctx.beginPath();ctx.setLineDash(dash);ctx.moveTo(x,y);ctx.lineTo(X,Y);
  ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();ctx.setLineDash([]);
}
function rect(x,y,w,h,color){ctx.fillStyle=color;ctx.fillRect(x,y,w,h);}
function dot(x,y,r,color){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();}
function fade(p,draw){if(p<=0)return;ctx.save();ctx.globalAlpha=clamp(p);draw();ctx.restore();}
function ring(x,y,r,color,width=2,progress=1){
  ctx.beginPath();ctx.arc(x,y,r,-Math.PI/2,-Math.PI/2+Math.PI*2*progress);
  ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();
}
function curve(points,color=C.line,width=2,progress=1,dash=[]){
  ctx.save();ctx.setLineDash(dash);ctx.strokeStyle=color;ctx.lineWidth=width;
  ctx.beginPath();ctx.moveTo(...points[0]);
  const count=(points.length-1)*clamp(progress);
  for(let i=1;i<=Math.floor(count);i++)ctx.lineTo(...points[i]);
  if(count%1){const i=Math.floor(count);ctx.lineTo(mix(points[i][0],points[i+1][0],count%1),mix(points[i][1],points[i+1][1],count%1));}
  ctx.stroke();ctx.restore();
}
function packet(points,t,speed=.12,color=C.teal){
  const u=(t*speed%1)*(points.length-1),i=Math.min(points.length-2,Math.floor(u));
  dot(mix(points[i][0],points[i+1][0],u-i),mix(points[i][1],points[i+1][1],u-i),5,color);
}
function bezier(a,b,c,d,n=32){
  return Array.from({length:n+1},(_,i)=>{const t=i/n,s=1-t;return [s*s*s*a[0]+3*s*s*t*b[0]+3*s*t*t*c[0]+t*t*t*d[0],s*s*s*a[1]+3*s*s*t*b[1]+3*s*t*t*c[1]+t*t*t*d[1]];});
}
function camera(t){
  let i=views.findIndex((v,j)=>j<views.length-1&&t>=v[0]&&t<views[j+1][0]);
  if(i<0)return views.at(-1).slice(1);
  const p=phase(t,views[i][0],views[i+1][0]);return [1,2,3].map(k=>mix(views[i][k],views[i+1][k],p));
}
function mark(x,y,size){ctx.drawImage(logo,x-size/2,y-size/2,size,size);}

function team(t){
  const moved=phase(t,7,13),y=mix(-90,282,moved),size=mix(166,118,moved);
  fade(1-phase(t,7,11),()=>{
    const people=[['Julius Störk',-530,C.blue],['Umar Khan',0,C.gold],['Muhammad Talha Toqeer',530,C.teal]];
    people.forEach(([name,x,color],i)=>fade(phase(t,.7+i*.4,2+i*.4),()=>{
      const path=bezier([x,235],[x,170],[x*.35,10],[0,-5]);
      curve(path,C.line,2,phase(t,2,5));
      dot(x,235,5,color);text(name,x,292,name.length>20?31:35,C.ink,'center',500);
      if(t>3)packet(path,t+i,.1,color);
    }));
    text('Every departure. Less shared power.',0,145,26,C.muted,'center');
  });
  mark(0,y,size);
  text('ChargeWise',0,y+mix(150,125,moved),mix(58,34,moved),C.ink,'center',600);
  fade(moved,()=>{text('FastAPI · workspace',0,475,24,C.muted,'center');});
}
function inputStream(t){
  const p=phase(t,8,13);
  fade(p,()=>{
    text('React + Vite',-1200,30,34,C.blue,'center',600);
    text('Roster · chargers · prices',-1200,78,24,C.muted,'center');
    [['Arrival / departure','06:00 → 12:00'],['Energy / charger','18 kWh · CH-01'],['Electricity price','EUR / kWh']].forEach(([name,value],i)=>{
      const y=200+i*125;
      line(-1430,y-34,-1394,y-34,C.blue,3);line(-1430,y-34,-1430,y+34,C.blue,3);line(-1430,y+34,-1394,y+34,C.blue,3);
      text(name,-1370,y-7,24,C.ink);text(value,-1370,y+25,21,C.muted);
      const path=bezier([-1040,y],[-900,y],[-850,350],[-720,350]);curve(path,C.line,2,phase(t,10,16));
      if(t>13)packet(path,t+i,.16,C.blue);
    });
    ring(-680,350,39,C.teal,3,phase(t,12,17));
    line(-698,350,-685,362,C.teal,4);line(-685,362,-662,337,C.teal,4);
    text('Pandas + Pydantic',-680,250,28,C.teal,'center',500);
    text('Typed scenario',-680,455,26,C.muted,'center');
    if(t>15)packet(route.slice(1,3),t,.18,C.gold);
  });
}
function grid(t){
  const open=phase(t,22,27),fold=phase(t,37,42),move=phase(t,81,87);
  const x=mix(mix(780,600,fold),600,move),y=mix(mix(350,565,fold),1035,move),scale=mix(1,.27,fold)*(1-move)+move;
  const change=phase(t,88,95),now=data.freeze_slot||24;
  fade(open,()=>{
    ctx.save();ctx.translate(x,y);ctx.scale(scale,scale);
    const left=-500,top=-160,cell=1000/56;
    rect(left-4,top-6,1008,315,C.bg);
    data.power_by_vehicle.forEach((row,i)=>{
      text(`V${i+1} · CH-0${i%2+1}`,left-22,top+i*78+30,22,C.muted,'right');
      row.forEach((p,j)=>{
        const after=data.replanned_by_vehicle?.[i]?.[j]??p;
        rect(left+j*cell,top+i*78,cell-2,52,'#182e3c');
        const value=mix(p,after,change),color=i<2?C.teal:C.blue;
        fade(value/11*phase(t,23+j*.02,26+j*.02),()=>rect(left+j*cell,top+i*78,cell-2,52,color));
      });
    });
    [6,10,14,18,20].forEach(hr=>text(`${String(hr).padStart(2,'0')}:00`,left+(hr-6)/14*1000,195,20,C.muted,'center'));
    fade(1-fold,()=>{
      text('Power × time becomes energy',0,-245,36,C.ink,'center',500);
      text('Site capacity · plug occupancy · battery taper',0,270,27,C.muted,'center');
      const q=left+phase(t,24,36)*1000;line(q,-185,q,145,C.gold,2);
    });
    fade(move,()=>{
      const xnow=left+now*cell;
      line(xnow,-215,xnow,165,C.ink,2);
      text('Delivered',xnow-95,-205,27,C.teal,'right');text('Replanned',xnow+95,-205,27,C.blue);
      text('NOW',xnow,240,22,C.muted,'center');
      fade(change,()=>{line(left+40*cell,top+3*78-8,left+48*cell,top+3*78-8,C.red,4);text('Charger outage',left+44*cell,top+3*78-32,23,C.red,'center');});
    });
    ctx.restore();
  });
}
function optimizer(t){
  const p=phase(t,38,42),details=phase(t,38,43),labels=1-phase(t,60,65);
  fade(p,()=>{
    ring(600,350,mix(22,76,details),C.gold,3);
    fade(details,()=>{
      text('OR-Tools',600,340,30,C.gold,'center',600);text('SCIP',600,376,20,C.muted,'center');
      fade(labels,()=>['FCFS','EDF','LLF'].forEach((label,i)=>{
        const x=350+i*250;const path=bezier([600,290],[600,165],[x,165],[x,80]);
        curve(path,C.line,2);dot(x,80,6,C.blue);text(label,x,32,27,C.blue,'center');
        packet(path,t+i,.12,C.blue);
      }));
      fade(labels,()=>{text('1  Departure energy',850,320,29,C.ink);text('2  Energy + demand cost',850,380,27,C.muted);});
    });
  });
}
function validator(t){
  const p=phase(t,50,56);
  fade(p,()=>{
    ring(1220,350,58,C.teal,3,phase(t,52,58));
    const q=phase(t,54,59);curve([[1193,350],[1213,370],[1250,329]],C.teal,5,q);
    [['Windows',-145,-130],['Power',150,-130],['Plugs',-145,160],['Energy',150,160]].forEach(([s,x,y],i)=>{
      fade(phase(t,53+i,56+i),()=>{dot(1220+x,350+y,5,C.teal);text(s,1220+x,350+y-22,24,C.muted,'center');});
    });
    text('Independent check',1220,245,29,C.teal,'center',500);
    const back=bezier([1275,350],[1660,350],[1470,-40],[950,-40]);curve(back,C.line,2,phase(t,57,62));
    fade(phase(t,57,62),()=>{text('Ready · peak · cost',1390,40,26,C.ink,'center');packet(back,t,.13,C.teal);});
  });
}
function agent(t){
  const p=phase(t,63,68);
  fade(p,()=>{
    const up=bezier([0,300],[0,-300],[230,-300],[530,-300]);
    const down=bezier([670,-300],[950,-300],[600,-80],[600,292]);
    curve(up,C.line,2);curve(down,C.line,2);packet(up,t,.1,C.gold);packet(down,t+.9,.1,C.teal);
    ring(600,-300,82,C.teal,3,phase(t,65,70));
    text('Nemotron',600,-302,30,C.teal,'center',600);text('NVIDIA',600,-264,18,C.muted,'center');
    text('Nebius Token Factory',600,-420,31,C.ink,'center',500);
    text('Question',75,-110,26,C.gold);text('Credit allowance',15,180,23,C.muted);
    text('{ typed tools }',600,8,29,C.gold,'center',500);
    text('get_schedule',600,58,24,C.muted,'center');text('simulate_event',600,98,24,C.muted,'center');
    ring(600,205,20,C.gold,2);text('User approval',650,213,23,C.muted);
    fade(phase(t,74,79),()=>{text('Computed facts',245,-375,23,C.teal,'center');});
  });
}
function replanning(t){
  fade(phase(t,82,87),()=>{
    text('Keep the delivered energy. Move the future.',600,690,35,C.ink,'center',500);
    const loop=bezier([960,1050],[1470,1050],[1570,500],[1270,380]);
    curve(loop,C.line,2,phase(t,88,94));packet(loop,t,.13,C.teal);
    text('New event → updated plan',1110,820,26,C.red,'center');
  });
}
function capacity(t){
  fade(phase(t,97,102),()=>{
    [-850,-510].forEach((x,i)=>{
      ring(x,990,35,C.blue,3);text(`CH-0${i+1}`,x,1070,24,C.muted,'center');
      line(x,1025,x,1140,C.line,2);line(x,1140,-680,1140,C.line,2);
    });
    text('Size the shared connection',-680,780,35,C.ink,'center',500);
    text('Normal day · four vans',-680,824,23,C.muted,'center');
    text('48 kWh ÷ (0.90 × 6 h)',-680,875,36,C.gold,'center');
    fade(phase(t,102,107),()=>{text('8.89 kW',-680,1210,48,C.teal,'center',600);text('Two installed plugs',-680,1255,25,C.muted,'center');});
  });
}
function overview(t){
  fade(phase(t,113,119),()=>{
    const historical=bezier([-1150,700],[-1050,820],[-400,740],[-160,750]);
    curve(historical,C.line,2,1,[7,6]);text('Forecasting study',-720,680,25,C.muted,'center');
    text('TimesFM · Chronos',-720,725,23,C.muted,'center');
  });
}
function draw(t){
  rect(0,0,1600,900,C.bg);
  const [x,y,z]=camera(t);ctx.save();ctx.translate(800,450);ctx.scale(z,z);ctx.translate(-x,-y);
  // Grid and rail stay fixed in world space throughout every camera movement.
  for(let gx=-1700;gx<=1900;gx+=100)for(let gy=-600;gy<=1500;gy+=100)dot(gx,gy,1,C.line);
  fade(phase(t,7,13),()=>{curve(route,C.line,3);curve(route,C.teal,3,phase(t,10,117));packet(route,t,.016,C.gold);});
  inputStream(t);optimizer(t);validator(t);agent(t);replanning(t);capacity(t);overview(t);grid(t);team(t);
  ctx.restore();
  fade(phase(t,116,121),()=>{
    rect(0,0,1600,130,C.bg);mark(105,68,66);text('ChargeWise',160,83,40,C.ink,'left',600);
    rect(0,803,1600,97,C.bg);text('Every departure. Less shared power.',800,835,38,C.ink,'center',500);
    text('Next: the live application walkthrough',800,880,22,C.muted,'center');
  });
  seek.value=t/D*100;clock.textContent=`${stamp(t)} / ${stamp(D)}`;
}
function frame(now){
  if(playing){position=Math.min(D,position+(now-last)/1000);if(position===D){playing=false;play.textContent='Replay';}}
  last=now;draw(position);if(!exporting)requestAnimationFrame(frame);
}
play.disabled=false;play.textContent='Play';
play.addEventListener('click',()=>{if(position===D)position=0;playing=!playing;play.textContent=playing?'Pause':'Play';last=performance.now();});
seek.addEventListener('input',()=>{position=Number(seek.value)/100*D;draw(position);});
document.querySelector('#fullscreen').addEventListener('click',()=>document.documentElement.requestFullscreen?.());
window.seekFilm=t=>{position=clamp(t/D)*D;draw(position);};
window.drawFilm=t=>draw(clamp(t/D)*D);
window.filmDuration=D;window.filmReady=true;
if(exporting)draw(0);else requestAnimationFrame(frame);
