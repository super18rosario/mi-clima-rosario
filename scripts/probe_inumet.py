#!/usr/bin/env python3
"""One-time technical probe of INUMET public CSV. No files are stored."""
import csv
import io
import urllib.request
from collections import Counter, deque

URLS = {
    'temperatura': 'https://catalogodatos.gub.uy/dataset/accd0e24-76be-4101-904b-81bb7d41ee88/resource/f800fc53-556b-4d1c-8bd6-28b41f9cf146/download/inumet_temperatura_del_aire.csv',
    'lluvia': 'https://catalogodatos.gub.uy/dataset/fd896b11-4c04-4807-bae4-5373d65beea2/resource/cc785e9e-d9c8-4706-b013-9a6a5b0f7d01/download/inumet_precipitacion_acumulada_horaria.csv',
}
for name, url in URLS.items():
    print(f'=== {name} ===', flush=True)
    try:
        req=urllib.request.Request(url, headers={'User-Agent':'MiClimaRosario/6.2 (INUMET source validation)'})
        with urllib.request.urlopen(req,timeout=70) as res:
            raw=res.read(32000000)
            print('http',res.status,'content-type',res.headers.get('Content-Type'), 'bytes',len(raw), 'content-length',res.headers.get('Content-Length'))
        if len(raw)>=32000000:
            print('WARNING: size limit exceeded');continue
        value=raw.decode('utf-8-sig')
        reader=csv.reader(io.StringIO(value),delimiter=';')
        header=next(reader,None)
        print('header',repr(header))
        print('first_rows:',flush=True)
        first=[];last=deque(maxlen=2);stations=Counter();n=0
        for row in reader:
            if not row:continue
            n+=1
            if len(first)<2:first.append(row)
            last.append(row)
            if len(row)>1: stations[row[1]]+=1
        for row in first:print('  ',repr(row)[:350])
        print('last_rows:',flush=True)
        for row in last:print('  ',repr(row)[:350])
        print('rows',n,'station-samples',stations.most_common(20),flush=True)
    except Exception as e:
        print('ERROR',type(e).__name__,str(e)[:300],flush=True)
