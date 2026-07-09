# AI Email Assistant - Tools Summary

Danh sách dưới đây tổng hợp tất cả các file trong thư mục `src/tools/` của hệ thống **AI Email Assistant Harness**, mô tả các class (công cụ) được định nghĩa và chức năng của chúng.

> [!NOTE]
> Hệ thống áp dụng triệt để nguyên lý **Tool Layer Encapsulation**. Agent (LLM) không gọi trực tiếp các API bên ngoài mà phải thông qua các Tool này. Điều này giúp hệ thống dễ dàng kiểm soát, giới hạn quyền và ghi log (audit log).

---

## 1. Core Framework (Hệ thống cốt lõi)

### [base_tool.py](file:///E:/FPT/ai-email-assistant-harness/src/tools/base_tool.py)
* **Class chính:** `BaseTool`
* **Chức năng:** Là abstract base class (lớp cơ sở trừu tượng) cho mọi Tool. 
* **Đặc điểm nổi bật:**
  - Bắt buộc các subclass (lớp con) phải có `name`, `description`, và `args_schema` (Pydantic schema).
  - Tự động validate dữ liệu đầu vào (prevent hallucination).
  - Cung cấp hàm `to_llm_dict()` để chuyển đổi Tool thành format Function-Calling tương thích với OpenAI.
  - Hỗ trợ cờ bảo mật `requires_approval = False` (mặc định) để giới hạn phân quyền.

### [registry.py](file:///E:/FPT/ai-email-assistant-harness/src/tools/registry.py)
* **Class chính:** `ToolRegistry`
* **Chức năng:** Sổ đăng ký trung tâm quản lý tất cả các tools trong hệ thống (Pattern: Tool Catalog).
* **Đặc điểm nổi bật:**
  - Cung cấp các hàm như `register()`, `get()`, `call()`.
  - **Harness Engineering:** Hàm `get_agent_tools()` có tính năng tự động lọc ra các tool có cờ `requires_approval = True`. Nhờ đó LLM Agent sẽ không bao giờ nhìn thấy hoặc gọi được các tool nguy hiểm (ví dụ tool gửi mail).

---

## 2. Agent Tools (Công cụ cho LLM Agent)

Các tool này đều an toàn và được Agent tự do gọi trong quá trình suy nghĩ (`DraftStep`).

### [gmail_reader_tool.py](file:///E:/FPT/ai-email-assistant-harness/src/tools/gmail_reader_tool.py)
* **Class chính:** `GmailReaderTool`
* **Chức năng:** Cho phép Agent đọc toàn bộ nội dung của một chuỗi email (thread) thông qua Gmail API dựa trên `thread_id`.
* **Output:** Trả về một mảng các tin nhắn gồm sender, date, subject, body để Agent nắm bắt context cuộc hội thoại trước khi viết thư phản hồi.

### [thread_summarizer_tool.py](file:///E:/FPT/ai-email-assistant-harness/src/tools/thread_summarizer_tool.py)
* **Class chính:** `ThreadSummarizerTool`
* **Chức năng:** Rút gọn và tóm tắt một thread email quá dài bằng cách sử dụng một Model LLM phụ (tiết kiệm chi phí và tăng tốc độ).
* **Quy trình:** Khi Agent nhận thấy text quá 2000 ký tự, nó gọi tool này. Tool gửi request đến router LLM (`llm_router`) để trích xuất Key points, Questions, Action items.

### [contact_lookup_tool.py](file:///E:/FPT/ai-email-assistant-harness/src/tools/contact_lookup_tool.py)
* **Class chính:** `ContactLookupTool`
* **Chức năng:** Tra cứu thông tin người gửi từ hệ thống CRM hoặc Directory.
* **Output:** Trả về Tên, Công ty, Mối quan hệ, và Sở thích giao tiếp (communication preferences) giúp Agent điều chỉnh Tone giọng (formal/informal) sao cho cá nhân hóa nhất. *(Hiện tại sử dụng Mock data để làm ví dụ).*

### [gmail_draft_tool.py](file:///E:/FPT/ai-email-assistant-harness/src/tools/gmail_draft_tool.py)
* **Class chính:** `GmailDraftTool`
* **Chức năng:** Tạo mới hoặc cập nhật một bản nháp (Draft) trực tiếp trên Gmail.
* **Quy trình:** Sau khi Agent suy nghĩ và soạn xong nội dung, nó gọi tool này để đẩy thành Draft. **Draft sẽ KHÔNG được gửi đi**, nó chỉ nằm trong hòm thư nháp chờ duyệt.

---

## 3. Restricted Tools (Công cụ bị giới hạn quyền)

Các tool này **KHÔNG** được cung cấp cho Agent, chỉ có Hệ thống (Orchestrator) mới được phép gọi.

### [gmail_send_tool.py](file:///E:/FPT/ai-email-assistant-harness/src/tools/gmail_send_tool.py)
* **Class chính:** `GmailSendTool`
* **Đặc tính an toàn:** `requires_approval = True`
* **Chức năng:** Chịu trách nhiệm gửi một bản draft đã có sẵn trên Gmail API thành email thực sự gửi đi.
* **Quy trình:** Orchestrator (bộ điều phối) chỉ gọi tool này ở bước `SendStep` sau khi vượt qua `ApprovalGate` - tức là đã có con người (Human-in-the-loop) bấm nút `approve` qua màn hình CLI và cung cấp `approval_id` hợp lệ. Lệnh gửi mail độc lập hoàn toàn với Agent.
