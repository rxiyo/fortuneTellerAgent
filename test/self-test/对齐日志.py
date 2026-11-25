"""把已经完成的案例执行日志与结果 JSON 改为相同的案例编号。"""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('directory', type=Path)
parser.add_argument('--final', action='store_true', help='仅在整批运行结束后同步总结果索引')
args = parser.parse_args()
root = args.directory
report_path = root / '结果.json'
report = json.loads(report_path.read_text(encoding='utf-8'))
for recorded in report['cases']:
    case_path = root / (recorded['id'] + '.json')
    case = json.loads(case_path.read_text(encoding='utf-8'))
    old = root / case['trace']
    new = root / '执行日志' / (case['id'] + '.md')
    if old != new:
        if not old.exists() or new.exists():
            raise RuntimeError(f'日志路径异常: {old} -> {new}')
        old.rename(new)
        case['trace'] = str(new.relative_to(root))
        case_path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if args.final:
        recorded['trace'] = case['trace']
if args.final:
    if report.get('completed_cases') != report.get('total_cases') or 'finished_at' not in report:
        raise RuntimeError('测试尚未全部结束，不能同步总结果索引')
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('已对齐案例数:', len(report['cases']))
