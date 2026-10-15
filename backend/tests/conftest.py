import os

# Тесты детерминированные: синтетический каталог и демо-агент, без сети и ключей.
os.environ["UMAY_TESTING"] = "1"
os.environ["UMAY_CATALOG"] = os.environ.get("TEST_CATALOG", "demo")
for k in ("ANTHROPIC_API_KEY", "QWEN_API_KEY", "DASHSCOPE_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(k, None)
