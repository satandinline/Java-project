#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动安装项目依赖脚本
运行此脚本将自动安装项目运行所需的所有依赖（Python和Node.js）
"""

import os
import sys
import subprocess
import platform
import shutil

def print_step(step_num, message):
    """打印步骤信息"""
    print(f"\n{'='*60}")
    print(f"步骤 {step_num}: {message}")
    print('='*60)

def check_command(command, name):
    """检查命令是否存在"""
    if shutil.which(command):
        return True
    else:
        print(f"❌ 未找到 {name}，请先安装 {name}")
        return False

def run_command(command, description, check=True):
    """运行命令并处理错误"""
    print(f"\n正在执行: {description}")
    print(f"命令: {command}")
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=check,
            capture_output=True,
            text=True,
            encoding='utf-8' if platform.system() != 'Windows' else 'gbk'
        )
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 执行失败: {e}")
        if e.stdout:
            print(f"输出: {e.stdout}")
        if e.stderr:
            print(f"错误: {e.stderr}")
        return False

def install_python_dependencies():
    """安装Python依赖"""
    print_step(1, "检查Python环境")
    
    # 检查Python版本
    python_version = sys.version_info
    print(f"Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 7):
        print("❌ 需要Python 3.7或更高版本")
        return False
    
    print("✅ Python版本符合要求")
    
    # 检查pip
    print_step(2, "检查pip")
    if not check_command("pip", "pip"):
        print("尝试使用 pip3...")
        if not check_command("pip3", "pip3"):
            return False
    
    pip_cmd = "pip3" if shutil.which("pip3") else "pip"
    print(f"✅ 使用 {pip_cmd} 安装依赖")
    
    # 升级pip
    print_step(3, "升级pip到最新版本")
    run_command(f"{pip_cmd} install --upgrade pip", "升级pip", check=False)
    
    # 安装依赖
    print_step(4, "安装Python依赖包")
    requirements_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
    
    if not os.path.exists(requirements_file):
        print(f"❌ 未找到 requirements.txt 文件: {requirements_file}")
        return False
    
    if not run_command(f"{pip_cmd} install -r {requirements_file}", "安装Python依赖"):
        return False
    
    print("✅ Python依赖安装完成")
    return True

def install_node_dependencies():
    """安装Node.js依赖"""
    print_step(5, "检查Node.js环境")
    
    # 检查Node.js
    if not check_command("node", "Node.js"):
        print("⚠️  未安装Node.js，跳过前端依赖安装")
        print("   如需安装前端依赖，请先安装Node.js: https://nodejs.org/")
        return False
    
    # 检查npm
    if not check_command("npm", "npm"):
        print("❌ 未找到npm，请确保Node.js正确安装")
        return False
    
    # 获取Node.js版本
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        node_version = result.stdout.strip()
        print(f"✅ Node.js版本: {node_version}")
    except:
        print("⚠️  无法获取Node.js版本")
    
    # 检查前端目录
    frontend_dir = os.path.join(os.path.dirname(__file__), "FrontEnd")
    if not os.path.exists(frontend_dir):
        print(f"⚠️  未找到FrontEnd目录: {frontend_dir}")
        return False
    
    package_json = os.path.join(frontend_dir, "package.json")
    if not os.path.exists(package_json):
        print(f"⚠️  未找到package.json: {package_json}")
        return False
    
    # 安装前端依赖
    print_step(6, "安装前端依赖（Node.js）")
    original_dir = os.getcwd()
    try:
        os.chdir(frontend_dir)
        if not run_command("npm install", "安装前端依赖"):
            return False
        print("✅ 前端依赖安装完成")
        return True
    finally:
        os.chdir(original_dir)

def main():
    """主函数"""
    print("\n" + "="*60)
    print("公共文化资源管理系统 - 依赖安装脚本")
    print("="*60)
    print("\n此脚本将自动安装项目运行所需的所有依赖")
    print("包括：")
    print("  1. Python依赖包（后端）")
    print("  2. Node.js依赖包（前端）")
    print("\n开始安装...")
    
    # 安装Python依赖
    python_success = install_python_dependencies()
    
    # 安装Node.js依赖
    node_success = install_node_dependencies()
    
    # 总结
    print("\n" + "="*60)
    print("安装总结")
    print("="*60)
    
    if python_success:
        print("✅ Python依赖: 安装成功")
    else:
        print("❌ Python依赖: 安装失败")
    
    if node_success:
        print("✅ Node.js依赖: 安装成功")
    else:
        print("⚠️  Node.js依赖: 跳过或失败（如果不需要前端功能可忽略）")
    
    print("\n" + "="*60)
    print("后续步骤")
    print("="*60)
    print("1. 配置环境变量：创建 .env 文件并设置数据库和API密钥")
    print("2. 初始化数据库：运行 database_files/run_init_schema.py")
    print("3. 启动项目：")
    print("   - Windows: start_dev.bat")
    print("   - Linux/Mac: ./start_dev.sh")
    print("   - 或使用: cd FrontEnd && npm run dev:full")
    print("="*60)
    
    if python_success:
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())

