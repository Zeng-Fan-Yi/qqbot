FROM python:3.12-slim

WORKDIR /app

# 先装依赖（利用层缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制代码与数据（.env 不入镜像，由 compose 的 env_file / 环境变量提供）
COPY bot.py pyproject.toml ./
COPY src/ ./src/
COPY config/ ./config/
COPY data/ ./data/

CMD ["python", "bot.py"]
