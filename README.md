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

## 当前限制

- API 回答仍需通过 11 段格式校验，不合格时禁止保存。
- 题目可以留空；只有无法从代码、报错或运行现象判断是否符合题意时，才会返回“需题目”。
- Streamlit Community Cloud 的本地文件不能作为长期数据库。
- 新记录和“已重做”状态在云端重启后可能丢失。

## 下一步

1. 接入持久化存储。
2. 完成第一位真实用户测试。
3. 开展有记忆与无记忆的 A/B 对照实验。
