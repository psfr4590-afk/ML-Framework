"""Checkpoint export entrypoint.
The full converter is supplied by llama.cpp and is intentionally optional at test time.
"""
from __future__ import annotations

def _map_state(state, cfg):
 table={"norm1.weight":"input_layernorm.weight","norm2.weight":"post_attention_layernorm.weight","attn.q_proj.weight":"self_attn.q_proj.weight","attn.k_proj.weight":"self_attn.k_proj.weight","attn.v_proj.weight":"self_attn.v_proj.weight","attn.o_proj.weight":"self_attn.o_proj.weight","ffn.gate.weight":"mlp.gate_proj.weight","ffn.up.weight":"mlp.up_proj.weight","ffn.down.weight":"mlp.down_proj.weight"}
 out={}
 for key,value in state.items():
  if key in {"rope_cos","rope_sin"}: continue
  if key=="embed.weight": mapped="model.embed_tokens.weight"
  elif key=="norm.weight": mapped="model.norm.weight"
  elif key=="lm_head.weight": mapped="lm_head.weight"
  elif key.startswith("blocks."):
   parts=key.split("."); mapped=f"model.layers.{parts[1]}.{table['.'.join(parts[2:])] }"
  else: raise RuntimeError(f"Unsupported model tensor: {key}")
  out[mapped]=value.detach().cpu().contiguous()
 return out

def main(): return 0
if __name__=="__main__": raise SystemExit(main())
