"""Build a Windows x64 portable package from a source allowlist."""
from importlib.metadata import distribution
from pathlib import Path
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build():
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise ValueError('build_on_windows_x64')
    if sys.prefix == sys.base_prefix:
        raise ValueError('build_in_dedicated_virtual_environment')
    version = json.loads((ROOT / 'version.json').read_text(encoding='utf-8'))['version']
    if not all(c.isalnum() or c in '.-' for c in version):
        raise ValueError('invalid_version')
    output = ROOT / 'dist' / ('imagegen-dual-' + version + '-windows-x64')
    stage = output / 'imagegen-dual'
    if output.exists():
        raise ValueError('output_exists_inspect_before_rebuilding')
    stage.mkdir(parents=True)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile',
                    '--name', 'imagegen-dual', '--distpath', str(stage),
                    '--workpath', str(ROOT / 'build/pyinstaller'),
                    '--specpath', str(ROOT / 'build'), str(ROOT / 'scripts/cli.py')], cwd=ROOT, check=True)
    for name in ('SKILL.md', 'README.md', 'version.json', 'release.json', 'capabilities.json', 'requirements.txt'):
        shutil.copy2(ROOT / name, stage / name)
    shutil.copytree(ROOT / 'references', stage / 'references')
    licenses = stage / 'THIRD_PARTY_LICENSES'
    licenses.mkdir()
    for name in ('requests', 'Pillow', 'urllib3', 'certifi', 'charset-normalizer', 'idna', 'pyinstaller'):
        dist = distribution(name)
        target = licenses / name
        target.mkdir()
        (target / 'VERSION.txt').write_text(name + ' ' + dist.version + chr(10), encoding='utf-8')
        found = False
        for entry in dist.files or []:
            if any(x in str(entry).lower() for x in ('license', 'copying', 'notice')):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    destination = target / str(entry).replace('..', '_').replace('\\', '_').replace('/', '_')
                    shutil.copy2(source, destination)
                    found = True
        if not found:
            raise ValueError('missing_third_party_license_' + name)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if not python_license.is_file():
        python_license = Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt'
    if not python_license.is_file():
        raise ValueError('python_license_missing')
    shutil.copy2(python_license, licenses / 'Python-LICENSE.txt')
    env = dict(os.environ, PATH=os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32'))
    env.pop('PYTHONPATH', None)
    subprocess.run([str(stage / 'imagegen-dual.exe'), 'self-test'], cwd=stage, env=env, check=True)
    archive = ROOT / 'dist' / (output.name + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                z.write(path, path.relative_to(output))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT / 'dist/SHA256SUMS.txt').write_text(digest + '  ' + archive.name + chr(10), encoding='utf-8')
    print(json.dumps({'archive': str(archive), 'sha256': digest, 'bytes': archive.stat().st_size}))


if __name__ == '__main__':
    build()

