import json
import re
import os
import difflib
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

def extract_patches_from_text(text: str):
    """Sử dụng lại Regex của Node 1 để bóc tách khối SEARCH/REPLACE"""
    pattern = re.compile(
        r"<<<< SEARCH\s*\n(.*?)\n\s*(?:====+|REPLACE)\s*\n(.*?)(?:\n\s*>>>> REPLACE|\n\s*```|\Z)", 
        re.DOTALL
    )
    return pattern.findall(text)

def view_latest_patch(json_path="debug_last_run.json"):
    """Đọc file log và render giao diện Git Diff"""
    if not os.path.exists(json_path):
        console.print(f"[bold red]❌ Không tìm thấy file {json_path}[/bold red]")
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        history = data.get("state", {}).get("history", [])
        if not history:
            console.print("[yellow]⚠️ Không có lịch sử chạy nào trong file log.[/yellow]")
            return

        patch_found = False

        # Duyệt ngược từ cuối lên để tìm bản vá gần nhất
        for entry in reversed(history):
            if entry.get("node") == "code_generator":
                messages = entry.get("output", {}).get("messages", [])
                if not messages:
                    continue
                    
                try:
                    content = messages[0]["kwargs"]["content"]
                    text = content[0]["text"] if isinstance(content, list) else str(content)
                except KeyError:
                    continue
                
                patches = extract_patches_from_text(text)
                if patches:
                    patch_found = True
                    console.print("\n[bold cyan]🔍 CHI TIẾT BẢN VÁ (GIT DIFF PREVIEW)[/bold cyan]")
                    
                    for idx, (search_block, replace_block) in enumerate(patches, 1):
                        search_block = search_block.strip()
                        replace_block = replace_block.replace("```", "").strip()

                        # 1. Tạo thuật toán so sánh Diff
                        diff = difflib.unified_diff(
                            search_block.splitlines(keepends=True),
                            replace_block.splitlines(keepends=True),
                            fromfile='Mã nguồn hiện tại (Trên RAM)',
                            tofile='Bản vá từ AI Agent',
                            lineterm=''
                        )

                        # 2. Render màu sắc chuẩn Git (Xanh/Đỏ)
                        diff_text = Text()
                        for line in diff:
                            if line.startswith('+') and not line.startswith('+++'):
                                diff_text.append(line + "\n", style="bold green")
                            elif line.startswith('-') and not line.startswith('---'):
                                diff_text.append(line + "\n", style="bold red")
                            elif line.startswith('@@'):
                                diff_text.append(line + "\n", style="cyan")
                            elif line.startswith('---') or line.startswith('+++'):
                                diff_text.append(line + "\n", style="bold white")
                            else:
                                diff_text.append(line + "\n", style="dim white")

                        # 3. Đóng khung Panel hiển thị
                        console.print(Panel(
                            diff_text, 
                            title=f"Patch #{idx} - Phẫu thuật cục bộ", 
                            border_style="blue",
                            expand=False
                        ))
                    
                    break
                    
        if not patch_found:
            console.print("[yellow]⚠️ LLM chưa tạo ra khối SEARCH/REPLACE nào trong chu kỳ chạy này.[/yellow]")
            
    except Exception as e:
        console.print(f"[bold red]❌ Lỗi khi đọc file log: {e}[/bold red]")

if __name__ == "__main__":
    view_latest_patch()