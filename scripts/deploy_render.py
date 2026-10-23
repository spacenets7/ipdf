"""Deploy the public repository to Render; credentials never go to stdout or Git."""
import argparse
import json
from pathlib import Path
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
REPO='https://github.com/spacenets7/ipdf'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--create',action='store_true');args=parser.parse_args()
    env=dotenv_values(ROOT/'.env')
    env['GITHUB_CLIENT_ID']=env.get('GITHUB_CLIENT_ID') or env.get('CLIENT_ID')
    env['GITHUB_CLIENT_SECRET']=env.get('GITHUB_CLIENT_SECRET') or env.get('CLIENT_SECRET')
    key=env.get('RENDER_API_KEY')
    if not key:
        raise SystemExit('Add RENDER_API_KEY to .env; no deployment was performed.')
    def request(client,method,path,**kwargs):
        response=client.request(method,path,**kwargs)
        if response.is_error:
            # Do not echo provider payloads, which can contain submitted secrets.
            raise SystemExit(f'Render {method} {path}: HTTP {response.status_code}. Inspect your Render dashboard for details.')
        return response.json()
    with httpx.Client(base_url='https://api.render.com/v1/',headers={'Authorization':'Bearer '+key},timeout=90) as client:
        owners=request(client,'GET','owners',params={'limit':100})
        owner=env.get('RENDER_OWNER_ID')
        if not owner:
            if len(owners)!=1:
                raise SystemExit('Multiple Render workspaces: set RENDER_OWNER_ID in .env to select one.')
            owner=owners[0]['owner']['id']
        services=request(client,'GET','services',params={'ownerId':owner,'limit':100})
        matches=[r['service'] for r in services if r['service'].get('repo','').removesuffix('.git')==REPO and r['service']['name']=='ipdf']
        if matches:
            service=matches[0]
        elif args.create:
            allowed=set(dotenv_values(ROOT/'.env.example'))-{'RENDER_API_KEY','RENDER_OWNER_ID','DATA_DIR','PORT'}
            variables=[{'key':k,'value':v} for k,v in env.items() if k in allowed and v is not None]
            variables+=[{'key':'DATA_DIR','value':'/tmp/ipdf-data'}]
            payload={'type':'web_service','name':'ipdf','ownerId':owner,'repo':REPO,'branch':'main',
                'autoDeployTrigger':'commit','envVars':variables,'serviceDetails':{
                    'runtime':'docker','plan':'free','region':'oregon','healthCheckPath':'/health',
                    'envSpecificDetails':{'dockerfilePath':'./Dockerfile','dockerContext':'.','dockerCommand':''}}}
            service=request(client,'POST','services',json=payload)['service']
        else:
            raise SystemExit('No matching service. Run with --create to deploy on the free plan.')
        deploys=request(client,'GET',f"services/{service['id']}/deploys",params={'limit':1})
        result={'service_id':service['id'],'url':service.get('serviceDetails',{}).get('url'),
            'deploy':deploys[0]['deploy']['status'] if deploys else 'pending'}
        target=ROOT/'data/validation/render-deployment.json';target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))

if __name__=='__main__':
    main()
