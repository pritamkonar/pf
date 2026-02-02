import streamlit as st
import pandas as pd
from fpdf import FPDF
from io import BytesIO
import math

# --- Page Configuration ---
st.set_page_config(page_title="PF Ledger (Nearest Rupee)", layout="wide")

st.title("💰 Provident Fund Ledger (Nearest Rupee Mode)")
st.markdown("""
**Updated Logic:**
1.  **Rounding:** Interest is now rounded to the **Nearest Rupee**.
    * `15.50` or higher → `16`
    * `15.49` or lower → `15`
2.  **P.F.L.R:** Logic remains (adds to Lowest Balance for Nov-Mar).
""")

# --- Sidebar: Configuration ---
st.sidebar.header("Configuration")
start_year = st.sidebar.number_input("Financial Year Start", value=2024, step=1)
opening_balance_input = st.sidebar.number_input("Opening Balance (April 1st)", min_value=0.0, value=1624526.0, step=100.0, format="%.2f")
rate_input = st.sidebar.number_input("Interest Rate (%)", min_value=0.0, value=7.1, step=0.1, format="%.2f")

# --- Helper: Generate Financial Year Months ---
def get_fy_months(start_year):
    m_names = ["April", "May", "June", "July", "August", "September", "October", "November", "December", "January", "February", "March"]
    fy_months = []
    for i, m in enumerate(m_names):
        y = start_year if i < 9 else start_year + 1
        fy_months.append(f"{m} '{str(y)[-2:]}")
    return fy_months

months_list = get_fy_months(start_year)

# --- Main Data Entry ---
if 'input_data' not in st.session_state:
    data = {
        "Month": months_list,
        "Dep_Before_15": [0.0] * 12, # Col 6(a)
        "PFLR": [3000.0] * 12,       # Default PFLR
        "Dep_After_15": [0.0] * 12,  # Col 6(b)
        "Withdrawal": [0.0] * 12,
        "Rate": [rate_input] * 12
    }
    
    st.session_state.input_data = pd.DataFrame(data)
else:
    st.session_state.input_data["Month"] = months_list
    st.session_state.input_data["Rate"] = rate_input

edited_df = st.data_editor(
    st.session_state.input_data,
    column_config={
        "Month": st.column_config.TextColumn("Month", disabled=True),
        "Dep_Before_15": st.column_config.NumberColumn("Deposit (<15th) [Col 6a]", format="₹ %.2f"),
        "PFLR": st.column_config.NumberColumn("P.F.L.R", format="₹ %.2f"),
        "Dep_After_15": st.column_config.NumberColumn("Deposit (>15th) [Col 6b]", format="₹ %.2f"),
        "Withdrawal": st.column_config.NumberColumn("Withdrawal", format="₹ %.2f"),
        "Rate": st.column_config.NumberColumn("Rate %", format="%.2f")
    },
    hide_index=True,
    use_container_width=True,
    num_rows="fixed"
)

# --- Calculation Engine ---
def calculate_ledger(opening_bal, input_df):
    results = []
    current_bal = opening_bal
    total_interest = 0.0

    for index, row in input_df.iterrows():
        month = row['Month']
        dep_before = row['Dep_Before_15']
        dep_after = row['Dep_After_15']
        pflr = row['PFLR']
        withdrawal = row['Withdrawal']
        rate = row['Rate']

        # --- LOGIC: Lowest Balance ---
        if dep_before > 0:
            effective_deposit = dep_before + pflr
        else:
            effective_deposit = 0 
        
        lowest_bal_calc = current_bal + effective_deposit - withdrawal
        lowest_bal = max(0, lowest_bal_calc)

        # --- LOGIC: Interest Rounding (Nearest Rupee) ---
        raw_interest = (lowest_bal * rate) / 1200
        
        # This formula implements standard rounding:
        # int(x + 0.5) converts 15.5 -> 16, 15.49 -> 15
        interest = int(raw_interest + 0.5)

        # --- LOGIC: Closing Balance ---
        closing_bal = current_bal + dep_before + dep_after + pflr - withdrawal

        results.append({
            "Month": month,
            "Opening Balance": current_bal,
            "Dep (<15th)": dep_before,
            "PFLR": pflr,
            "Dep (>15th)": dep_after,
            "Withdrawal": withdrawal,
            "Lowest Balance": lowest_bal,
            "Rate (%)": rate,
            "Interest": interest,
            "Closing Balance": closing_bal
        })

        current_bal = closing_bal
        total_interest += interest

    return pd.DataFrame(results), total_interest, current_bal

# Perform Calculation
result_df, total_yearly_interest, final_principal = calculate_ledger(opening_balance_input, edited_df)

# --- Display Results ---
st.subheader("Calculation Result")

st.dataframe(result_df.style.format({
    "Opening Balance": "₹ {:.2f}",
    "Dep (<15th)": "₹ {:.2f}",
    "PFLR": "₹ {:.2f}",
    "Dep (>15th)": "₹ {:.2f}",
    "Withdrawal": "₹ {:.2f}",
    "Lowest Balance": "₹ {:.2f}",
    "Interest": "₹ {:.0f}",  # <--- Changed to show Integer
    "Closing Balance": "₹ {:.2f}"
}), use_container_width=True)

# Summary
final_balance_with_interest = final_principal + total_yearly_interest
col1, col2, col3 = st.columns(3)
col1.metric("Closing Principal", f"₹ {final_principal:,.2f}")
col2.metric("Total Interest", f"₹ {total_yearly_interest:,.0f}") # <--- Integer
col3.metric("Final Balance", f"₹ {final_balance_with_interest:,.2f}")

# --- PDF Export ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'PF Ledger Statement', 0, 1, 'C')
        self.ln(5)

def to_pdf(df, final_bal, tot_int, year_label):
    pdf = PDF(orientation='L') 
    pdf.add_page()
    pdf.set_font("Arial", size=8)
    
    # Title
    pdf.cell(0, 10, f"Financial Year: {year_label}-{year_label+1}", 0, 1, 'L')

    cols = ["Month", "Open", "Dep<15", "PFLR", "Dep>15", "Withdr", "Lowest", "Rate", "Int", "Close"]
    col_widths = [20, 30, 20, 20, 20, 20, 30, 10, 20, 30] 
    
    pdf.set_font("Arial", 'B', 8)
    for i, col in enumerate(cols):
        pdf.cell(col_widths[i], 10, col, 1, 0, 'C')
    pdf.ln()
    
    pdf.set_font("Arial", size=8)
    for index, row in df.iterrows():
        pdf.cell(col_widths[0], 10, str(row['Month']), 1)
        pdf.cell(col_widths[1], 10, f"{row['Opening Balance']:.2f}", 1)
        pdf.cell(col_widths[2], 10, f"{row['Dep (<15th)']:.2f}", 1)
        pdf.cell(col_widths[3], 10, f"{row['PFLR']:.2f}", 1)
        pdf.cell(col_widths[4], 10, f"{row['Dep (>15th)']:.2f}", 1)
        pdf.cell(col_widths[5], 10, f"{row['Withdrawal']:.2f}", 1)
        pdf.cell(col_widths[6], 10, f"{row['Lowest Balance']:.2f}", 1)
        pdf.cell(col_widths[7], 10, str(row['Rate (%)']), 1)
        pdf.cell(col_widths[8], 10, f"{row['Interest']:.0f}", 1) # <--- Round to Integer in PDF
        pdf.cell(col_widths[9], 10, f"{row['Closing Balance']:.2f}", 1)
        pdf.ln()

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, f"Total Interest: {tot_int:,.0f}", 0, 1) # <--- Integer
    pdf.cell(0, 10, f"Final Balance: {final_bal:,.2f}", 0, 1)
    
    return pdf.output(dest='S').encode('latin-1')

pdf_data = to_pdf(result_df, final_balance_with_interest, total_yearly_interest, start_year)
st.download_button("📄 Download PDF", pdf_data, 'PF_Statement_Final.pdf', 'application/pdf')
