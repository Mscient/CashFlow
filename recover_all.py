import json
import os
import glob

brain_dir = r'C:\Users\prash\.gemini\antigravity-ide\brain'
files = {}

# Find all transcript_full.jsonl files
transcript_paths = glob.glob(os.path.join(brain_dir, '*', '.system_generated', 'logs', 'transcript_full.jsonl'))

# We want to process them chronologically (by creation time or just by reading all of them)
# To be safe, we'll sort them by modification time so we replay them in order
transcript_paths.sort(key=os.path.getmtime)

for log_path in transcript_paths:
    print("Processing", log_path)
    for line in open(log_path, encoding='utf-8'):
        try:
            step = json.loads(line)
        except:
            continue
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