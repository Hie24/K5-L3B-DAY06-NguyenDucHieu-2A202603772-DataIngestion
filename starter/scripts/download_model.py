"""Download public, revision-pinned model files only; no inference API or remote code."""
import hashlib
import json
from pathlib import Path
from huggingface_hub import hf_hub_download

root=Path(__file__).resolve().parents[2]
config=json.loads((root/"artifacts/run_config.json").read_text(encoding="utf-8"))
target=root/config["model_dir"]
files=["tokenizer.json","tokenizer_config.json","special_tokens_map.json","config.json",config["onnx_file"]]
manifest={}
for name in files:
    print("Downloading/checking",name,flush=True)
    result=Path(hf_hub_download(repo_id=config["model_name"],filename=name,
                               revision=config["revision"],local_dir=target,token=False))
    manifest[name]={"sha256":hashlib.sha256(result.read_bytes()).hexdigest(),"bytes":result.stat().st_size}
out=root/"artifacts/model_files.json"
out.write_text(json.dumps({"model":config["model_name"],"revision":config["revision"],"files":manifest},indent=2)+"\n",encoding="utf-8")
print("Pinned model files ready; no inference API used.",flush=True)
