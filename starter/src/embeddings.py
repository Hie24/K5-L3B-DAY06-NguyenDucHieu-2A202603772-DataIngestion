"""Local real ONNX E5 embedding: masked mean pooling and unit normalization."""
import hashlib
from pathlib import Path
from typing import Protocol
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


class Embedder(Protocol):
    model_name: str
    dimensions: int
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, question: str) -> list[float]: ...


class MyEmbedder:
    def __init__(self, model_name: str, model_dir: str | Path, *, revision: str,
                 onnx_file: str, max_tokens: int = 512, batch_size: int = 16,
                 threads: int = 4) -> None:
        self.model_name, self.revision = model_name, revision
        self.dimensions, self.max_tokens, self.batch_size = 384, max_tokens, batch_size
        model_dir = Path(model_dir)
        self.tokenizer = Tokenizer.from_file(str(model_dir/"tokenizer.json"))
        # No truncation: fail explicitly if any input exceeds the locked budget.
        self.tokenizer.no_truncation()
        pad_id = self.tokenizer.token_to_id("<pad>")
        if pad_id is None:
            raise ValueError("Missing expected E5 padding token")
        self.tokenizer.enable_padding(pad_id=pad_id, pad_token="<pad>")
        options = ort.SessionOptions()
        options.intra_op_num_threads, options.inter_op_num_threads = threads, 1
        self.session = ort.InferenceSession(str(model_dir/onnx_file), options,
                                           providers=["CPUExecutionProvider"])
        self.file_hashes = {name:hashlib.sha256((model_dir/name).read_bytes()).hexdigest()
                            for name in ("tokenizer.json",onnx_file)}
        self.last_stats = {}

    def _encode(self, texts: list[str], prefix: str) -> list[list[float]]:
        if any(not isinstance(t,str) or not t.strip() for t in texts):
            raise ValueError("Embedding inputs must be nonempty strings")
        if not texts:
            self.last_stats = {"texts":0,"tokens":0,"max_tokens":0,"truncated":0}
            return []
        vectors, counts = [], []
        for start in range(0,len(texts),self.batch_size):
            encoded = self.tokenizer.encode_batch([prefix+t for t in texts[start:start+self.batch_size]])
            token_counts = [sum(item.attention_mask) for item in encoded]
            if max(token_counts) > self.max_tokens:
                raise ValueError("Input exceeds model token budget; no silent truncation")
            counts.extend(token_counts)
            inputs = {
                "input_ids":np.array([x.ids for x in encoded],dtype=np.int64),
                "attention_mask":np.array([x.attention_mask for x in encoded],dtype=np.int64),
                "token_type_ids":np.array([x.type_ids for x in encoded],dtype=np.int64),
            }
            hidden = self.session.run(None,{i.name:inputs[i.name] for i in self.session.get_inputs()})[0]
            mask = inputs["attention_mask"][...,None].astype(np.float32)
            pooled = (hidden*mask).sum(axis=1)/mask.sum(axis=1)
            norms = np.linalg.norm(pooled,axis=1,keepdims=True)
            if not np.isfinite(pooled).all() or (norms<=0).any():
                raise ValueError("Invalid output from real embedding model")
            pooled = pooled/norms
            if pooled.shape[1] != self.dimensions:
                raise ValueError("Unexpected model dimensions")
            vectors.extend(pooled.tolist())
        self.last_stats = {"texts":len(texts),"tokens":sum(counts),
                           "max_tokens":max(counts),"truncated":0}
        return vectors

    def embed_documents(self,texts):
        return self._encode(texts,"passage: ")

    def embed_queries(self,texts):
        return self._encode(texts,"query: ")

    def embed_query(self,question):
        return self.embed_queries([question])[0]
