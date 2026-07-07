import json
import os
from rich.console import Console
from rich.tree import Tree
from rich.panel import Panel

console = Console()

def view_execution_flow(json_path="debug_last_run.json"):
    """Đọc file log và vẽ sơ đồ luồng chạy của LangGraph"""
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

        console.print("\n[bold magenta]🔄 TRUY VẾT LUỒNG HOẠT ĐỘNG (AGENT EXECUTION FLOW)[/bold magenta]")
        
        # Tạo cấu trúc Tree của thư viện Rich
        flow_tree = Tree("[bold white]Bắt đầu quy trình xử lý...[/bold white]")

        for step, entry in enumerate(history, 1):
            node_name = entry.get("node", "Unknown Node")
            attempt = entry.get("attempt", 0)
            duration = entry.get("duration_ms", 0) / 1000  # Đổi ra giây
            
            # 1. Phân tích Node 1: Generator
            if node_name == "code_generator":
                node_label = f"[bold cyan]🤖 Node 1 (Generator)[/bold cyan] - Lần thử {attempt} | ⏱️ {duration}s"
                step_tree = flow_tree.add(node_label)
                
                output_msgs = entry.get("output", {}).get("messages", [])
                if output_msgs:
                    # Kiểm tra xem có gọi tool không
                    for msg in output_msgs:
                        # Đọc từ input thay vì output để lấy lịch sử gọi tool
                        pass
                
                # Để lấy tool calls, ta phải quét lại lịch sử trong chu kỳ này
                # Giả lập hiển thị dựa trên những gì ta phân tích được từ text
                try:
                    content = output_msgs[0]["kwargs"]["content"]
                    text = content[0]["text"] if isinstance(content, list) else str(content)
                    if "<<<< SEARCH" in text:
                        step_tree.add("[green]└─ Hành động: Xuất bản vá (Patch Replace)[/green]")
                    else:
                        step_tree.add("[white]└─ Hành động: Sinh mã nguồn gốc (Initial Code)[/white]")
                except:
                    pass

            # 2. Phân tích Node 2: Executor
            elif node_name == "code_executor":
                node_label = f"[bold yellow]⚙️ Node 2 (Executor)[/bold yellow] - Lần thử {attempt} | ⏱️ {duration}s"
                step_tree = flow_tree.add(node_label)
                
                is_success = entry.get("output", {}).get("is_success", False)
                if is_success:
                    step_tree.add("[bold green]└─ Kết quả: ✅ PASS toàn bộ Test Case[/bold green]")
                else:
                    step_tree.add("[bold red]└─ Kết quả: ❌ FAIL (Lỗi logic hoặc Cú pháp)[/bold red]")

            # 3. Phân tích Node 3: Router
            elif node_name == "critic_router":
                node_label = f"[bold magenta]🔀 Node 3 (Router)[/bold magenta] - Lần thử {attempt}"
                step_tree = flow_tree.add(node_label)
                
                action = entry.get("output", {}).get("action", {})
                next_node = action.get("next_node", "")
                reasoning = action.get("reasoning", "")
                
                if next_node == "code_generator":
                    step_tree.add(f"[bold yellow]├─ Quyết định: ↩️ Quay lại Node 1 (Retry)[/bold yellow]")
                    step_tree.add(f"[dim]└─ Lý do: {reasoning}[/dim]")
                elif next_node == "END_SUCCESS":
                    step_tree.add(f"[bold green]├─ Quyết định: 🏁 Kết thúc (Thành công)[/bold green]")
                    step_tree.add(f"[dim]└─ Lý do: {reasoning}[/dim]")

        # In cây thư mục ra terminal
        console.print(Panel(flow_tree, border_style="cyan"))
            
    except Exception as e:
        console.print(f"[bold red]❌ Lỗi khi đọc file log: {e}[/bold red]")

if __name__ == "__main__":
    view_execution_flow()