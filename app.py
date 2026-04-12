# app.py
import os
import json
import streamlit as st
from export import apply_month_to_xlsx
from pathlib import Path
from datetime import datetime

from db import add_transaction, upsert_adjustment, upsert_sales, upsert_fixed_cost
from db import get_fixed_cost_items_for_month
from db import get_sales_amount

def money_text_input(label: str, key: str, *, placeholder: str = "例: 1000 / 1,000") -> int | None:
    # SessionState 主導にする（value= は渡さない）
    if key not in st.session_state:
        st.session_state[key] = ""

    s = st.text_input(label, key=key, placeholder=placeholder)
    s = (s or "").strip()
    if s == "":
        return None

    s2 = s.replace(",", "")
    if not s2.isdigit():
        st.error("金額は数字のみで入力してください（例: 1000 / 1,000）")
        return None

    return int(s2)

BASE_DIR = Path(__file__).parent


# ------------------------
# 設定読み込み
# ------------------------
def load_templates():
    path = BASE_DIR / "templates.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


TEMPLATES = load_templates()

def scroll_box(height=520):
    return st.container(height=height, border=True)

# ------------------------
# 日付UI
# ------------------------
def date_inputs(prefix: str):
    col1, col2 = st.columns(2)

    with col1:
        m = st.selectbox(
            "月",
            list(range(1, 13)),
            key=f"{prefix}_month"
        )

    with col2:
        max_d = 31
        if m in (4, 6, 9, 11):
            max_d = 30
        elif m == 2:
            max_d = 29

        d = st.selectbox(
            "日",
            list(range(1, max_d + 1)),
            key=f"{prefix}_day"
        )

    y = datetime.now().year
    return y, m, d

def date_month_only(prefix: str):
    col1, col2 = st.columns(2)

    with col1:
        m = st.selectbox("月", list(range(1, 13)), key=f"{prefix}_month")

    with col2:
        st.text_input("日", value="1", disabled=True, key=f"{prefix}_day_fixed")

    y = datetime.now().year
    d = 1
    return y, m, d

# ------------------------
# 売上タブ
# ------------------------
def sales_tab():
    st.header("📈 売上入力")

    y, m, d = date_month_only("sales")

    sales_items = TEMPLATES["categories"]["売上"]

    item = st.selectbox("売上項目", sales_items)

    # 月×売上項目ごとに入力欄を分離（切替で空欄、戻すと復元、月が変われば月別） 
    amount_key = f"sales_amount_{m}_{item}"
    desc_key = f"sales_desc_{m}_{item}"

    # 初回だけDBから初期値を流し込む（登録済みは表示、未登録は空欄）
    if amount_key not in st.session_state:
        existing_amount = get_sales_amount(y=y, m=m, description=item)
        st.session_state[amount_key] = "" if existing_amount is None else str(existing_amount)

    if desc_key not in st.session_state:
        st.session_state[desc_key] = item

    amount = money_text_input("金額（円）", key=amount_key)
    description = st.text_input("摘要", key=desc_key)
    if st.button("登録（売上）"):
        if amount is None:
            st.error("金額を入力してください")
            return

        if amount <= 0:
            st.error("金額は1円以上で入力してください")
            return

        ok, msg = upsert_sales(
            y=y,
            m=m,
            d=d,
            description=description,
            amount=amount,
        )

        if ok:
            st.success(msg)
        else:
            st.error(msg)

# ------------------------
# 固定費タブ
# ------------------------
def fixed_cost_tab():
    st.header("🏠 固定費入力")

    # 月だけ選ぶ（各項目の日付は個別）
    y = datetime.now().year
    m = st.selectbox("月", list(range(1, 13)), key="fixed_month")

    fixed_items = TEMPLATES["categories"]["固定費"]
    code_map = TEMPLATES["code_map"]
    default_map = TEMPLATES["default_code_for_item"]

    inputs = {}   # {item: amount}
    days = {}     # {item: day}

    with scroll_box():
        st.caption("※ 入力した項目だけ登録されます（各項目ごとに日を選べます）")

        for item in fixed_items:
            col1, col2 = st.columns([3, 1])

            with col1:
                inputs[item] = money_text_input(f"{item}（円）", key=f"fixed_amount_{item}")

            with col2:
                days[item] = st.selectbox(
                    "日",
                    list(range(1, 32)),
                    key=f"fixed_day_{item}",
                )

        filled = [k for k, v in inputs.items() if v is not None and v > 0]

        # DB登録済み（この月）の件数を表示（※月を変えたらここが変わる）
        fixed_codes = []
        for _item in fixed_items:
            _code_name = default_map.get(_item)
            _code = code_map.get(_code_name)
            if _code is not None:
                fixed_codes.append(int(_code))

        registered_items = get_fixed_cost_items_for_month(y=y, m=m, items=fixed_items)
        registered_count = len(registered_items)

        if registered_count == len(fixed_items):
            st.success("✅ すべて登録済み（この月）")
        elif registered_count == 0:
            st.warning("⚠️ まだ登録されていません（この月）")
        else:
            st.info(f"📌 登録済み：{registered_count} / {len(fixed_items)}（この月）")

        if st.button("登録（固定費まとめて）"):
            if not filled:
                st.error("金額を入力してください")
                return

            success = 0

            for item in filled:
                code_name = default_map.get(item)
                code = code_map.get(code_name)

                d = int(days[item])  # ← 各項目ごとの日付

                ok, _msg = upsert_fixed_cost(
                    y=y,
                    m=m,
                    d=d,
                    code=code,
                    item=item,
                    amount=inputs[item],
                )

            if ok:
                    success += 1

            st.success(f"✅ {success}件 登録しました！")

# ------------------------
# 経費タブ
# ------------------------
def expense_tab():
    st.header("🧾 経費入力")

    y, m, d = date_inputs("expense")

    # --- ワンクリ金額入力のリセット用キー ---
    if "expense_quick_key" not in st.session_state:
       st.session_state["expense_quick_key"] = 0  

    code_map = TEMPLATES["code_map"]
    default_map = TEMPLATES["default_code_for_item"]
    quick_items = TEMPLATES["categories"]["経費_ワンクリ"]

    with scroll_box():
        st.subheader("✅ ワンクリ登録（主要）")

        # 摘要（ワンクリ）→ 科目を自動決定
        quick_desc_items = ["ガソリン", "食事", "駐車場", "タクシー"]
        quick_desc = st.selectbox("摘要（ワンクリ）", quick_desc_items, key="expense_quick_desc2")
        quick_amount = money_text_input(
            "金額（円）",
            key=f"expense_quick_amount_{st.session_state['expense_quick_key']}"
        )
        quick_subject_map = {
            "駐車場": "車両費",
            "ガソリン": "車両費",
            "食事": "接待交際費",
            "タクシー": "旅費交通費",
        }
        quick_subject = quick_subject_map[quick_desc]
        st.write(f"科目（自動）：**{quick_subject}**")

        force_quick = st.checkbox("重複でも登録する", key="expense_quick_force")

        if st.button("登録（ワンクリ）", key="btn_expense_quick"):
            if quick_amount is None:
                st.error("金額を入力してください")
                return
            if quick_amount <= 0:
                st.error("金額は1円以上で入力してください")
                return

            code = code_map.get(quick_subject)
            if code is None:
                st.error(f"科目が見つかりません: {quick_subject}")
                return

            ok, err = add_transaction(
                y=y,
                m=m,
                d=d,
                code=code,
                description=quick_desc,  # 摘要として保存
                amount=quick_amount,
                direction="out",
                force=force_quick,
            )
            if ok:
                st.success("登録しました！")

                # 入力欄を完全リセット（keyを切り替える）
                st.session_state["expense_quick_key"] += 1
                st.rerun()

            else:
                st.error(err)

        st.divider()

        st.subheader("✍️ 手入力（科目を選ぶ）")

        # 優先順で並べる
        priority_subjects = ["車両費", "接待交際費", "消耗品費", "旅費交通費", "通信費"]
        subjects = [s for s in priority_subjects if s in code_map] + [s for s in code_map.keys() if s not in priority_subjects]

        desc = st.text_input("摘要（手入力）", value="", key="expense_manual_desc")
        amount = money_text_input("金額（円）（手入力）", key="expense_manual_amount")

        subject = st.selectbox("科目", subjects, key="expense_subject")
        code = code_map[subject]

        force_manual = st.checkbox("重複でも登録する", key="expense_manual_force")

        if st.button("登録（手入力）", key="btn_expense_manual"):
            if amount is None:
                st.error("金額を入力してください")
            elif amount <= 0:
                st.error("金額は1円以上で入力してください")
            elif not desc.strip():
                st.error("摘要を入力してください")
            else:
                ok, err = add_transaction(
                    y=y,
                    m=m,
                    d=d,
                    code=code,
                    description=desc,
                    amount=amount,
                    direction="out",
                    force=force_manual,
                )
                if ok:
                    st.success("登録しました！")

                    # 入力欄を完全リセット（keyを切り替える）
                    st.session_state["expense_quick_key"] += 1
                    st.rerun()

                else:
                    st.error(err)

# ------------------------
# 反映タブ（SQLite → 本命xlsx）
# ------------------------
def reflect_tab():
    st.header("📤 反映（SQLite → 本命xlsx）")

    st.write("※ 反映先は Excel の **現金** タブのみ（他タブは触りません）")
    st.write("※ 指定月の未反映データだけ追記し、反映済みにします（重複はスキップ）")

    base_dir = Path.home() / "Desktop" / "tatsunori-DEV" / "finance" / "keihi_xlsx"
    st.caption(f"推奨フォルダ: {base_dir}")

    y = datetime.now().year
    month = st.selectbox("反映する月", list(range(1, 13)), key="reflect_month")
    base_dir = Path.home() / "Desktop" / "tatsunori-DEV" / "finance" / "keihi_xlsx"
    default_path = base_dir / f"{month}月簡易版青色申告決算書.xlsx"

    if "reflect_path" not in st.session_state:
        st.session_state["reflect_path"] = str(default_path)

    # 月を変えたらパスも追従
    st.session_state["reflect_path"] = str(default_path)
    default_path = base_dir / f"{month}月簡易版青色申告決算書.xlsx"


    xlsx_path_str = st.text_input("本命xlsxのパス", key="reflect_path")

    xlsx_path = Path(xlsx_path_str).expanduser()

    if st.button("反映する", key="btn_reflect"):
        if not xlsx_path.exists():
            st.error(f"ファイルが見つかりません: {xlsx_path}")
            return

        try:
            added, skipped = apply_month_to_xlsx(xlsx_path=xlsx_path, year=y, month=month)
            st.success(f"反映完了：追加 {added}件 / スキップ {skipped}件\n保存先：{xlsx_path}")
        except Exception as e:
            st.error(f"反映に失敗しました: {e}")

# ------------------------
# 調整用タブ（年まとめ：SQLiteに保存）
# ------------------------
def adjustment_tab():
    st.header("🧩 調整用（年まとめ）")

    y = datetime.now().year
    m = st.selectbox("月", list(range(1, 13)), key="adj_month")

    with scroll_box():
        st.write("※ 調整用は仕訳にしません（本命月別xlsxには入れない）")
        st.write("※ ここに入れた内容は、あとで 2026_調整一覧.xlsx に反映します")

        st.subheader("家賃（合計）")
        rent_total = money_text_input("家賃（合計）（円）", key="adj_rent_total")
        rent_note = "（共営費/駐車料/上下水道/暖房含む）"

        st.subheader("社会保険など")
        health = money_text_input("健康保険（円）", key="adj_health")
        pension = money_text_input("年金（円）", key="adj_pension")

        st.divider()

        if st.button("保存（調整用）", key="btn_adj_save"):
            upsert_adjustment(y=y, m=m, item="家賃（合計）", amount=rent_total or 0, note=rent_note)
            upsert_adjustment(y=y, m=m, item="健康保険", amount=health or 0, note="")
            upsert_adjustment(y=y, m=m, item="年金", amount=pension or 0, note="")
            upsert_adjustment(y=y, m=m, item="AppleCare（表示のみ）", amount=1340, note="固定：表示のみ")
            upsert_adjustment(y=y, m=m, item="市道民税（❌経費にしない）", amount=0, note="表示のみ")
            st.success("保存しました！（SQLite）")

        st.caption("※ 入力した項目だけ登録されます")
        st.subheader("メモ枠")
        st.caption("AppleCare：1340円（表示のみ）")
        st.caption("市道民税（❌経費にしない）（表示のみ）")



# ------------------------
# メイン
# ------------------------
def main():
    from PIL import Image as _PILImage
    st.set_page_config(page_title="経費計上App", page_icon=_PILImage.open(os.path.join(os.path.dirname(__file__), "icon.png")), layout="centered")

    st.title("📒 経費計上App")

    tabs = st.tabs(
        [
            "売上",
            "固定費",
            "経費",
            "調整用",
            "反映",
        ]
    )

    with tabs[0]:
        sales_tab()

    with tabs[1]:
        fixed_cost_tab()

    with tabs[2]:
        expense_tab()

    with tabs[3]:
        adjustment_tab()

    with tabs[4]:
        reflect_tab()

if __name__ == "__main__":
    main()
