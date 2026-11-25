# Agent 测试目录

- `self-test/测试问题.md`：适合手动复制的测试问题和核对说明。
- `self-test/测试案例.json`：29 个结构化案例，每个案例包含一轮或多轮输入及预期检查。
- `self-test/run_cases.py`：逐案例创建独立 Agent 会话并运行测试的脚本。
- `self-test/result/`：按运行时间和模型分开的result目录。每个案例的 Markdown 和 JSON 保存输入、回答、工具调用、错误、预期工具缺失情况和耗时；`执行日志/` 保存完整执行轨迹和证据。两者使用相同的案例编号，例如 `chart_001.md` 对应 `执行日志/chart_001.md`，结构化文件为 `chart_001.json`。`result.json` 为进度与全部案例汇总，脚本结束时生成 `运行汇总.md`。

在项目根目录运行：

```bash
bazi/bin/python test/self-test/run_cases.py --model qwen3.5:9b
```

只运行指定案例可使用：

```bash
bazi/bin/python test/self-test/run_cases.py --model qwen3.5:9b --case date_001 --case location_001
```

地点查询需要联网；RAG 首次运行可能需要下载模型。脚本的 `completed` 只表示该轮程序返回了回答，`expected_tools_not_called` 是简单的工具名称对照；回答正确性、工具使用是否恰当、古籍引用是否支持结论及 `expected_checks` 仍需逐项核对，不能据此直接判定测试通过。

## MingLi-Bench 对照测试

在 `metaphysics_agent` 目录运行：

```bash
bazi/bin/python test/MingLi-Bench/run_mingli.py
```

需要本机 Ollama 服务和 `qwen3.5:9b` 模型；Agent 的地点查询和首次检索模型下载可能需要网络。默认选 2025 年 40 道题，同题各运行一次无工具模型基线和 Agent，使用上游的 CoT 与八字、紫微预排盘输入，保留选项顺序。结果默认保存到 `test/MingLi-Bench/result/mingli-年份-时间戳/`，每次启动自动创建新目录，终端会显示其完整路径；与自建案例 `self-test/result/` 分开。

例如，只测试前两题时，使用新的输出目录：

```bash
bazi/bin/python test/MingLi-Bench/run_mingli.py --limit 2 --output test/MingLi-Bench/result/tmp
```

`--year 2024` 可切换年份；`--id ftb_0121` 可选题并可重复；`--mode agent` 或 `--mode baseline` 只运行一组。`--num-ctx` 和 `--num-predict` 分别设置 Ollama 上下文容量和单次生成的 token 上限，默认分别为 16384 和服务端配置。`--dry-run` 只检查配置并打印首题提示词，不调用模型。

每完成一项即更新输出目录的 `结果.json`；Agent 轨迹位于 `执行日志/`。续跑时用 `--output` 指定原目录，并使用相同配置（超时时间可以调整），脚本会跳过已记录的项，`--retry-failed` 会重试超时或出错的项；已完成但未解析答案的项不会自动重试。运行中的 `accuracy_all` 以所选全部题数为分母，并非最终分数。不要同时运行两个进程写同一目录。实际回答与答案提取需要人工核查。

本地单次运行不等于项目公开的五轮投票、按命例截尾成绩，详细口径见 `MingLi-Bench/MingLi-Bench基线说明.md`。

MingLi 测试显示已完成项数及当前项已用时间。续跑允许改变超时时限；`--retry-failed` 重新运行超时或报错项，并保留此前尝试和日志。

Agent 根据需要调用工具。MingLi 和自建测试会记录耗时。

Agent 和基线遇到空正文或未能提取选项时，会关闭 thinking 重试一次。发生截断时，已经单独写在完整一行的 `答案：X` 仍可计分，并计入 `completed_with_truncation`。重试后仍无可计分选项时，`status` 记录实际失败原因，例如 `empty_output`、`truncated_output` 或 `unparsed`。结果和 Agent 日志保存 Ollama 返回的停止原因和 token 计数。新结果另记录项目的 Git 提交、Python 源码是否有未提交改动，以及 MingLi-Bench 数据版本。对照旧配置时使用新的输出目录。

### 续跑没有选项和未运行的题目

例如，在 `metaphysics_agent` 目录下，对使用相同版本和配置生成的 2025 年 Agent 结果续跑：

```bash
bazi/bin/python test/MingLi-Bench/run_mingli.py \
  --mode agent \
  --retry-unanswered \
  --output test/MingLi-Bench/result/colab-2025-recheck
```

`--retry-unanswered` 重新运行 `prediction` 为 `null` 的记录，包括超时、报错和程序已返回文字但未提取出选项的情况；没有记录的题目也会运行，已提取出选项的记录会跳过。重跑前的记录保存在 `previous_attempts`，已有执行日志保留，新日志使用不同文件名。进程中断时，重新执行相同命令可继续；仍未提取出选项的记录会再次重试。

`--output` 必须指向包含 `结果.json` 的现有目录。年份、模型、模式、题目范围和代码版本等配置须与原测试一致。`--retry-failed` 会重试所有状态不是 `completed` 的记录。

在 Colab 中，先将新版脚本同步到 Colab，然后使用 `python` 代替 `bazi/bin/python`，并把 `--output` 改成 Google Drive 上该批结果的实际目录。Colab 的 `/content` 环境重置后需要重新准备代码、依赖和 Ollama，再挂载原结果目录续跑。
