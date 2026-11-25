"""读取已完成案例，生成可核对的初步汇总；不判断自然语言的正确性。"""
import argparse
import json
import re
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('directory', type=Path)
args = parser.parse_args()
root = args.directory
report = json.loads((root / '结果.json').read_text(encoding='utf-8'))
rows = []
for case in report['cases']:
    detail = json.loads((root / (case['id'] + '.json')).read_text(encoding='utf-8'))
    issues = []
    for number, turn in enumerate(detail['turns'], 1):
        if turn['execution_status'] != 'completed':
            issues.append(f"第{number}轮中断：{turn.get('error_type', 'Error')}")
        missing = turn.get('expected_tools_not_called', [])
        if missing:
            issues.append(f"第{number}轮未调用预期工具：{', '.join(missing)}（需结合上下文核对）")
        for err in turn.get('tool_errors', []):
            issues.append(f"第{number}轮工具报错：{err['tool']}")
    trace_path = root / detail['trace']
    if trace_path.exists():
        for title, raw in re.findall(r'### ([^\n]+)\n\n```json\n(.*?)\n```', trace_path.read_text(encoding='utf-8'), re.S):
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            result = event.get('result')
            if title == '工具返回' and event.get('tool') == 'lookup_location' and isinstance(result, dict) and result.get('matches') == []:
                issues.append('地点查询有空候选（如随后换名查询成功，应结合完整日志核对）')
            if title == '本轮证据链' and event.get('unresolved_citations'):
                issues.append('证据链有未解析引用：' + ', '.join(map(str, event['unresolved_citations'])))
    rows.append((detail, list(dict.fromkeys(issues))))
lines = ['# 测试初步汇总', '', f"模型：`{report['model']}`；已完成 {report['completed_cases']} / {report['total_cases']} 个案例。", '',
         '本表只检查运行状态、预期工具名称、工具报错、空地点候选和证据链未解析 ID。',
         '没有列出问题并不代表回答正确；古籍适用性、数值、单位和自然语言含义仍需人工核对。', '',
         '| 案例 | 运行状态 | 待核对项 | 详细结果 | 原始日志 |', '| --- | --- | --- | --- | --- |']
for case, issues in rows:
    status = '完成' if all(t['execution_status'] == 'completed' for t in case['turns']) else '包含中断'
    display = '；'.join(issues).replace('|', '\\|') if issues else '未发现上述自动检查项'
    lines.append(f"| {case['id']} {case['title']} | {status} | {display} | [{case['id']}.md]({case['id']}.md) | [原始日志]({case['trace']}) |")
(root / '初步汇总.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('汇总案例数:', len(rows))
