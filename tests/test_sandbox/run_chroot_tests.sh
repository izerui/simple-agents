#!/bin/bash
# 测试 chroot 沙箱
# 使用方法: sudo bash tests/test_sandbox/run_chroot_tests.sh

echo "========================================"
echo "chroot 沙箱测试"
echo "========================================"
echo "当前用户: $(whoami)"
echo "UID: $(id -u)"
echo "是否有 root 权限: $([ $(id -u) -eq 0 ] && echo '是' || echo '否')"
echo ""

if [ $(id -u) -ne 0 ]; then
    echo "❌ 需要 root 权限运行"
    echo "请使用: sudo bash tests/test_sandbox/run_chroot_tests.sh"
    exit 1
fi

echo "✅ 有 root 权限，开始测试..."
echo ""

# 激活虚拟环境并运行测试
source .venv/bin/activate
python tests/test_sandbox/test_chroot_only.py
