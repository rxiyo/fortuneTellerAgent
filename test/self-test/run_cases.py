"""逐案例运行本地 Agent；记录实际输出，不把预期检查自动判成通过。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

TEST_DIR = Path(__file__).resolve().parent
PROJECT = TEST_DIR.parents[1]
sys.path.insert(0, str(PROJECT))
from langchain_core.messages import AIMessage, ToolMessage
from langchain_ollama import ChatOllama
from agent import create_graph
from agent_trace import SessionTrace


def dump(path, data):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default=os.environ.get('OLLAMA_MODEL', 'qwen3.5:9b'))
    parser.add_argument('--base-url', default=os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434'))
    parser.add_argument('--cases-file', type=Path, default=TEST_DIR / '测试案例.json',
                        help='读取指定的 JSON 案例文件（默认：测试案例.json）')
    parser.add_argument('--case', action='append', help='只运行指定案例，可重复；不指定时全部运行')
    args = parser.parse_args()
    cases = json.loads((TEST_DIR / '测试案例.json').read_text(encoding='utf-8'))['cases']
    if args.case:
        cases = [c for c in cases if c['id'] in args.case]
        if len(cases) != len(set(args.case)):
            parser.error('指定的案例 ID 不存在')
    stamp = datetime.now().astimezone().strftime('%Y%m%d-%H%M%S')
    outdir = TEST_DIR / '结果' / f'{stamp}-{args.model.replace(":", "-")}'
    outdir.mkdir(parents=True, exist_ok=False)
    traces = outdir / '执行日志'
    traces.mkdir()
    model = ChatOllama(model=args.model, base_url=args.base_url, temperature=0,
                       num_ctx=int(os.environ.get('OLLAMA_NUM_CTX', '16384')),
                       reasoning=True if args.model.startswith('deepseek-r1') or (
                           args.model.startswith('qwen3') and 'instruct' not in args.model.lower()) else None)
    report = {'model': args.model, 'base_url': args.base_url, 'started_at': datetime.now().astimezone().isoformat(),
              'total_cases': len(cases), 'completed_cases': 0, 'cases': []}
    dump(outdir / '结果.json', report)
    print(f'输出目录：{outdir}', flush=True)
    for case in cases:
        print(f"开始 {len(report['cases']) + 1}/{len(cases)} {case['id']} {case['title']}", flush=True)
        graph = create_graph(model)
        trace = SessionTrace(args.model, traces)
        # 每个案例独立目录下用相同 ID 命名结果和原始执行日志。
        trace.path = trace.path.replace(traces / f"{case['id']}.md")
        history = []
        item = {'id': case['id'], 'category': case['category'], 'title': case['title'],
                'trace': str(trace.path.relative_to(outdir)), 'turns': []}
        for number, turn in enumerate(case['turns'], 1):
            started = time.monotonic()
            print(f"  第 {number}/{len(case['turns'])} 轮", flush=True)
            turn_result = {'input': turn['input'], 'expected_tools': turn.get('expected_tools', []),
                           'expected_checks': turn.get('expected_checks', [])}
            try:
                old_len = len(history)
                messages = trace.run_turn(graph, history, turn['input'])
                added = messages[old_len + 1:]
                calls = [call['name'] for msg in added if isinstance(msg, AIMessage) for call in msg.tool_calls]
                tool_messages = [msg for msg in added if isinstance(msg, ToolMessage)]
                tool_errors = []
                for msg in tool_messages:
                    try:
                        data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    except (ValueError, TypeError):
                        data = msg.content
                    if msg.status == 'error' or isinstance(data, dict) and data.get('error'):
                        tool_errors.append({'tool': msg.name, 'result': data})
                turn_result.update({'execution_status': 'completed', 'answer': messages[-1].text,
                                    'tool_calls': calls, 'tool_errors': tool_errors,
                                    'expected_tools_not_called': [x for x in turn_result['expected_tools'] if x not in calls]})
                history = messages
            except Exception as exc:
                turn_result.update({'execution_status': 'error', 'error_type': type(exc).__name__, 'error': str(exc)})
            turn_result['elapsed_seconds'] = round(time.monotonic() - started, 2)
            item['turns'].append(turn_result)
            print(f"  {turn_result['execution_status']} {turn_result['elapsed_seconds']}秒", flush=True)
            dump(outdir / f"{case['id']}.json", item)
        report['cases'].append(item)
        report['completed_cases'] = len(report['cases'])
        dump(outdir / '结果.json', report)
        # 已完成案例立即生成便于阅读的结果和进度汇总。
        for helper in ('整理结果.py', '生成初步汇总.py'):
            subprocess.run([sys.executable, str(TEST_DIR / helper), str(outdir)], check=True)
    report['finished_at'] = datetime.now().astimezone().isoformat()
    dump(outdir / '结果.json', report)
    lines = ['# Agent 测试运行结果', '', f"模型：`{args.model}`", f"完成案例：{report['completed_cases']}/{report['total_cases']}",
             '', '下表中的“完成”仅表示程序返回了回答，不代表预期检查已通过；具体问题、回答和工具调用见对应 JSON 及执行日志。', '',
             '| 案例 | 分类 | 运行状态 | 每轮耗时（秒） | 文件 |', '| --- | --- | --- | --- | --- |']
    for c in report['cases']:
        status = '完成' if all(t['execution_status'] == 'completed' for t in c['turns']) else '包含异常'
        lines.append(f"| {c['id']} {c['title']} | {c['category']} | {status} | {', '.join(str(t['elapsed_seconds']) for t in c['turns'])} | [{c['id']}]({c['id']}.json) |")
    (outdir / '运行汇总.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('测试完成。', flush=True)


if __name__ == '__main__':
    main()
