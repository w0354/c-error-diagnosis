# 项目记忆

## 当前状态

- 项目：面向 C 语言初学者的错因诊断助手。
- 本地原项目：`D:\python-learn\app`
- 部署副本：`D:\python-learn\diagnosis_app`
- GitHub：https://github.com/w0354/c-error-diagnosis
- 公开演示：https://c-error-diagnosis-i7guwfzpdoqxbpmput6ngu.streamlit.app/

## 已完成的稳定能力

- 固定 11 段诊断格式，规则保存在 `prompt_v6.txt`。
- 15 类错因和 K01–K15 知识点体系，权威表保存在 `knowledge_map.md`。
- Streamlit 解析、校验、代码归档、复习列表和质量看板。
- GitHub 和 Streamlit Community Cloud 发布链路。
- 已恢复 36 条记录及其代码关联。
- UI V2 使用 `app_v2.py` 预览，稳定入口仍为 `app.py`。
- 改版前备份：`D:\python-learn\diagnosis_app_backups`
- Git 回退标签：`working-diagnosis-before-ui-20261126`

## 当前阶段目标

使用 DeepSeek `deepseek-chat` 接入一键诊断：

```text
输入代码、报错和可选题目要求 -> DeepSeek API -> 11 段回答
-> 解析 -> 校验 -> 页面展示 -> 合格后保存
```

- 代码能编译但没有题目、样例或预期结果时，不能直接判“无错误”；应返回“需题目”。
- 代码能编译但不符合题意时，应结合题目要求判断逻辑、边界、输入输出或类型错误。

## 数据安全

- 原始数据恢复包：`D:\python-learn\diagnosis_data_recovery_20261125`
- DeepSeek Key 只保存在 `.streamlit/secrets.toml`，不得提交。
- Streamlit Community Cloud 本地文件不能作为长期数据库。

## 尚未完成

- 云端配置 DeepSeek Secret。
- 接入持久化数据库。
- 第一位真实用户测试。
- 记忆注入 A/B 对照实验。
