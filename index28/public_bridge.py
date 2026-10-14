"""Transporte para ejecutar el motor congelado desde Node en desarrollo."""
import json
import re
import sys
from urllib.parse import urlsplit,parse_qs
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError
from index28.socrata import FIELDS

ALLOWED=set(FIELDS)|{"qmzu-gj57","ceth-n4bn","hgi6-6wh3"}


def valid_url(url: str) -> bool:
    try:
        u=urlsplit(url);match=re.fullmatch(r"/(resource|api/views)/([a-z0-9-]+)\.json",u.path)
        if not (u.scheme=="https" and u.hostname=="www.datos.gov.co" and not u.username and not u.password and u.port in (None,443) and match and match[2] in ALLOWED and not u.fragment):return False
        q=parse_qs(u.query,keep_blank_values=True)
        if match[1]=="api/views":return not q
        return set(q)<={"$where","$limit","$offset","$order"} and all(len(v)==1 for v in q.values()) and 1<=int(q.get("$limit",["200"])[0])<=1000 and 0<=int(q.get("$offset",["0"])[0])<=100000
    except (ValueError,TypeError):return False


def request(url: str) -> dict:
    if not valid_url(url):raise ValueError("URL publica no permitida")
    class Redirect(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            if not valid_url(newurl):raise ValueError("Redireccion no permitida")
            return super().redirect_request(req,fp,code,msg,headers,newurl)
    try:
        with build_opener(Redirect()).open(Request(url,headers={"Accept":"application/json","User-Agent":"SECOP-Consulta-Mixta-Indexer/0.3"}),timeout=18) as stream:
            body=stream.read(8_000_001)
            if len(body)>8_000_000:raise ValueError("Respuesta excesiva")
            return {"status":200,"body":json.loads(body)}
    except HTTPError as exc:return {"status":exc.code,"body":"Error HTTP de fuente publica"}
    except Exception:return {"status":504,"body":"La fuente no respondio dentro del limite"}


if __name__=="__main__":print(json.dumps(request(sys.argv[1]),ensure_ascii=False))
