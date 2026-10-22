"""Local-only persistence check. Run prepare, restart local services, then verify."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parent.parent
STATE=ROOT/'var/persistence-check.json'
COOKIES=ROOT/'var/persistence-check.cookies'
BASE='http://127.0.0.1:5173/api'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['prepare','verify'])
    args=parser.parse_args()
    jar=http.cookiejar.MozillaCookieJar(str(COOKIES))
    if args.command=='verify':
        jar.load(ignore_discard=True)
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    def call(path,body=None,method=None):
        req=urllib.request.Request(BASE+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'},method=method)
        with client.open(req, timeout=10) as response:
            return json.load(response)
    if args.command=='prepare':
        call('/session',{'actor_id':'st-01'})
        record=call('/trace?ref=ev-0960')
        page=record['page']['printed_content']
        start=page.index('18,450.00')
        saved=call('/locators/ev-0960',{'expected_revision':record['revision'],'start':start,'end':start+9},'PUT')
        report=call('/audit')
        state={'ref':'ev-0960','revision':saved['revision'],'locator':saved['payload']['locator'],'counts':report['counts'],'hash':report['packet_hash']}
        STATE.parent.mkdir(parents=True,exist_ok=True)
        STATE.write_text(json.dumps(state))
        jar.save(ignore_discard=True)
        print('Prepared manual anchor and database-backed demo session. Restart the app and database, then run verify.')
    else:
        expected=json.loads(STATE.read_text())
        assert call('/session')['id']=='st-01'
        actual=call('/trace?ref='+expected['ref'])
        assert actual['revision']==expected['revision']
        assert actual['value']['locator']==expected['locator']
        report=call('/audit')
        assert report['packet_hash']==expected['hash']
        assert report['counts']==expected['counts']
        print('PASS: manual anchor, revision, demo session, original hash and import counts survived service restarts.')

if __name__=='__main__':
    main()
