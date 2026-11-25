"""为已完成案例生成与原始日志同名的可读结果。"""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('directory', type=Path)
args = parser.parse_args()
root = args.directory
report = json.loads((root / '结果.json').read_text(encoding='utf-8'))
for recorded in report['cases']:
    case = json.loads((root / (recorded['id'] + '.json')).read_text(encoding='utf-8'))
    lines = [f"# {case['id']} {case['title']}", '', f"分类：{case['category']}", '',
             f"[查看原始执行日志]({case['trace']}) · [查看结构化结果]({case['id']}.json)", '',
             '完成表示模型返回了回答，不代表人工核对通过。', '']
    for number, turn in enumerate(case['turns'], 1):
        lines.extend([f'## 第 {number} 轮', '', '### 用户输入', '', turn['input'], '',
                      '### 运行信息', '', f"- 状态：{turn['execution_status']}",
                      f"- 耗时：{turn['elapsed_seconds']} 秒",
                      '- 实际工具调用：' + ('、'.join(turn.get('tool_calls', [])) or '无')])
        if turn.get('expected_tools_not_called'):
            lines.append('- 未调用的预期工具（需结合上下文判断）：' + '、'.join(turn['expected_tools_not_called']))
        if turn.get('tool_errors'):
            lines.append('- 有工具报错，请查看原始执行日志。')
        if turn.get('error'):
            lines.append(f"- 中断原因：{turn.get('error_type', '')} {turn['error']}")
        lines.extend(['', '### 模型回答', '', turn.get('answer') or '本轮没有完整回答，请查看原始日志。', ''])
        if turn.get('expected_checks'):
            lines.extend(['### 待核对', ''] + ['- ' + item for item in turn['expected_checks']] + [''])
    (root / (case['id'] + '.md')).write_text('\n'.join(lines), encoding='utf-8')
print('已整理案例数:', len(report['cases']))
