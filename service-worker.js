// Solo se guarda estructura visual; los datos meteorológicos se piden a la red.
const CACHE='mi-clima-rosario-v8-shell';
self.addEventListener('install', e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['./','./index.html','./manifest.webmanifest?v=7','./icon-192.png?v=7','./icon-512.png?v=7'])).then(()=>self.skipWaiting())));
self.addEventListener('activate', e=>e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch', e=>{
  if(e.request.method!=='GET' || new URL(e.request.url).pathname.includes('/data/'))return;
  if(new URL(e.request.url).origin!==self.location.origin)return;
  e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));
});
