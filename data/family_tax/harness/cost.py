import json, sys
tin = tout = n = 0
for f in sys.argv[1:]:
    for l in open(f):
        d = json.loads(l)
        if d.get("model") and not d.get("cache_hit"):
            n += 1; tin += d["input_tokens"]; tout += d["output_tokens"]
print(f"live calls {n}, input {tin}, output {tout}, cost ${tin*4/1e6 + tout*20/1e6:.2f} at $4/$20 per M")
