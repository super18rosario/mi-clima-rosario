// Pruebas reales del selector usado por index.html; sin servidor ni red.
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const html=fs.readFileSync('index.html','utf8');
const start=html.indexOf('function chooseTemperatureReference(');
const end=html.indexOf('function render(){',start);
assert(start>0&&end>start,'No se encontró función de producción');
const choose=vm.runInNewContext('('+html.slice(start,end).trim()+')');
const values={
 ecmwf:{tmax:23.4,tmin:12.7},
 gfs:{tmax:22.8,tmin:11.2},
 icon:{tmax:24,tmin:13.3},
 aifs:{tmax:100,tmin:100}
};
const score={schema:1,observation_station:'Colonia G3',eligible_dates:[
 '2026-10-25','2026-10-26','2026-10-27','2026-10-28'],models:{
 ecmwf:{tmax:{mae_c:1.05,n:4},tmin:{mae_c:1.12,n:4}},
 gfs:{tmax:{mae_c:0.90,n:4},tmin:{mae_c:2.30,n:4}},
 icon:{tmax:{mae_c:0.37,n:4},tmin:{mae_c:1.45,n:4}}
}};
const highest=choose(values,score,'tmax');
assert.equal(highest.model,'icon');assert.equal(highest.value,24);assert.equal(highest.provisional,true);
const lowest=choose(values,score,'tmin');
assert.equal(lowest.model,'ecmwf');assert.equal(lowest.value,12.7);
assert.equal(lowest.days,4);
assert.equal(choose(values,null,'tmax').model,'ecmwf');
assert.equal(choose(values,null,'tmax').provisional,false);
const poor=structuredClone(score);
for(const name of ['ecmwf','gfs','icon'])poor.models[name].tmax.n=2;
assert.equal(choose(values,poor,'tmax').model,'ecmwf');
const unequal=structuredClone(score);unequal.models.icon.tmax.n=3;
assert.equal(choose(values,unequal,'tmax').model,'ecmwf');
const unavailable=structuredClone(values);delete unavailable.icon;
assert.equal(choose(unavailable,score,'tmax').model,'gfs');
assert.equal(choose({},score,'tmin'),null);
const incorrectStation=structuredClone(score);incorrectStation.observation_station='Rosario';
assert.equal(choose(values,incorrectStation,'tmax').model,'ecmwf');
console.log('Selector de máximas y mínimas: 10 comprobaciones correctas');
