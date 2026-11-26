# C 语言错因诊断工作台

这是一个面向 C 语言初学者的错因诊断与复习辅助项目。当前公开版本负责：

- 输入出错代码和编译器报错，调用 DeepSeek 完成诊断；
- 代码能编译但不符合题意时，可补充题目、样例和实际输出；
- 解析固定格式的 11 段诊断回答；
- 校验错因类别、知识点和必要字段；
- 展示原题、同类题、正确代码和逐行说明；
- 查看错题记录、待重做题目和错因分布；
- 展示编译检查与运行检查结果。

## 本地运行

```powershell
python -m pip install -r requirements.txt
Copy-Item .streamlit/secrets.example.toml .streamlit/secrets.toml
streamlit run app.py
```

然后将 `.streamlit/secrets.toml` 中的 `DEEPSEEK_API_KEY` 替换为自己的
DeepSeek API Key。该文件已加入 `.gitignore`，不得提交。

## API 配置

默认使用：

- 模型：`deepseek-chat`
- 接口地址：`https://api.deepseek.com`
- 系统提示词：`prompt_v6.txt`

## 数据存储

错题主数据保存在 Supabase 的 `records` 表中。首次建库使用
`supabase_schema.sql`，现有 CSV 数据通过以下命令迁移：

```powershell
python migrate_to_supabase.py
```

本地 `records_v3.csv` 与 `codes` 目录保留为迁移前备份，不再作为网页的
正式数据源。

需要在 `.streamlit/secrets.toml` 中配置：

```toml
SUPABASE_URL = "你的 Supabase Project URL"
SUPABASE_SERVICE_ROLE_KEY = "你的 Secret key"
```

## 质量审计

本地编译审计会读取 Supabase 中的 R004–R010，分别检查原题正确代码、
同类题代码和同类题正确代码，并生成 `quality_audit.csv`：

```powershell
python quality_audit.py
```

脚本优先使用环境变量 `C_COMPILER`，否则尝试系统 `gcc`，再回退到
Dev-C++ 的 MinGW 编译器。逻辑类错误的同类题应能编译但运行结果错误；
若同类题产生额外编译错误，会被标记为不合格。

## V2 界面预览

公开入口暂时仍是 `app.py`。新版界面在完成验收前通过以下命令本地预览：

```powershell
streamlit run app_v2.py
```

V2 将页面拆分为“一键诊断”“错题库与复习”“项目质量”三个标签页，
诊断、知识分类和保存逻辑继续复用原有模块。

## 当前限制

- API 回答仍需通过 11 段格式校验，不合格时禁止保存。
- 题目可以留空；只有无法从代码、报错或运行现象判断是否符合题意时，才会返回“需题目”。
- V2 已使用 Supabase 持久化，公开入口切换前仍应通过 V2 预览版验收。
- 多用户数据隔离和账号权限尚未实现。

## 下一步

1. 完成 V2 公开入口切换。
2. 完成第一位真实用户测试。
3. 开展有记忆与无记忆的 A/B 对照实验。
