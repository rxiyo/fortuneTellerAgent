# 命理解读 Agent 执行日志

### 会话开始

```json
{
  "time_utc": "2026-11-20T18:30:20.023+00:00",
  "model": "qwen3.5:9b"
}
```

## 第 1 轮

### 用户输入

```json
{
  "time_utc": "2026-11-20T18:30:20.023+00:00",
  "text": "请查询项目的奇门遁甲工具中，起局有哪些可用方法，需要哪些参数。"
}
```

### 模型思考

```json
{
  "time_utc": "2026-11-20T18:30:25.374+00:00",
  "text": "用户想了解奇门遁甲工具中的起局方法。我需要先查看tianzhi_api的qimen层，了解该层的模块和方法。\n\n让我先使用inspect_tianzhi_api查看qimen层的信息。"
}
```

### 模型请求调用工具

```json
{
  "time_utc": "2026-11-20T18:30:25.374+00:00",
  "tool_calls": [
    {
      "name": "inspect_tianzhi_api",
      "args": {
        "layer": "qimen"
      },
      "id": "70ce16c1-ee27-4ca9-9982-8b7f9caf5b89",
      "type": "tool_call"
    }
  ],
  "invalid_tool_calls": []
}
```

### 工具返回

```json
{
  "time_utc": "2026-11-20T18:30:25.379+00:00",
  "tool": "inspect_tianzhi_api",
  "tool_call_id": "70ce16c1-ee27-4ca9-9982-8b7f9caf5b89",
  "status": "success",
  "result": {
    "layer": "qimen",
    "modules": [
      {
        "name": "geju",
        "description": "奇门吉凶诸格：在排好的盘上逐宫判定。"
      },
      {
        "name": "ju",
        "description": "时家奇门定局：这一时辰属哪一节气、上中下哪一元、阴阳遁第几局。"
      },
      {
        "name": "pan",
        "description": "时家奇门排盘：给定阴阳遁、局数与时干支，布地盘、天盘九星、八门、八神。"
      },
      {
        "name": "qiju",
        "description": "起局：输入一个时刻，一步给出四柱、定局、九宫、成格、旬空、马星。"
      }
    ]
  }
}
```

### 模型思考

```json
{
  "time_utc": "2026-11-20T18:30:33.736+00:00",
  "text": "好的，我看到qimen层有4个子模块：geju（奇门吉凶诸格）、ju（时家奇门定局）、pan（时家奇门排盘）、qiju（起局）。\n\n用户问的是\"起局有哪些可用方法\"，看起来qiju模块就是专门做起局的。让我查看qiju模块的详细信息，看看它有哪些具体方法。"
}
```

### 模型请求调用工具

```json
{
  "time_utc": "2026-11-20T18:30:33.736+00:00",
  "tool_calls": [
    {
      "name": "inspect_tianzhi_api",
      "args": {
        "layer": "qimen",
        "module": "qiju"
      },
      "id": "2d5cddf7-646c-4fc0-aa85-be9057464f62",
      "type": "tool_call"
    }
  ],
  "invalid_tool_calls": []
}
```

### 工具返回

```json
{
  "time_utc": "2026-11-20T18:30:33.741+00:00",
  "tool": "inspect_tianzhi_api",
  "tool_call_id": "2d5cddf7-646c-4fc0-aa85-be9057464f62",
  "status": "success",
  "result": {
    "layer": "qimen",
    "module": "qiju",
    "tools": [
      {
        "name": "qimen.qiju.xun_kong",
        "description": "qimen.qiju.xun_kong\nxun_kong(gz: 'str') -> 'str'\n→ str\n\n旬空二支：本旬十干用尽所余之二支"
      },
      {
        "name": "qimen.qiju.ma_xing",
        "description": "qimen.qiju.ma_xing\nma_xing(gz: 'str') -> 'str'\n→ str\n\n（无说明）"
      },
      {
        "name": "qimen.qiju.qiju",
        "description": "qimen.qiju.qiju\nqiju(dt: 'datetime', *, method: 'str' = 'zhirun', rule: 'str' = 'qian_yuan_hou_jin', pan_method: 'str' = 'zhuan', names: 'str' = 'default') -> 'dict'\n→ dict\n\n为这一时刻起一局时家奇门。\n\n:param dt: 起局时刻，北京时间（naive 按东八区理解）。用真太阳时的话由调用方先换算好再传入。\n返回 {sizhu, ju, pan, geju, kong, ma, options}：\n  sizhu  年月日时四柱（日以子初换，与本包八字默认一致）\n  ju     定局结果（节气、元、遁、局、符头、正授/超神/接气/置闰）\n  pan    九宫（见 pan.build）\n  geju   成格（见 geju.find）\n  kong   时旬空亡之二支及其所落之宫；ma 时支驿马及其宫"
      }
    ]
  }
}
```

### 模型思考

```json
{
  "time_utc": "2026-11-20T18:30:45.660+00:00",
  "text": "好的，我看到qiju模块下有一个主要方法 qimen.qiju.qiju，这是起局的核心方法。让我查看这个方法的详细参数说明。\n\n另外，我还看到有 xun_kong（旬空）和 ma_xing（驿马）两个辅助方法。让我再查看一下这两个方法的详情，以及 pan 模块的排盘方法，因为 qiju 返回的 pan 需要进一步查看。"
}
```

### 模型请求调用工具

```json
{
  "time_utc": "2026-11-20T18:30:45.660+00:00",
  "tool_calls": [
    {
      "name": "inspect_tianzhi_api",
      "args": {
        "name": "qimen.qiju.qiju"
      },
      "id": "667cef85-3af2-4eb4-ba2f-c213b01fdabc",
      "type": "tool_call"
    }
  ],
  "invalid_tool_calls": []
}
```

### 工具返回

```json
{
  "time_utc": "2026-11-20T18:30:45.674+00:00",
  "tool": "inspect_tianzhi_api",
  "tool_call_id": "667cef85-3af2-4eb4-ba2f-c213b01fdabc",
  "status": "success",
  "result": {
    "name": "qimen.qiju.qiju",
    "description": "qimen.qiju.qiju\nqiju(dt: 'datetime', *, method: 'str' = 'zhirun', rule: 'str' = 'qian_yuan_hou_jin', pan_method: 'str' = 'zhuan', names: 'str' = 'default') -> 'dict'\n→ dict\n\n为这一时刻起一局时家奇门。\n\n:param dt: 起局时刻，北京时间（naive 按东八区理解）。用真太阳时的话由调用方先换算好再传入。\n返回 {sizhu, ju, pan, geju, kong, ma, options}：\n  sizhu  年月日时四柱（日以子初换，与本包八字默认一致）\n  ju     定局结果（节气、元、遁、局、符头、正授/超神/接气/置闰）\n  pan    九宫（见 pan.build）\n  geju   成格（见 geju.find）\n  kong   时旬空亡之二支及其所落之宫；ma 时支驿马及其宫"
  }
}
```

### 模型思考

```json
{
  "time_utc": "2026-11-20T18:30:52.777+00:00",
  "text": "好的，我已经了解了 qiju.qiju 方法的参数。现在让我查看一下 pan 模块的排盘方法，因为 qiju 返回的 pan 需要进一步查看其详细结构。"
}
```

### 模型请求调用工具

```json
{
  "time_utc": "2026-11-20T18:30:52.778+00:00",
  "tool_calls": [
    {
      "name": "inspect_tianzhi_api",
      "args": {
        "layer": "qimen",
        "module": "pan"
      },
      "id": "69702f6f-3336-4f67-8726-c386f4aff6ad",
      "type": "tool_call"
    }
  ],
  "invalid_tool_calls": []
}
```

### 工具返回

```json
{
  "time_utc": "2026-11-20T18:30:52.782+00:00",
  "tool": "inspect_tianzhi_api",
  "tool_call_id": "69702f6f-3336-4f67-8726-c386f4aff6ad",
  "status": "success",
  "result": {
    "layer": "qimen",
    "module": "pan",
    "tools": [
      {
        "name": "qimen.pan.dipan",
        "description": "qimen.pan.dipan\ndipan(yang: 'bool', ju: 'int') -> 'dict[int, str]'\n→ dict[int, str]\n\n地盘：宫 → 干。本局之宫起戊，阳遁按宫数顺布、阴遁逆布，干序戊己庚辛壬癸丁丙乙"
      },
      {
        "name": "qimen.pan.xun_of",
        "description": "qimen.pan.xun_of\nxun_of(gz: 'str') -> 'tuple[str, str]'\n→ tuple[str, str]\n\n干支所在之旬：(旬首如「甲子」, 所隐之仪如「戊」)"
      },
      {
        "name": "qimen.pan.build",
        "description": "qimen.pan.build\nbuild(yang: 'bool', ju: 'int', hour_gz: 'str', *, method: 'str' = 'zhuan', names: 'str' = 'default') -> 'Pan'\n→ Pan\n\n排一个时辰的盘。\n\n:param yang: 阳遁为 True\n:param ju: 局数 1..9\n:param hour_gz: 时干支，如「丙寅」\n:param method: \"zhuan\" 转盘（默认，《演義》）/ \"xieji_fei\" 九星飞布八门转（《協紀》）\n:param names: 八神名号，\"default\" 白虎玄武 / \"gouchen\" 勾陈朱雀"
      }
    ]
  }
}
```

### 模型思考

```json
{
  "time_utc": "2026-11-20T18:31:11.050+00:00",
  "text": "好的，现在我已经了解了奇门遁甲起局的主要方法。让我总结一下：\n\n1. **qimen.qiju.qiju** - 这是核心起局方法，一步给出四柱、定局、九宫、成格、旬空、马星\n   - 参数：dt（起局时刻）、method（排盘方法）、rule（定局规则）、pan_method（排盘方式）、names（八神名号）\n\n2. **qimen.pan.build** - 排一个时辰的盘，需要阳遁/阴遁、局数、时干支等参数\n\n3. **qimen.pan.dipan** - 布地盘，宫→干\n\n4. **qimen.pan.xun_of** - 查询干支所在之旬\n\n5. **qimen.qiju.xun_kong** - 查旬空二支\n\n6. **qimen.qiju.ma_xing** - 查驿马星\n\n7. **qimen.ju** - 时家奇门定局，判断节气、元、遁、局等\n\n8. **qimen.geju** - 奇门吉凶诸格判定\n\n让我再查看一下 ju 和 geju 模块的详细信息。"
}
```

### 模型请求调用工具

```json
{
  "time_utc": "2026-11-20T18:31:11.051+00:00",
  "tool_calls": [
    {
      "name": "inspect_tianzhi_api",
      "args": {
        "name": "qimen.ju"
      },
      "id": "941518e0-45c9-4669-826b-bbe95b929184",
      "type": "tool_call"
    }
  ],
  "invalid_tool_calls": []
}
```

### 工具返回

```json
{
  "time_utc": "2026-11-20T18:31:11.060+00:00",
  "tool": "inspect_tianzhi_api",
  "tool_call_id": "941518e0-45c9-4669-826b-bbe95b929184",
  "status": "success",
  "result": {
    "error": "目录中没有方法：qimen.ju",
    "layers": [
      "calendar",
      "core",
      "bazi",
      "liuren",
      "qimen",
      "ziwei"
    ]
  }
}
```

### 模型思考

```json
{
  "time_utc": "2026-11-20T18:31:15.341+00:00",
  "text": "看来 qimen.ju 不是一个独立的方法，而是模块名。让我查看 ju 模块的详细信息。"
}
```

### 模型请求调用工具

```json
{
  "time_utc": "2026-11-20T18:31:15.341+00:00",
  "tool_calls": [
    {
      "name": "inspect_tianzhi_api",
      "args": {
        "layer": "qimen",
        "module": "ju"
      },
      "id": "1e4d84ec-c3be-4c23-b02e-5d29b7199f49",
      "type": "tool_call"
    }
  ],
  "invalid_tool_calls": []
}
```

### 工具返回

```json
{
  "time_utc": "2026-11-20T18:31:15.346+00:00",
  "tool": "inspect_tianzhi_api",
  "tool_call_id": "1e4d84ec-c3be-4c23-b02e-5d29b7199f49",
  "status": "success",
  "result": {
    "layer": "qimen",
    "module": "ju",
    "tools": [
      {
        "name": "qimen.ju.day_ganzhi",
        "description": "qimen.ju.day_ganzhi\nday_ganzhi(d: 'date') -> 'str'\n→ str\n\n某日的日干支（儒略日数推算，与 bazi.chart 同法）"
      },
      {
        "name": "qimen.ju.ju_of",
        "description": "qimen.ju.ju_of\nju_of(dt: 'datetime', *, method: 'str' = 'zhirun', rule: 'str' = 'qian_yuan_hou_jin') -> 'dict'\n→ dict\n\n这一时刻的局。\n\n返回 jieqi（所用节气）、jieqi_time（该节气交节时刻）、yuan（上/中/下）、dun（阳/阴）、ju（1–9）、\nfutou（本元符头日干支）、futou_date、mode（正授/超神/接气/置闰/拆补）、run（是否闰局）。\n置闰法另返回 shangyuan_date（本节上元符头之日）。"
      }
    ]
  }
}
```

### 模型思考

```json
{
  "time_utc": "2026-11-20T18:31:20.605+00:00",
  "text": "好的，现在让我查看 geju 模块的详细信息。"
}
```

### 模型请求调用工具

```json
{
  "time_utc": "2026-11-20T18:31:20.606+00:00",
  "tool_calls": [
    {
      "name": "inspect_tianzhi_api",
      "args": {
        "layer": "qimen",
        "module": "geju"
      },
      "id": "18c56569-3bad-4ede-a2a0-bb07c289a263",
      "type": "tool_call"
    }
  ],
  "invalid_tool_calls": []
}
```

### 工具返回

```json
{
  "time_utc": "2026-11-20T18:31:20.609+00:00",
  "tool": "inspect_tianzhi_api",
  "tool_call_id": "18c56569-3bad-4ede-a2a0-bb07c289a263",
  "status": "success",
  "result": {
    "layer": "qimen",
    "module": "geju",
    "tools": [
      {
        "name": "qimen.geju.find",
        "description": "qimen.geju.find\nfind(pan: 'dict', *, day: 'str | None' = None, month: 'str | None' = None, year: 'str | None' = None) -> 'list[dict]'\n→ list[dict]\n\n这一盘成哪些格。day/month/year 为日、月、年干支（判伏干、飞干、岁月格与五不遇时要用；缺则跳过相关格）。\n\n返回 [{name, verdict, gong, cite, quote}]；gong 为 None 表示整盘之格（如五不遇时、伏吟）。"
      }
    ]
  }
}
```

### 模型思考

```json
{
  "time_utc": "2026-11-20T18:32:58.447+00:00",
  "text": "好的，现在我已经了解了奇门遁甲工具中起局相关的所有方法。让我整理一下给用户一个清晰的回答。\n\n主要起局方法是 qimen.qiju.qiju，它是一步完成的方法。其他辅助方法包括：\n- qimen.ju.ju_of：单独定局\n- qimen.pan.build：排盘\n- qimen.pan.dipan：布地盘\n- qimen.pan.xun_of：查旬首\n- qimen.qiju.xun_kong：查旬空\n- qimen.qiju.ma_xing：查驿马\n- qimen.geju.find：查成格\n\n让我把这些信息整理清楚给用户。"
}
```

### 模型最终回复

```json
{
  "time_utc": "2026-11-20T18:32:58.448+00:00",
  "text": "根据工具目录查询，奇门遁甲（qimen）层中**起局相关的方法**如下：\n\n---\n\n## 一、核心起局方法\n\n### `qimen.qiju.qiju`\n一步完成时家奇门起局，返回四柱、定局、九宫、成格、旬空、马星等完整信息。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `dt` | datetime | 起局时刻，北京时间（naive按东八区理解）。若用真太阳时，需调用方先换算好再传入 |\n| `method` | str | 排盘方法，默认 `\"zhirun\"` |\n| `rule` | str | 定局规则，默认 `\"qian_yuan_hou_jin\"`（千元后尽） |\n| `pan_method` | str | 排盘方式，默认 `\"zhuan\"`（转盘，《演義》），也可用 `\"xieji_fei\"`（九星飞布八门转，《協紀》） |\n| `names` | str | 八神名号，默认 `\"default\"`（白虎玄武），也可用 `\"gouchen\"`（勾陈朱雀） |\n\n**返回结构：**\n```python\n{\n    \"sizhu\":   # 年月日时四柱（日以子初换）\n    \"ju\":      # 定局结果（节气、元、遁、局、符头、正授/超神/接气/置闰）\n    \"pan\":     # 九宫排盘（见 pan.build）\n    \"geju\":    # 成格（见 geju.find）\n    \"kong\":    # 时旬空亡之二支及其所落之宫\n    \"ma\":      # 时支驿马及其宫\n    \"options\": # 其他选项\n}\n```\n\n---\n\n## 二、辅助方法\n\n### `qimen.ju.ju_of`\n单独查询某一时刻的局信息（节气、元、遁、局等）。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `dt` | datetime | 起局时刻 |\n| `method` | str | 排盘方法，默认 `\"zhirun\"` |\n| `rule` | str | 定局规则，默认 `\"qian_yuan_hou_jin\"` |\n\n**返回：**\n```python\n{\n    \"jieqi\":        # 所用节气\n    \"jieqi_time\":   # 该节气交节时刻\n    \"yuan\":         # 上/中/下元\n    \"dun\":          # 阳遁/阴遁\n    \"ju\":           # 局数 1–9\n    \"futou\":        # 本元符头日干支\n    \"futou_date\":   # 符头日期\n    \"mode\":         # 正授/超神/接气/置闰/拆补\n    \"run\":          # 是否闰局\n    \"shangyuan_date\": # （置闰法时返回）本节上元符头之日\n}\n```\n\n### `qimen.pan.build`\n排一个时辰的盘。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `yang` | bool | 阳遁为 True，阴遁为 False |\n| `ju` | int | 局数 1–9 |\n| `hour_gz` | str | 时干支，如 `\"丙寅\"` |\n| `method` | str | 排盘方式，默认 `\"zhuan\"`（转盘），也可用 `\"xieji_fei\"`（九星飞布八门转） |\n| `names` | str | 八神名号，默认 `\"default\"`（白虎玄武），也可用 `\"gouchen\"`（勾陈朱雀） |\n\n### `qimen.pan.dipan`\n布地盘：宫 → 干。本局之宫起戊，阳遁按宫数顺布、阴遁逆布。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `yang` | bool | 阳遁为 True |\n| `ju` | int | 局数 |\n\n### `qimen.pan.xun_of`\n查询干支所在之旬：返回 `(旬首如「甲子」, 所隐之仪如「戊」)`。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `gz` | str | 干支，如 `\"丙寅\"` |\n\n### `qimen.qiju.xun_kong`\n查询旬空二支：本旬十干用尽所余之二支。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `gz` | str | 时干支 |\n\n### `qimen.qiju.ma_xing`\n查询驿马星（无详细说明）。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `gz` | str | 时干支 |\n\n### `qimen.geju.find`\n查询这一盘成哪些格。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `pan` | dict | 排好的九宫盘 |\n| `day` | str | 日干支（判伏干、飞干） |\n| `month` | str | 月干支（判岁月格） |\n| `year` | str | 年干支（判岁月格与五不遇时） |\n\n**返回：**\n```python\n[{\n    \"name\":     # 格名\n    \"verdict\":  # 断语\n    \"gong\":     # 所落宫位（None表示整盘之格，如五不遇时、伏吟）\n    \"cite\":     # 引用出处\n    \"quote\":    # 引用原文\n}]\n```\n\n---\n\n## 三、使用建议\n\n**推荐流程：**\n1. 若只需起局：直接调用 `qimen.qiju.qiju(dt=...)`，一步完成。\n2. 若需分步操作：\n   - 先用 `qimen.ju.ju_of(dt=...)` 定局（节气、元、遁、局）\n   - 再用 `qimen.pan.build(yang, ju, hour_gz, ...)` 排盘\n   - 最后用 `qimen.geju.find(pan, day, month, year)` 查成格\n\n**注意：**\n- `dt` 参数建议使用北京时间（naive datetime），若需真太阳时，请调用方先换算。\n- 定局规则 `\"qian_yuan_hou_jin\"` 为默认，也可根据流派需求调整。"
}
```

### 本轮证据链

```json
{
  "time_utc": "2026-11-20T18:32:58.450+00:00",
  "turn": 1,
  "question": "请查询项目的奇门遁甲工具中，起局有哪些可用方法，需要哪些参数。",
  "facts": {
    "chart": null,
    "chart_inputs": null,
    "calculation_results": {},
    "date_info": null,
    "birth_date_info": null,
    "location_search": null
  },
  "answer": "根据工具目录查询，奇门遁甲（qimen）层中**起局相关的方法**如下：\n\n---\n\n## 一、核心起局方法\n\n### `qimen.qiju.qiju`\n一步完成时家奇门起局，返回四柱、定局、九宫、成格、旬空、马星等完整信息。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `dt` | datetime | 起局时刻，北京时间（naive按东八区理解）。若用真太阳时，需调用方先换算好再传入 |\n| `method` | str | 排盘方法，默认 `\"zhirun\"` |\n| `rule` | str | 定局规则，默认 `\"qian_yuan_hou_jin\"`（千元后尽） |\n| `pan_method` | str | 排盘方式，默认 `\"zhuan\"`（转盘，《演義》），也可用 `\"xieji_fei\"`（九星飞布八门转，《協紀》） |\n| `names` | str | 八神名号，默认 `\"default\"`（白虎玄武），也可用 `\"gouchen\"`（勾陈朱雀） |\n\n**返回结构：**\n```python\n{\n    \"sizhu\":   # 年月日时四柱（日以子初换）\n    \"ju\":      # 定局结果（节气、元、遁、局、符头、正授/超神/接气/置闰）\n    \"pan\":     # 九宫排盘（见 pan.build）\n    \"geju\":    # 成格（见 geju.find）\n    \"kong\":    # 时旬空亡之二支及其所落之宫\n    \"ma\":      # 时支驿马及其宫\n    \"options\": # 其他选项\n}\n```\n\n---\n\n## 二、辅助方法\n\n### `qimen.ju.ju_of`\n单独查询某一时刻的局信息（节气、元、遁、局等）。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `dt` | datetime | 起局时刻 |\n| `method` | str | 排盘方法，默认 `\"zhirun\"` |\n| `rule` | str | 定局规则，默认 `\"qian_yuan_hou_jin\"` |\n\n**返回：**\n```python\n{\n    \"jieqi\":        # 所用节气\n    \"jieqi_time\":   # 该节气交节时刻\n    \"yuan\":         # 上/中/下元\n    \"dun\":          # 阳遁/阴遁\n    \"ju\":           # 局数 1–9\n    \"futou\":        # 本元符头日干支\n    \"futou_date\":   # 符头日期\n    \"mode\":         # 正授/超神/接气/置闰/拆补\n    \"run\":          # 是否闰局\n    \"shangyuan_date\": # （置闰法时返回）本节上元符头之日\n}\n```\n\n### `qimen.pan.build`\n排一个时辰的盘。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `yang` | bool | 阳遁为 True，阴遁为 False |\n| `ju` | int | 局数 1–9 |\n| `hour_gz` | str | 时干支，如 `\"丙寅\"` |\n| `method` | str | 排盘方式，默认 `\"zhuan\"`（转盘），也可用 `\"xieji_fei\"`（九星飞布八门转） |\n| `names` | str | 八神名号，默认 `\"default\"`（白虎玄武），也可用 `\"gouchen\"`（勾陈朱雀） |\n\n### `qimen.pan.dipan`\n布地盘：宫 → 干。本局之宫起戊，阳遁按宫数顺布、阴遁逆布。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `yang` | bool | 阳遁为 True |\n| `ju` | int | 局数 |\n\n### `qimen.pan.xun_of`\n查询干支所在之旬：返回 `(旬首如「甲子」, 所隐之仪如「戊」)`。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `gz` | str | 干支，如 `\"丙寅\"` |\n\n### `qimen.qiju.xun_kong`\n查询旬空二支：本旬十干用尽所余之二支。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `gz` | str | 时干支 |\n\n### `qimen.qiju.ma_xing`\n查询驿马星（无详细说明）。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `gz` | str | 时干支 |\n\n### `qimen.geju.find`\n查询这一盘成哪些格。\n\n| 参数 | 类型 | 说明 |\n|------|------|------|\n| `pan` | dict | 排好的九宫盘 |\n| `day` | str | 日干支（判伏干、飞干） |\n| `month` | str | 月干支（判岁月格） |\n| `year` | str | 年干支（判岁月格与五不遇时） |\n\n**返回：**\n```python\n[{\n    \"name\":     # 格名\n    \"verdict\":  # 断语\n    \"gong\":     # 所落宫位（None表示整盘之格，如五不遇时、伏吟）\n    \"cite\":     # 引用出处\n    \"quote\":    # 引用原文\n}]\n```\n\n---\n\n## 三、使用建议\n\n**推荐流程：**\n1. 若只需起局：直接调用 `qimen.qiju.qiju(dt=...)`，一步完成。\n2. 若需分步操作：\n   - 先用 `qimen.ju.ju_of(dt=...)` 定局（节气、元、遁、局）\n   - 再用 `qimen.pan.build(yang, ju, hour_gz, ...)` 排盘\n   - 最后用 `qimen.geju.find(pan, day, month, year)` 查成格\n\n**注意：**\n- `dt` 参数建议使用北京时间（naive datetime），若需真太阳时，请调用方先换算。\n- 定局规则 `\"qian_yuan_hou_jin\"` 为默认，也可根据流派需求调整。",
  "references": [],
  "unresolved_citations": []
}
```
