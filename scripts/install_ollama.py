"""Install the official portable Windows CPU/Vulkan runtime inside this project.

The pinned release includes large optional CUDA runtimes. HTTP range retrieval
downloads its final 61 MB containing the complete CPU/Vulkan runtime instead.
ZIP CRC checks are performed for every extracted file. No system settings change.
"""
import io
import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://github.com/ollama/ollama/releases/download/v0.34.2/ollama-windows-amd64.zip'
START = 1400000000
SIZE = 1460928014


class ArchiveTail(io.BytesIO):
    def seek(self, offset, whence=0):
        return super().seek(offset - START if whence == 0 else offset, whence) + START

    def tell(self):
        return super().tell() + START


def main():
    local = ROOT / '.local'
    local.mkdir(exist_ok=True)
    archive = local / 'ollama-tail.zip'
    if not archive.exists() or archive.stat().st_size != SIZE - START:
        print('Downloading official Ollama 0.34.2 CPU/Vulkan runtime (61 MB)...', flush=True)
        request = urllib.request.Request(URL, headers={'Range': f'bytes={START}-{SIZE-1}'})
        with urllib.request.urlopen(request, timeout=180) as response:
            if response.status != 206:
                raise RuntimeError('The release server did not honor the requested byte range')
            with archive.open('wb') as output:
                shutil.copyfileobj(response, output)
    if archive.stat().st_size != SIZE - START:
        raise RuntimeError('Incomplete download; rerun setup')
    destination = (local / 'ollama').resolve()
    with zipfile.ZipFile(ArchiveTail(archive.read_bytes())) as source:
        cutoff = source.getinfo('lib/ollama/ggml-base.dll').header_offset
        for item in source.infolist():
            if item.header_offset < cutoff or item.is_dir():
                continue
            target = (destination / item.filename).resolve()
            if not target.is_relative_to(destination):
                raise RuntimeError('Unsafe archive member')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read(item))
    print('Installed:', destination / 'ollama.exe')


if __name__ == '__main__':
    main()
