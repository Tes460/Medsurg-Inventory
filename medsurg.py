import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 0. COMPANY SETTINGS
# ==========================================
COMPANY_NAME = "MEDSURG TECHNOLOGY"
COMPANY_ADDRESS = "Post Office Box 793, Madina\nAccra, Ghana"
COMPANY_PHONE = "+233 20 479 3691 / +233 24 200 1242"
COMPANY_EMAIL = "medsurgtechnology@gmail.com"
THANK_YOU_MSG = "Thank you for your business!"

# ==========================================
# 1. GOOGLE SHEETS CONNECTION
# ==========================================
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_db_connection():
    try:
        # Check if secrets exist
        if "gcp_service_account" not in st.secrets:
            st.error("❌ Secrets missing! Please go to Settings > Secrets on Streamlit Cloud.")
            st.stop()
            
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        return client.open("Medsurg Database")
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        st.stop()

def init_db():
    try:
        sh = get_db_connection()
        # Create sheets if they don't exist
        for sheet_name, headers in {
            "Inventory": ["Item Name", "Stock Qty", "Unit Price"],
            "Invoices": ["Invoice ID", "Customer Name", "Date", "Total Amount"],
            "Invoice_Items": ["Invoice ID", "Item Name", "Qty", "Subtotal"]
        }.items():
            try:
                sh.worksheet(sheet_name)
            except:
                ws = sh.add_worksheet(sheet_name, 100, 5)
                ws.append_row(headers)
    except Exception as e:
        st.warning(f"Database check failed (Might be connection issue): {e}")

def get_inventory():
    sh = get_db_connection()
    ws = sh.worksheet("Inventory")
    data = ws.get_all_records()
    if not data:
        return pd.DataFrame(columns=["Item Name", "Stock Qty", "Unit Price"])
    df = pd.DataFrame(data)
    # Force clean numbers
    df['Stock Qty'] = pd.to_numeric(df['Stock Qty'], errors='coerce').fillna(0).astype(int)
    df['Unit Price'] = pd.to_numeric(df['Unit Price'], errors='coerce').fillna(0.0).astype(float)
    return df

def add_or_update_item(name, qty, price):
    sh = get_db_connection()
    ws = sh.worksheet("Inventory")
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    
    if not df.empty and name in df['Item Name'].values:
        row_idx = df.index[df['Item Name'] == name].tolist()[0] + 2
        current_qty = df.loc[df['Item Name'] == name, 'Stock Qty'].values[0]
        new_qty = int(current_qty) + int(qty)
        ws.update_cell(row_idx, 2, new_qty)
        ws.update_cell(row_idx, 3, float(price))
        st.success(f"Updated '{name}': Stock is now {new_qty}")
    else:
        ws.append_row([name, int(qty), float(price)])
        st.success(f"Created '{name}'")

def delete_item(name):
    sh = get_db_connection()
    ws = sh.worksheet("Inventory")
    try:
        cell = ws.find(name)
        ws.delete_rows(cell.row)
        st.success(f"Deleted '{name}'")
    except:
        st.error("Item not found.")

# Run init
init_db()

# ==========================================
# 2. PDF GENERATOR (Safe Mode)
# ==========================================
def create_pdf(invoice_id, customer_name, date, items, total):
    pdf = FPDF()
    pdf.add_page()
    
    # Helper to clean text (removes non-latin chars that crash PDF)
    def clean(text):
        return str(text).encode('latin-1', 'replace').decode('latin-1')

    # Header
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 10, clean(COMPANY_NAME), ln=True, align='C')
    
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, clean(COMPANY_ADDRESS), align='C')
    pdf.cell(0, 5, f"Tel: {clean(COMPANY_PHONE)}", ln=True, align='C')
    pdf.cell(0, 5, f"Email: {clean(COMPANY_EMAIL)}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "OFFICIAL INVOICE", ln=True, align='C')
    
    pdf.set_font("Arial", size=11)
    pdf.cell(100, 8, f"Customer: {clean(customer_name)}", ln=0)
    pdf.cell(90, 8, f"Invoice #: {invoice_id}", ln=1, align='R')
    pdf.cell(100, 8, "", ln=0)
    pdf.cell(90, 8, f"Date: {clean(date)}", ln=1, align='R')
    pdf.ln(5)
    
    # Table
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(90, 10, "Description", 1, 0, 'L', True)
    pdf.cell(30, 10, "Qty", 1, 0, 'C', True)
    pdf.cell(35, 10, "Unit Price", 1, 0, 'R', True)
    pdf.cell(35, 10, "Total", 1, 1, 'R', True)
    
    pdf.set_font("Arial", size=11)
    for item in items:
        pdf.cell(90, 10, clean(item['item']), 1)
        pdf.cell(30, 10, str(item['qty']), 1, 0, 'C')
        pdf.cell(35, 10, f"{item['price']:.2f}", 1, 0, 'R')
        pdf.cell(35, 10, f"{item['subtotal']:.2f}", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(155, 10, "GRAND TOTAL (GHS):", 0, 0, 'R')
    pdf.cell(35, 10, f"{total:,.2f}", 0, 1, 'R')
    
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, clean(THANK_YOU_MSG), ln=True, align='C')
    
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 3. INTERFACE
# ==========================================
st.set_page_config(page_title="Medsurg Manager", layout="wide")
st.title(f"🏢 {COMPANY_NAME} Inventory System")

tab1, tab2, tab3 = st.tabs(["📦 Inventory", "🧾 New Sale", "📂 Records"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.subheader("Restock")
        with st.form("inv_form"):
            c1, c2, c3 = st.columns(3)
            new_name = c1.text_input("Item Name")
            new_qty = c2.number_input("Add Qty", 1, step=1)
            new_price = c3.number_input("Price (GHS)", 0.0, step=0.1)
            if st.form_submit_button("Update Inventory"):
                if new_name:
                    add_or_update_item(new_name, new_qty, new_price)
                    st.rerun()
    with col_b:
        st.subheader("Delete")
        df = get_inventory()
        if not df.empty:
            del_item = st.selectbox("Item", df['Item Name'].unique())
            if st.button("Delete"):
                delete_item(del_item)
                st.rerun()
    if not df.empty:
        st.dataframe(df, use_container_width=True)

with tab2:
    st.header("Point of Sale")
    df = get_inventory()
    if 'cart' not in st.session_state: st.session_state.cart = []
    
    with st.container():
        c1, c2, c3 = st.columns([3, 2, 1])
        if df.empty:
            st.warning("No items in stock.")
        else:
            item_list = df['Item Name'].unique()
            item = c1.selectbox("Product", item_list)
            qty = c2.number_input("Qty", 1)
            if c3.button("Add to Cart"):
                stock = df.loc[df['Item Name']==item, 'Stock Qty'].values[0]
                price = df.loc[df['Item Name']==item, 'Unit Price'].values[0]
                # Force Python Types
                stock = int(stock)
                price = float(price)
                if qty > stock:
                    st.error(f"Low Stock! Only {stock} left.")
                else:
                    st.session_state.cart.append({'item': item, 'qty': int(qty), 'price': price, 'subtotal': float(qty*price)})
                    st.success(f"Added {item}")

    st.divider()
    if st.session_state.cart:
        c_cart, c_bill = st.columns([2, 1])
        with c_cart:
            st.subheader("🛒 Cart")
            st.dataframe(pd.DataFrame(st.session_state.cart), use_container_width=True)
            if st.button("Clear Cart"):
                st.session_state.cart = []
                st.rerun()
        with c_bill:
            total = sum(x['subtotal'] for x in st.session_state.cart)
            st.metric("Total", f"GHS {total:,.2f}")
            cust = st.text_input("Customer", "Walk-in")
            if st.button("✅ Confirm & Print"):
                try:
                    sh = get_db_connection()
                    ws_inv = sh.worksheet("Invoices")
                    ws_items = sh.worksheet("Invoice_Items")
                    ws_stock = sh.worksheet("Inventory")
                    
                    inv_id = len(ws_inv.get_all_values()) + 1000
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 1. Update Sheet
                    ws_inv.append_row([int(inv_id), cust, ts, float(total)])
                    stock_df = pd.DataFrame(ws_stock.get_all_records())
                    
                    for i in st.session_state.cart:
                        row_idx = stock_df.index[stock_df['Item Name'] == i['item']].tolist()[0] + 2
                        curr = stock_df.loc[stock_df['Item Name'] == i['item'], 'Stock Qty'].values[0]
                        ws_stock.update_cell(row_idx, 2, int(curr) - int(i['qty']))
                        ws_items.append_row([int(inv_id), i['item'], int(i['qty']), float(i['subtotal'])])
                    
                    # 2. PDF
                    pdf_bytes = create_pdf(inv_id, cust, ts, st.session_state.cart, total)
                    st.download_button("Download PDF", pdf_bytes, f"Invoice_{inv_id}.pdf", "application/pdf")
                    st.success("Success!")
                    st.session_state.cart = []
                    
                except Exception as e:
                    st.error(f"An error occurred: {e}")

with tab3:
    st.header("Records")
    try:
        sh = get_db_connection()
        st.dataframe(pd.DataFrame(sh.worksheet("Invoices").get_all_records()), use_container_width=True)
    except:
        st.info("No records.")