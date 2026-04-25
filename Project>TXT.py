import os
from pathlib import Path

def is_text_file(file_path):
    """Check if file is likely a text file by extension or name."""
    text_extensions = {
        '.py', '.js', '.html', '.css', '.md', '.txt', '.yml', '.yaml', 
        '.json', '.xml', '.csv', '.sql', '.sh', '.bash', '.zsh',
        '.cfg', '.conf', '.ini', '.env', '.log', '.rst', '.toml'
    }
    basename_matches = {
        'Makefile', 'Dockerfile', 'Procfile', 'requirements.txt', 'README'
    }
    if file_path.suffix.lower() in text_extensions:
        return True
    if not file_path.suffix and file_path.name in basename_matches:
        return True
    return False

def should_skip_directory(dir_name):
    """
    Skip directory if:
    1. It matches known skip_dirs.
    2. It contains 'data' (case-insensitive), unless exactly 'data'.
    """
    skip_dirs = {
        'scrape_env', '.venv', '__pycache__', '.git', '.mypy_cache',
        '.pytest_cache', '.tox', '.idea', '.vscode', '.DS_Store'
    }
    lname = dir_name.lower()
    if dir_name in skip_dirs:
        return True
    if "data" in lname and lname != "data":
        return True
    return False

def extract_all_text(output_file='Project_Files.txt'):
    """Extract text from all project files, skipping unwanted dirs."""
    current_dir = Path('.')
    files_processed = 0
    total_chars = 0

    print(f"📁 Scanning directory: {current_dir.absolute()}")

    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(f"# All Project Files Extract\n")
        out.write(f"# Generated on: {Path.cwd()}\n") 
        out.write(f"# Excludes: .venv, build/cache, and 'data*' dirs (except 'data')\n\n")
        
        for root, dirs, files in os.walk(current_dir, topdown=True):
            dirs[:] = [d for d in dirs if not should_skip_directory(d)]
            root_path = Path(root)
            for file_name in sorted(files):
                file_path = root_path / file_name
                if not is_text_file(file_path) or file_name == output_file:
                    continue
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    if not content.strip():
                        continue
                    relative_path = file_path.relative_to(current_dir)
                    out.write('=' * 80 + '\n')
                    out.write(f'File: {relative_path}\n')
                    out.write('=' * 80 + '\n')
                    out.write(content)
                    out.write('\n\n')
                    files_processed += 1
                    total_chars += len(content)
                    print(f"✅ {relative_path} ({len(content):,} chars)")
                except Exception as e:
                    print(f"⚠️  Skipping {file_path}: {e}")

    print(f"\n🎉 Your files have been summarise!! 🙏🙏🙏")
    print(f"   📁 Files processed: {files_processed}")
    print(f"   📝 Total characters: {total_chars:,}")
    print(f"   💾 Output file: {output_file}")
    output_size = Path(output_file).stat().st_size
    print(f"   📏 Output size: {output_size:,} bytes ({output_size/1024/1024:.1f} MB)")

if __name__ == "__main__":
    extract_all_text()
