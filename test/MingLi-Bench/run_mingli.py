"""Run MingLi-Bench questions against the agent and a no-tools Ollama baseline."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import threading
from uuid import uuid4
from tqdm import tqdm

PROJECT = Path(__file__).resolve().parents[2]
BENCH = PROJECT.parent / 'MingLi-Bench'
sys.path[:0] = [str(PROJECT), str(BENCH)]
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from mingli_bench.benchmark import FortuneTellingBenchmark
from mingli_bench.models.base import ModelClient
from agent import create_graph
from agent_trace import SessionTrace


def dump(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    temp.replace(path)


def on_timeout(signum, frame):
    raise TimeoutError('超过单题运行时限')


def make_budget_hint(started, timeout, round_budget):
    def hint(state):
        messages = state['messages']
        last_user = next((i for i in range(len(messages) - 1, -1, -1)
                          if isinstance(messages[i], HumanMessage)), -1)
        rounds = sum(isinstance(m, AIMessage) and bool(m.tool_calls) for m in messages[last_user + 1:])
        remaining = max(0, int(timeout - (time.monotonic() - started)))
        urgency = ('预算已接近或达到，请停止重复查询，基于已有材料尽快给出最终回答。'
                   if rounds >= round_budget or remaining <= max(120, timeout * 0.2)
                   else '请优先完成必要的查询，并避免重复检索和无关计算。')
        return (f'本次测试的时间预算约为 {timeout} 秒，目前约剩 {remaining} 秒；'
                f'已执行 {rounds} 轮工具请求，建议不超过 {round_budget} 轮。{urgency}'
                '这是软性建议，时间只是本次调用开始时的估计，不能保证下一次生成及时结束。'
                '不得猜测缺失的出生资料、工具结果或引用；依据不足时如实说明。'
                '最终回答若能选择，请按题目要求使用“答案：X”。')
    return hint


def extract_explicit(answer):
    cleaned = re.sub(r'[*_`]', '', answer)
    matches = re.findall(r'(?:答案|选择|选项)\s*(?:是|为)?\s*[：:]?\s*[（(]?([A-D])(?:[）)]|\b|(?=[。\s]|$))', cleaned, re.I)
    if matches:
        return matches[-1].upper()
    matches = re.findall(r'^\s*([A-D])\s*[。.]?\s*$', cleaned, re.M | re.I)
    return matches[-1].upper() if matches else None


def stats(records, ids, modes):
    result = {}
    for mode in modes:
        items = [records.get(mode + ':' + qid) for qid in ids]
        done = [x for x in items if x]
        result[mode] = {'total': len(ids), 'attempted': len(done),
            'completed': sum(x['status'] == 'completed' for x in done),
            'timeout': sum(x['status'] == 'timeout' for x in done),
            'error': sum(x['status'] == 'error' for x in done),
            'unparsed': sum(x['status'] == 'completed' and x['prediction'] is None for x in done),
            'correct': sum(x['correct'] is True for x in done),
            'accuracy_all': sum(x['correct'] is True for x in done) / len(ids) if ids else None,
            'accuracy_answered': (sum(x['correct'] is True for x in done) / sum(x['prediction'] is not None for x in done)) if any(x['prediction'] is not None for x in done) else None}
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', default='qwen3.5:9b')
    p.add_argument('--base-url', default=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'))
    p.add_argument('--year', type=int, default=2025)
    p.add_argument('--id', action='append', dest='ids')
    p.add_argument('--category', action='append')
    p.add_argument('--limit', type=int)
    p.add_argument('--mode', choices=['both', 'agent', 'baseline'], default='both')
    p.add_argument('--timeout', type=int, default=900, help='单题总时限（秒），默认 900')
    p.add_argument('--tool-round-budget', type=int, default=8, help='提示模型的建议工具请求轮数；不是硬限制')
    p.add_argument('--output', type=Path,
                   help='结果目录；省略时自动创建带时间戳的新目录；指定旧目录可续跑')
    p.add_argument('--retry-failed', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    if args.timeout < 1:
        p.error('--timeout 必须大于 0')
    if args.tool_round_budget < 1:
        p.error('--tool-round-budget 必须大于 0')
    bench = FortuneTellingBenchmark(None, str(BENCH / 'data/data.json'))
    loader = bench.data_loader
    loader.fortune_data_path = BENCH / 'data/fortune_api_results.json'
    loader.astro_data_path = BENCH / 'data/data_with_astro.json'
    questions = loader.load_questions(use_astro=True, year=args.year, categories=args.category, shuffle=False)
    if args.ids:
        requested = set(args.ids)
        questions = [q for q in questions if q['id'] in requested]
        if {q['id'] for q in questions} != requested:
            p.error('题目 ID 不存在或不符合年份/类别筛选')
    if args.limit is not None:
        if args.limit < 1: p.error('--limit 必须大于 0')
        questions = questions[:args.limit]
    if not questions: p.error('没有匹配题目')
    fortune = loader.data['fortune_data']
    for q in questions:
        entry = fortune.get(q['case_id'], {}).get('api_response', {})
        if not entry.get('success') or not entry.get('data', {}).get('data'):
            p.error(f"缺少预排盘: {q['id']}")
    try:
        revision = subprocess.check_output(['git', '-C', str(BENCH), 'rev-parse', 'HEAD'], text=True).strip()
    except Exception:
        revision = 'unknown'
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [BENCH/'data/data.json', BENCH/'data/fortune_api_results.json']}
    modes = ['baseline', 'agent'] if args.mode == 'both' else [args.mode]
    config = {'model': args.model, 'base_url': args.base_url, 'year': args.year, 'question_ids': [q['id'] for q in questions],
              'modes': modes, 'timeout_seconds': args.timeout, 'temperature': 0, 'num_ctx': 16384,
              'precomputed_chart': True, 'cot': True, 'bench_git_revision': revision, 'data_sha256': hashes,
              'agent_budget_hint': {'version': 1, 'tool_round_budget': args.tool_round_budget}}
    if args.dry_run:
        print(json.dumps({'config':config,'example_prompt':bench._prepare_prompt(questions[0], True, True)},ensure_ascii=False,indent=2)); return
    if args.output is None:
        root = PROJECT / 'test/MingLi-Bench/result'
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone().strftime('%y%m%d-%H%M%S')
        base = f'mingli-{args.year}-{stamp}'
        for number in range(1000):
            candidate = root / (base if number == 0 else f'{base}-{number}')
            try:
                candidate.mkdir()
                args.output = candidate
                break
            except FileExistsError:
                continue
        else:
            raise RuntimeError('无法创建唯一的测试结果目录')
    else:
        args.output.mkdir(parents=True, exist_ok=True)
    print(f'结果目录：{args.output.resolve()}', flush=True)
    report_path = args.output / '结果.json'
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding='utf-8'))
        previous = report['config']
        if {k: v for k, v in previous.items() if k != 'timeout_seconds'} != {k: v for k, v in config.items() if k != 'timeout_seconds'}:
            p.error('输出目录的配置与本次不一致，不能恢复；请使用原配置或新目录')
        if previous['timeout_seconds'] != args.timeout:
            report.setdefault('timeout_changes', []).append({'from': previous['timeout_seconds'], 'to': args.timeout,
                                                             'at': datetime.now(timezone.utc).isoformat()})
            report['config'] = config
    else:
        report = {'config': config, 'started_at': datetime.now(timezone.utc).isoformat(), 'records': {}}
    dump(report_path, report)
    records = report['records']
    model = ChatOllama(model=args.model, base_url=args.base_url, temperature=0, num_ctx=16384,
                       client_kwargs={'timeout': args.timeout + 30},
                       reasoning=True if args.model.startswith('deepseek-r1') or (args.model.startswith('qwen3') and 'instruct' not in args.model.lower()) else None)
    signal.signal(signal.SIGALRM, on_timeout)
    keys = [mode + ':' + q['id'] for q in questions for mode in modes]
    skipped = sum(k in records and not (args.retry_failed and records[k]['status'] != 'completed') for k in keys)
    progress = tqdm(total=len(keys), initial=skipped, desc='评测进度', unit='项', dynamic_ncols=True)
    for q in questions:
        prompt = bench._prepare_prompt(q, use_cot=True, use_astro=True)
        for mode in modes:
            key = mode + ':' + q['id']
            if key in records and not (args.retry_failed and records[key]['status'] != 'completed'): continue
            tqdm.write('运行 ' + key)
            item = {'id': q['id'], 'case_id': q['case_id'], 'category': q.get('category'), 'mode': mode,
                    'prompt': prompt, 'correct_answer': q['answer'], 'status': 'error', 'prediction': None,
                    'prediction_official_extractor': None, 'correct': False, 'timeout_seconds': args.timeout}
            if key in records:
                previous_attempt = records[key]
                item['previous_attempts'] = previous_attempt.pop('previous_attempts', []) + [previous_attempt]
            started = time.monotonic()
            stop_heartbeat = threading.Event()
            def heartbeat():
                while not stop_heartbeat.wait(1):
                    progress.set_postfix_str(f'{key} 已用 {int(time.monotonic()-started)}s / {args.timeout}s')
            thread = threading.Thread(target=heartbeat, daemon=True)
            thread.start()
            try:
                signal.alarm(args.timeout)
                if mode == 'agent':
                    trace = SessionTrace(args.model, args.output / '执行日志')
                    trace_dir = args.output / '执行日志'
                    trace_path = trace_dir / (q['id'] + '.md')
                    if trace_path.exists():
                        trace_path = trace_dir / (q['id'] + '-' + uuid4().hex[:8] + '.md')
                    trace.path = trace.path.replace(trace_path)
                    item['trace'] = str(trace.path.relative_to(args.output))
                    graph = create_graph(model, budget_hint=make_budget_hint(started, args.timeout, args.tool_round_budget))
                    messages = trace.run_turn(graph, [], prompt)
                    answer = messages[-1].text
                else:
                    item['system_prompt'] = ModelClient.SYSTEM_PROMPT
                    answer = model.invoke([SystemMessage(content=ModelClient.SYSTEM_PROMPT), HumanMessage(content=prompt)]).text
                item.update(status='completed', answer=answer, prediction=extract_explicit(answer),
                            prediction_official_extractor=bench._extract_answer(answer, True))
                item['correct'] = item['prediction'] == q['answer']
            except TimeoutError as exc:
                item.update(status='timeout', error=str(exc))
            except Exception as exc:
                item.update(status='timeout' if 'timeout' in type(exc).__name__.lower() else 'error', error=type(exc).__name__ + ': ' + str(exc))
            finally:
                signal.alarm(0)
                stop_heartbeat.set()
                thread.join()
            item['elapsed_seconds'] = round(time.monotonic()-started, 2)
            records[key] = item
            report['stats'] = stats(records, config['question_ids'], modes)
            report['updated_at'] = datetime.now(timezone.utc).isoformat()
            dump(report_path, report)
            progress.update(1)
            tqdm.write(f"{item['status']} {item['elapsed_seconds']} {item['prediction']}")
    progress.close()
    print(json.dumps(report['stats'], ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
