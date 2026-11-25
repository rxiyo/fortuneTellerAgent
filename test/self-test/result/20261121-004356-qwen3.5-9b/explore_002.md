# explore_002 查询奇门遁甲工具

分类：其他术数探索

[查看原始执行日志](执行日志/explore_002.md) · [查看结构化结果](explore_002.json)

完成表示模型返回了回答，不代表人工核对通过。

## 第 1 轮

### 用户输入

请查询项目的奇门遁甲工具中，起局有哪些可用方法，需要哪些参数。

### 运行信息

- 状态：completed
- 耗时：158.43 秒
- 实际工具调用：inspect_tianzhi_api、inspect_tianzhi_api、inspect_tianzhi_api、inspect_tianzhi_api、inspect_tianzhi_api、inspect_tianzhi_api、inspect_tianzhi_api
- 有工具报错，请查看原始执行日志。

### 模型回答

根据工具目录查询，奇门遁甲（qimen）层中**起局相关的方法**如下：

---

## 一、核心起局方法

### `qimen.qiju.qiju`
一步完成时家奇门起局，返回四柱、定局、九宫、成格、旬空、马星等完整信息。

| 参数 | 类型 | 说明 |
|------|------|------|
| `dt` | datetime | 起局时刻，北京时间（naive按东八区理解）。若用真太阳时，需调用方先换算好再传入 |
| `method` | str | 排盘方法，默认 `"zhirun"` |
| `rule` | str | 定局规则，默认 `"qian_yuan_hou_jin"`（千元后尽） |
| `pan_method` | str | 排盘方式，默认 `"zhuan"`（转盘，《演義》），也可用 `"xieji_fei"`（九星飞布八门转，《協紀》） |
| `names` | str | 八神名号，默认 `"default"`（白虎玄武），也可用 `"gouchen"`（勾陈朱雀） |

**返回结构：**
```python
{
    "sizhu":   # 年月日时四柱（日以子初换）
    "ju":      # 定局结果（节气、元、遁、局、符头、正授/超神/接气/置闰）
    "pan":     # 九宫排盘（见 pan.build）
    "geju":    # 成格（见 geju.find）
    "kong":    # 时旬空亡之二支及其所落之宫
    "ma":      # 时支驿马及其宫
    "options": # 其他选项
}
```

---

## 二、辅助方法

### `qimen.ju.ju_of`
单独查询某一时刻的局信息（节气、元、遁、局等）。

| 参数 | 类型 | 说明 |
|------|------|------|
| `dt` | datetime | 起局时刻 |
| `method` | str | 排盘方法，默认 `"zhirun"` |
| `rule` | str | 定局规则，默认 `"qian_yuan_hou_jin"` |

**返回：**
```python
{
    "jieqi":        # 所用节气
    "jieqi_time":   # 该节气交节时刻
    "yuan":         # 上/中/下元
    "dun":          # 阳遁/阴遁
    "ju":           # 局数 1–9
    "futou":        # 本元符头日干支
    "futou_date":   # 符头日期
    "mode":         # 正授/超神/接气/置闰/拆补
    "run":          # 是否闰局
    "shangyuan_date": # （置闰法时返回）本节上元符头之日
}
```

### `qimen.pan.build`
排一个时辰的盘。

| 参数 | 类型 | 说明 |
|------|------|------|
| `yang` | bool | 阳遁为 True，阴遁为 False |
| `ju` | int | 局数 1–9 |
| `hour_gz` | str | 时干支，如 `"丙寅"` |
| `method` | str | 排盘方式，默认 `"zhuan"`（转盘），也可用 `"xieji_fei"`（九星飞布八门转） |
| `names` | str | 八神名号，默认 `"default"`（白虎玄武），也可用 `"gouchen"`（勾陈朱雀） |

### `qimen.pan.dipan`
布地盘：宫 → 干。本局之宫起戊，阳遁按宫数顺布、阴遁逆布。

| 参数 | 类型 | 说明 |
|------|------|------|
| `yang` | bool | 阳遁为 True |
| `ju` | int | 局数 |

### `qimen.pan.xun_of`
查询干支所在之旬：返回 `(旬首如「甲子」, 所隐之仪如「戊」)`。

| 参数 | 类型 | 说明 |
|------|------|------|
| `gz` | str | 干支，如 `"丙寅"` |

### `qimen.qiju.xun_kong`
查询旬空二支：本旬十干用尽所余之二支。

| 参数 | 类型 | 说明 |
|------|------|------|
| `gz` | str | 时干支 |

### `qimen.qiju.ma_xing`
查询驿马星（无详细说明）。

| 参数 | 类型 | 说明 |
|------|------|------|
| `gz` | str | 时干支 |

### `qimen.geju.find`
查询这一盘成哪些格。

| 参数 | 类型 | 说明 |
|------|------|------|
| `pan` | dict | 排好的九宫盘 |
| `day` | str | 日干支（判伏干、飞干） |
| `month` | str | 月干支（判岁月格） |
| `year` | str | 年干支（判岁月格与五不遇时） |

**返回：**
```python
[{
    "name":     # 格名
    "verdict":  # 断语
    "gong":     # 所落宫位（None表示整盘之格，如五不遇时、伏吟）
    "cite":     # 引用出处
    "quote":    # 引用原文
}]
```

---

## 三、使用建议

**推荐流程：**
1. 若只需起局：直接调用 `qimen.qiju.qiju(dt=...)`，一步完成。
2. 若需分步操作：
   - 先用 `qimen.ju.ju_of(dt=...)` 定局（节气、元、遁、局）
   - 再用 `qimen.pan.build(yang, ju, hour_gz, ...)` 排盘
   - 最后用 `qimen.geju.find(pan, day, month, year)` 查成格

**注意：**
- `dt` 参数建议使用北京时间（naive datetime），若需真太阳时，请调用方先换算。
- 定局规则 `"qian_yuan_hou_jin"` 为默认，也可根据流派需求调整。

### 待核对

- 说明目录中实际存在的方法及参数
