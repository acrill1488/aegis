param([string]$HostName = $env:AEGIS_SERVER_HOST, [string]$User = "mk")
$ErrorActionPreference = "Stop"
$remote = @'
python3 - <<'PY'
import json, subprocess, sys
def run(args):
    return subprocess.run(args, text=True, capture_output=True, check=False).stdout.strip()
import os
greenboost_dir = os.path.expanduser('~/greenboost')
sys.path.insert(0, greenboost_dir)
try:
    from gb_nvml import get_nvml
    used, free, total, _ = get_nvml().mem()
    gpu = [total, used, free]
except Exception:
    gpu = [int(x) for x in run(['nvidia-smi','--query-gpu=memory.total,memory.used,memory.free','--format=csv,noheader,nounits']).splitlines()[0].split(',')]
rows = run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits']).splitlines()
processes=[]
for row in rows:
    parts=[x.strip() for x in row.split(',')]
    if len(parts)>=3:
        try: mem=int(parts[2])
        except ValueError: mem=0
        processes.append({'pid':int(parts[0]),'name':parts[1],'used_vram_mb':mem})
services={}
for p in processes:
    n=p['name'].lower()
    service='unlimited-ocr' if 'python' in n else ('comfyui' if 'comfy' in n else ('ollama' if 'ollama' in n else None))
    if service: services[service]=services.get(service,0)+p['used_vram_mb']
sha = run(['git','-C',greenboost_dir,'rev-parse','HEAD'])
print(json.dumps({'available':True,'total_vram_mb':int(gpu[0]),'used_vram_mb':int(gpu[1]),'free_vram_mb':int(gpu[2]),'cuda_processes':processes,'aegis_services':services,'greenboost_commit':sha}))
PY
'@
ssh -o BatchMode=yes -o ConnectTimeout=8 "$User@$HostName" $remote
exit $LASTEXITCODE
