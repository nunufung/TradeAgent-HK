"""Explicit deployment to a separate Space; never changes billing/hardware."""
from pathlib import Path
import hashlib
import hmac
import os
import sys

SPACE='lewisf/tradeagent-hk-fcc-gateway'
ALLOWED={'README.md','Dockerfile','gateway.py','.dockerignore'}
PROVIDERS=('DEEPSEEK_API_KEY','NVIDIA_NIM_API_KEY','OPENROUTER_API_KEY','GROQ_API_KEY')


def main():
    from huggingface_hub import HfApi
    token=os.getenv('HF_TOKEN','').strip()
    if not token: sys.exit('HF_TOKEN write credential missing')
    api=HfApi(token=token)
    profile=api.whoami()
    if profile.get('name')!='lewisf': sys.exit('Unexpected Hugging Face account')
    if not profile.get('isPro'): sys.exit('Docker Space requires an eligible paid plan; no deployment or billing changes made')
    if not os.getenv('DEEPSEEK_API_KEY','').strip(): sys.exit('DEEPSEEK_API_KEY missing')
    folder=Path(__file__).parent/'space'
    files={p.name for p in folder.iterdir() if p.is_file()}
    if files!=ALLOWED: sys.exit('Unexpected gateway deployment files')
    key=hmac.new(token.encode(),b'TradeAgent-HK/FCC-gateway/v1',hashlib.sha256).hexdigest()
    api.create_repo(repo_id=SPACE,repo_type='space',space_sdk='docker',private=False,exist_ok=True)
    for name,value in {'FCC_API_KEY':key,'FCC_ALLOWED_MODELS':os.getenv('FCC_ALLOWED_MODELS','deepseek/deepseek-chat'),
                       **{p:os.getenv(p,'').strip() for p in PROVIDERS}}.items():
        if value: api.add_space_secret(repo_id=SPACE,key=name,value=value)
    api.upload_folder(repo_id=SPACE,repo_type='space',folder_path=str(folder),allow_patterns=sorted(ALLOWED),
                      commit_message='Deploy authenticated FCC gateway')
    print('Gateway source published: https://huggingface.co/spaces/'+SPACE)
    print('Runtime and inference remain unverified until smoke tests pass.')
    # Keep matching client settings private; the current static dashboard cannot call them.
    dashboard='lewisf/tradeagent-hk-dashboard'
    for name,value in {'FCC_API_KEY':key,'FCC_BASE_URL':'https://lewisf-tradeagent-hk-fcc-gateway.hf.space',
                       'FCC_MODEL':'deepseek/deepseek-chat'}.items():
        api.add_space_secret(repo_id=dashboard,key=name,value=value)


if __name__=='__main__': main()
