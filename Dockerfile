FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 使用国内Debian镜像源加速
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's/security.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    wget \
    tar \
    && rm -rf /var/lib/apt/lists/*

# 安装TA-Lib C库
RUN wget -q https://mirrors.tuna.tsinghua.edu.cn/ta-lib/ta-lib-0.4.0-src.tar.gz -O ta-lib-0.4.0-src.tar.gz || \
    wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz -O ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz && \
    ldconfig

WORKDIR /app

COPY requirements.txt .

# 使用国内PyPI镜像加速 + PyTorch CPU版
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

COPY . .

# 修复Windows CRLF行尾 + 重命名README.md为readme.md（比赛要求小写） + 创建目录
RUN sed -i 's/\r$//' /app/init.sh /app/train.sh /app/test.sh && \
    chmod +x /app/init.sh /app/train.sh /app/test.sh && \
    (mv README.md readme.md 2>/dev/null || true) && \
    (test -f readme.md || cp README.md readme.md 2>/dev/null || true) && \
    ls -la /app/*.md /app/*.sh 2>/dev/null && \
    mkdir -p /app/output /app/temp

ENV LD_LIBRARY_PATH="/usr/lib:/usr/local/lib"

CMD ["sleep", "infinity"]
