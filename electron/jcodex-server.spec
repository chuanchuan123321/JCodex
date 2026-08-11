# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules
import os

# 无窗口模式：Windows 打包时通过 JCODEX_WINDOWED=true 关闭控制台窗口；
# macOS 模板打包保持 console=True 不变。
console = os.environ.get("JCODEX_WINDOWED", "") != "true"

hiddenimports = []
hiddenimports += collect_submodules('agent')


a = Analysis(
    ['backend_entry.py'],
    pathex=['..'],
    binaries=[],
    datas=[('../agent/ui/desktop', 'agent/ui/desktop'), ('../Agent.md', '.'), ('../workspace/skills', 'workspace/skills'), ('../workspace/skill-store', 'workspace/skill-store'), ('../agent/skills', 'agent/skills'), ('../.env', '.')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pyarrow', 'playwright', 'googleapiclient', 'scipy', 'matplotlib',
              'streamlit', 'gradio', 'nicegui', 'yfinance', 'dashscope',
              'google.genai', 'litellm', 'huggingface_hub', 'fontTools', 'altair',
              'tokenizers', 'hf_xet', 'curl_cffi', 'Cython', 'Crypto', 'pandas'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='jcodex-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='jcodex-server',
)
