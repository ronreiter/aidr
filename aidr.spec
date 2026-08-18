# PyInstaller spec for ai;dr — self-contained macOS menu-bar app.
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [('models/Qwen3-0.6B-Q8_0.gguf', 'models')]
binaries = []
hiddenimports = ['objc', 'Foundation', 'AppKit', 'CoreFoundation']
hiddenimports += collect_submodules('rumps')

for pkg in ('llama_cpp', 'huggingface_hub'):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ['aidr.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='aidr', console=False, argv_emulation=False, target_arch=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name='aidr')
app = BUNDLE(
    coll,
    name='aidr.app',
    icon='aidr.icns',
    bundle_identifier='io.aidr.app',
    info_plist={
        'LSUIElement': True,               # menu-bar only, no dock icon
        'CFBundleName': 'ai;dr',
        'CFBundleDisplayName': 'ai;dr',
        'CFBundleShortVersionString': '0.1.3',
        'NSHighResolutionCapable': True,
    },
)
