import json
import os

log_path = r'C:\Users\prash\.gemini\antigravity-ide\brain\56b3266a-e34d-428e-923f-4646a27357ff\.system_generated\logs\transcript_full.jsonl'
files = {}

for line in open(log_path, encoding='utf-8'):
    step = json.loads(line)
    if 'tool_calls' in step:
        for call in step['tool_calls']:
            args = call.get('args', {})
            if not args:
                args = call.get('arguments', {})
            name = call.get('name')
            
            if name in ('write_to_file', 'default_api:write_to_file'):
                target = args.get('TargetFile')
                if target:
                    files[target.lower()] = (target, args.get('CodeContent', ''))
            elif name in ('replace_file_content', 'default_api:replace_file_content'):
                target = args.get('TargetFile')
                if target and target.lower() in files:
                    orig_target, content = files[target.lower()]
                    if 'TargetContent' in args and 'ReplacementContent' in args:
                        new_content = content.replace(args['TargetContent'], args['ReplacementContent'])
                        files[target.lower()] = (orig_target, new_content)
            elif name in ('multi_replace_file_content', 'default_api:multi_replace_file_content'):
                target = args.get('TargetFile')
                if target and target.lower() in files:
                    orig_target, content = files[target.lower()]
                    for chunk in args.get('ReplacementChunks', []):
                        content = content.replace(chunk['TargetContent'], chunk['ReplacementContent'])
                    files[target.lower()] = (orig_target, content)

count = 0
for _, (path, content) in files.items():
    if path.endswith('.jsx') or path.endswith('.py') or path.endswith('.js') or path.endswith('.css'):
        if 'recover.py' in path: continue
        print(f"Recovering {path}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        count += 1
print(f"Recovery complete. Restored {count} files.")
