
import streamlit as st
import random
import re
from io import BytesIO
from typing import List, Dict, Any
from docx import Document

st.set_page_config(page_title="Quiz AI & Chuyển đổi số", page_icon="🧠")

st.title("🧠 Quiz Ôn luyện: AI & Chuyển đổi số")
st.write("Tải file **.docx** chứa ngân hàng câu hỏi (định dạng linh hoạt: đoạn văn hoặc bảng). App sẽ tự phân tích và tạo quiz.")

# ---------------------- Parsers ----------------------
OPTION_PATTERN = re.compile(r"^[A-D]\.\s*(.*)")
ANSWER_LINE_PATTERN = re.compile(r"đáp\s*án\s*[:\-]?\s*([A-D])", re.IGNORECASE)

def _is_question_line(text: str) -> bool:
    text = text.strip()
    if re.match(r"^\d+\.\s+", text):
        return True
    return (not re.match(r"^[A-D]\.", text)) and ("?" in text and len(text) > 5)

def _gather_paragraph_blocks(doc: Document):
    items = []
    paras = [p for p in doc.paragraphs if p.text.strip()]
    i = 0
    while i < len(paras):
        t = paras[i].text.strip()
        if _is_question_line(t):
            q = t
            i += 1
            options = []
            correct_idx = None
            while i < len(paras) and (OPTION_PATTERN.match(paras[i].text.strip())):
                line = paras[i].text.strip()
                m = OPTION_PATTERN.match(line)
                if m:
                    options.append(m.group(1).strip())
                i += 1
                if len(options) >= 4:
                    break
            j = i
            answer_found = False
            for k in range(j, min(j+3, len(paras))):
                m2 = ANSWER_LINE_PATTERN.search(paras[k].text.strip())
                if m2:
                    letter = m2.group(1).upper()
                    correct_idx = ord(letter) - ord('A')
                    i = k + 1
                    answer_found = True
                    break
            if not answer_found and len(options)==4:
                back_scan = paras[i-len(options):i]
                bold_idx = None
                for idx, p in enumerate(back_scan):
                    for run in p.runs:
                        if run.bold:
                            bold_idx = idx
                            break
                    if bold_idx is not None:
                        break
                if bold_idx is not None:
                    correct_idx = bold_idx
            if len(options)==4 and correct_idx is not None and 0 <= correct_idx < 4:
                items.append({"question": q, "options": options, "answer_idx": correct_idx})
        else:
            i += 1
    return items

def _parse_tables(doc: Document):
    results = []
    for table in doc.tables:
        headers = [cell.text.strip().lower() for cell in table.rows[0].cells]
        def find_idx(name_options):
            for n in name_options:
                if n in headers:
                    return headers.index(n)
            return None
        q_idx = find_idx(["câu hỏi", "cau hoi", "question", "câu hỏi/ câu phát biểu"])
        a_idx = find_idx(["a", "phương án a", "đáp án a"])
        b_idx = find_idx(["b", "phương án b", "đáp án b"])
        c_idx = find_idx(["c", "phương án c", "đáp án c"])
        d_idx = find_idx(["d", "phương án d", "đáp án d"])
        ans_idx = find_idx(["đáp án", "dap an", "answer", "key"])
        if None in [q_idx, a_idx, b_idx, c_idx, d_idx, ans_idx]:
            if len(headers) >= 6:
                q_idx, a_idx, b_idx, c_idx, d_idx, ans_idx = 0,1,2,3,4,5
            else:
                continue
        for r in table.rows[1:]:
            cells = [c.text.strip() for c in r.cells]
            try:
                q = cells[q_idx]
                opts = [cells[a_idx], cells[b_idx], cells[c_idx], cells[d_idx]]
                ans_letter = cells[ans_idx].strip().upper()[:1]
                if ans_letter in ["A","B","C","D"]:
                    answer_idx = ord(ans_letter) - ord('A')
                    if q and all(opts):
                        results.append({"question": q, "options": opts, "answer_idx": answer_idx})
            except Exception:
                continue
    return results

def parse_docx_questions(file_bytes: bytes):
    doc = Document(BytesIO(file_bytes))
    questions = []
    questions.extend(_parse_tables(doc))
    questions.extend(_gather_paragraph_blocks(doc))
    seen = set()
    deduped = []
    for q in questions:
        key = q["question"].strip()
        if key not in seen:
            seen.add(key)
            deduped.append(q)
    return deduped

uploaded = st.file_uploader("📄 Kéo thả file .docx", type=["docx"])

if uploaded is not None:
    try:
        data = uploaded.read()
        all_questions = parse_docx_questions(data)
        total = len(all_questions)
        if total == 0:
            st.error("Không tìm thấy câu hỏi nào trong file. Kiểm tra định dạng (A./B./C./D. và/hoặc bảng có cột 'Đáp án').")
            st.stop()

        st.success(f"Đã nạp **{total}** câu hỏi từ file.")

        with st.sidebar:
            st.header("⚙️ Cấu hình Quiz")
            num_q = st.slider("Số câu trong đề", min_value=5, max_value=min(50, total), value=min(20, total), step=1)
            shuffle_questions = st.checkbox("Xáo trộn thứ tự câu", value=True)
            shuffle_options = st.checkbox("Xáo trộn đáp án trong từng câu", value=False)
            show_explanations = st.checkbox("Hiển thị đáp án đúng sau khi nộp", value=True)
            seed = st.number_input("Seed ngẫu nhiên", value=42, step=1)

        rng = random.Random(seed)
        pool = list(all_questions)
        if shuffle_questions:
            rng.shuffle(pool)
        quiz = pool[:num_q]

        rendered = []
        for item in quiz:
            opts = list(enumerate(item["options"]))
            if shuffle_options:
                rng.shuffle(opts)
            new_correct = None
            for new_i, (orig_i, text) in enumerate(opts):
                if orig_i == item["answer_idx"]:
                    new_correct = new_i
                    break
            rendered.append({
                "question": item["question"],
                "options": [t for _, t in opts],
                "answer_idx": new_correct
            })

        st.write("---")
        st.subheader("📝 Làm bài")
        answers = []
        for idx, q in enumerate(rendered, start=1):
            st.markdown(f"**{idx}. {q['question']}**")
            choice = st.radio(
                label=f"Chọn đáp án cho câu {idx}",
                options=[f\"{chr(65+i)}. {opt}\" for i, opt in enumerate(q[\"options\"])],
                index=None,
                key=f\"q_{idx}\",
            )
            answers.append(choice)

        if st.button("✅ Nộp bài chấm điểm"):
            total_correct = 0
            details = []
            for i, (q, choice) in enumerate(zip(rendered, answers), start=1):
                if choice is None:
                    is_correct = False
                    chosen_idx = None
                else:
                    chosen_idx = ord(choice[0]) - ord('A')
                    is_correct = (chosen_idx == q["answer_idx"])
                if is_correct:
                    total_correct += 1
                details.append((i, q, chosen_idx, is_correct))

            st.success(f"🎯 Kết quả: {total_correct} / {len(rendered)} đúng ({total_correct/len(rendered)*100:.1f}%)")

            if show_explanations:
                st.write("---")
                st.subheader("🔍 Xem lại đáp án")
                for i, q, chosen_idx, is_correct in details:
                    label = "✅ Đúng" if is_correct else "❌ Sai"
                    st.markdown(f"**Câu {i}: {label}**")
                    for j, opt in enumerate(q["options"]):
                        prefix = f"{chr(65+j)}. {opt}"
                        if j == q["answer_idx"]:
                            st.markdown(f"- **{prefix}** ← *Đáp án đúng*")
                        elif chosen_idx is not None and j == chosen_idx:
                            st.markdown(f"- {prefix} *(Bạn chọn)*")
                        else:
                            st.markdown(f"- {prefix}")

        if rendered:
            data_bytes = str(rendered).encode('utf-8')
            st.download_button(
                label="💾 Tải bộ đề đang hiển thị (JSON)",
                data=data_bytes,
                file_name="quiz_rendered.json",
                mime="application/json"
            )

    except Exception as e:
        st.error(f"Lỗi đọc file: {e}")
else:
    st.info("📥 Hãy tải file .docx vào ô trên để bắt đầu.")
