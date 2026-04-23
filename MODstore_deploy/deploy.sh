#!/bin/bash
# MODstore Linux 部署脚本
# 用法: chmod +x deploy.sh && ./deploy.sh

set -e

echo "========================================"
echo "   MODstore Linux 部署"
echo "========================================"
echo ""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为 root
if [ "$EUID" -eq 0 ]; then
   echo -e "${RED}[警告] 不建议使用 root 用户运行${NC}"
   sleep 2
fi

echo "[1/7] 检查 Python 3.11+..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[错误] 未找到 Python3${NC}"
    echo "请先安装 Python 3.11+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}[OK] Python 版本: $PYTHON_VERSION${NC}"

echo ""
echo "[2/7] 检查 .env 配置..."
if [ ! -f ".env" ]; then
    if [ -f ".env.production" ]; then
        cp .env.production .env
        echo -e "${YELLOW}[提示] 已从 .env.production 复制 .env，请编辑修改配置${NC}"
        echo "必须修改: JWT_SECRET, ADMIN_RECHARGE_TOKEN, CORS_ORIGINS, PUBLIC_ORIGIN"
        exit 1
    else
        echo -e "${RED}[错误] 未找到 .env 或 .env.production${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}[OK] .env 存在${NC}"

echo ""
echo "[3/7] 创建虚拟环境..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}[OK] 虚拟环境已创建${NC}"
else
    echo -e "${GREEN}[OK] 虚拟环境已存在${NC}"
fi

# 激活虚拟环境
source .venv/bin/activate

echo ""
echo "[4/7] 安装 Python 依赖..."
pip install -q --upgrade pip
pip install -q fastapi "uvicorn[standard]" python-multipart httpx sqlalchemy PyJWT bcrypt python-dotenv python-alipay-sdk
pip install -q -e .
echo -e "${GREEN}[OK] 依赖安装完成${NC}"

echo ""
echo "[5/7] 构建前端..."
if command -v npm &> /dev/null; then
    cd market
    if [ ! -d "node_modules" ]; then
        echo "[提示] 安装 npm 依赖..."
        npm ci
    fi
    npm run build
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[OK] 前端构建完成${NC}"
    else
        echo -e "${RED}[警告] 前端构建失败${NC}"
    fi
    cd ..
else
    echo -e "${YELLOW}[跳过] 未找到 npm，跳过前端构建${NC}"
fi

echo ""
echo "[6/7] 初始化数据库..."
python3 -c "
from modstore_server.models import init_db
init_db()
print('数据库初始化完成')
"

echo ""
echo "[7/7] 启动服务..."
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "启动命令:"
echo "  source .venv/bin/activate"
echo "  python -m uvicorn modstore_server.app:app --host 0.0.0.0 --port 8765"
echo ""
echo "或使用 systemd 后台运行:"
echo "  sudo systemctl enable --now modstore"
echo ""
echo "访问地址:"
echo "  前端: http://你的服务器IP:8765/market"
echo "  API文档: http://你的服务器IP:8765/docs"
echo ""

# 询问是否立即启动
read -p "是否立即启动服务? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "正在启动..."
    python -m uvicorn modstore_server.app:app --host 0.0.0.0 --port 8765
fi
