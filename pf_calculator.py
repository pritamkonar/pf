import streamlit as st
import pandas as pd
from fpdf import FPDF
from io import BytesIO

# --- Page Configuration ---
st.set_page_config(page_title="PF Ledger Calculator", layout="wide")

st.title("💰 Provident Fund Ledger Calculator")
st.markdown("""
**Shyambazar D.N. High School Format**
This application replicates the manual ledger logic, including **P.F.L.R (Loan Recovery)**.
""")

# --- Sidebar: Initial Settings ---
st.sidebar.header("Configuration")
opening_balance_input = st.sidebar.number_input("Opening Balance (as of 1st April)", min_value=0.0, value=21880982.0, step=1000.0, format="%.2f")
default_rate = st.sidebar.number_input("Default Interest Rate (% per annum)", min_value=0.0, value=7.1, step=0.1)

# --- Main Data Entry ---
st.subheader("Monthly Entries")
st.info("Enter Deposits, P.F.L.R (Loan Recovery), and Withdrawals below.")

# Initialize the data structure for 12 months (Apr to Mar)
months = ["APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC", "JAN", "FEB", "MAR"]

# Create a default dataframe for inputs
if 'input_data' not in st.session_state:
    data = {
        "Month": months,
        "Dep_Before_15": [0.0] * 12,
        "Dep_After_15": [0.0] * 12,
        "PFLR": [0.0] * 12,  # <--- Added PFLR Column
        "Withdrawal": [0.0] * 12,
        "Rate": [default_rate] * 12
    }
    st.session_state.input_data = pd.DataFrame(data)

# Data Editor
edited_df = st.data_editor(
    st.session_state.input_data,
    column_config={
        "Month": st.column_config.TextColumn("Month", disabled=True),
        "Dep_Before_15": st.column_config.NumberColumn("Deposit (Within 15th)", format="₹ %.2f"),
        "Dep_After_15": st.column_config.NumberColumn("Deposit (After 15th)", format="₹ %.2f"),
        "PFLR": st.column_config.NumberColumn("P.F.L.R (Recovery)", format="₹ %.2f"), # <--- Configured PFLR
        "Withdrawal": st.column_config.NumberColumn("Withdrawal", format="₹ %.2f"),
        "Rate": st.column_config.NumberColumn("Interest Rate (%)", format="%.2f")
    },
    hide_index=True,
    use_container_width=True,
    num_rows="fixed"
)

# --- Calculation Engine ---
def calculate_ledger(opening_bal, input_df):
    results = []
    current_bal = opening_bal
    total_interest = 0

    for index, row in input_df.iterrows():
        month = row['Month']
        dep_before = row['Dep_Before_15']
        dep_after = row['Dep_After_15']
        pflr = row['PFLR']  # <--- Get PFLR value
        withdrawal = row['Withdrawal']
        rate = row['Rate']

        # Logic: Lowest Balance for Interest = Opening + Dep (Before 15th) - Withdrawal
        # Note: Based on the image, PFLR does NOT increase the Lowest Balance for the current month.
        lowest_bal_calc = current_bal + dep_before - withdrawal
        lowest_bal = max(0, lowest_bal_calc)

        # Logic: Monthly Interest = (Lowest Balance * Rate) / 1200
        interest = round((lowest_bal * rate) / 1200)
        
        # Logic: Closing Balance = Opening + All Deposits + PFLR - Withdrawal
        closing_bal = current_bal + dep_before + dep_after + pflr - withdrawal

        results.append({
            "Month": month,
            "Opening Balance": current_bal,
            "Dep (<15th)": dep_before,
            "Dep (>15th)": dep_after,
            "PFLR": pflr, # <--- Added to results
            "Withdrawal": withdrawal,
            "Lowest Balance": lowest_bal,
            "Rate (%)": rate,
            "Interest": interest,
            "Closing Balance": closing_bal
        })

        # Update Opening Balance for next month
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
    "Dep (>15th)": "₹ {:.2f}",
    "PFLR": "₹ {:.2f}",
    "Withdrawal": "₹ {:.2f}",
    "Lowest Balance": "₹ {:.2f}",
    "Interest": "₹ {:.2f}",
    "Closing Balance": "₹ {:.2f}"
}), use_container_width=True)

# Summary Metrics
final_balance_with_interest = final_principal + total_yearly_interest

col1, col2, col3 = st.columns(3)
col1.metric("Closing Principal (Mar 31)", f"₹ {final_principal:,.2f}")
col2.metric("Total Interest Earned", f"₹ {total_yearly_interest:,.2f}")
col3.metric("Final Balance (Inc. Interest)", f"₹ {final_balance_with_interest:,.2f}")

# --- Export Functions ---

# 1. Excel Export
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='PF_Ledger')
        workbook = writer.book
        worksheet = writer.sheets['PF_Ledger']
        format1 = workbook.add_format({'num_format': '₹ #,##0.00'})
        worksheet.set_column('B:J', 18, format1) # Adjusted for extra column
    processed_data = output.getvalue()
    return processed_data

excel_data = to_excel(result_df)
st.download_button(
    label="📥 Download as Excel",
    data=excel_data,
    file_name='PF_Ledger_Calculated.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

# 2. PDF Export
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Provident Fund Ledger Statement', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def to_pdf(df, final_bal, tot_int):
    pdf = PDF(orientation='L') 
    pdf.add_page()
    pdf.set_font("Arial", size=9)
    
    # Define Columns and Widths (Adjusted for PFLR)
    # Month, Open, Dep<15, Dep>15, PFLR, With, Low, Rate, Int, Close
    cols = ["Month", "Opening", "<15th", ">15th", "PFLR", "Withdr", "Lowest", "Rt", "Int", "Closing"]
    # Map dataframe columns to short names for header
    df_cols = df.columns.tolist() 
    
    # Widths (Total approx 275 for Landscape A4 safe area)
    col_widths = [15, 30, 22, 22, 22, 22, 30, 12, 20, 30] 
    
    # Table Header
    pdf.set_font("Arial", 'B', 8)
    for i, col in enumerate(cols):
        pdf.cell(col_widths[i], 10, col, 1, 0, 'C')
    pdf.ln()
    
    # Table Rows
    pdf.set_font("Arial", size=8)
    for index, row in df.iterrows():
        pdf.cell(col_widths[0], 10, str(row['Month']), 1)
        pdf.cell(col_widths[1], 10, f"{row['Opening Balance']:.0f}", 1)
        pdf.cell(col_widths[2], 10, f"{row['Dep (<15th)']:.0f}", 1)
        pdf.cell(col_widths[3], 10, f"{row['Dep (>15th)']:.0f}", 1)
        pdf.cell(col_widths[4], 10, f"{row['PFLR']:.0f}", 1)  # <--- PFLR in PDF
        pdf.cell(col_widths[5], 10, f"{row['Withdrawal']:.0f}", 1)
        pdf.cell(col_widths[6], 10, f"{row['Lowest Balance']:.0f}", 1)
        pdf.cell(col_widths[7], 10, str(row['Rate (%)']), 1)
        pdf.cell(col_widths[8], 10, f"{row['Interest']:.0f}", 1)
        pdf.cell(col_widths[9], 10, f"{row['Closing Balance']:.0f}", 1)
        pdf.ln()

    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Total Interest: {tot_int:,.2f}", 0, 1)
    pdf.cell(0, 10, f"Final Balance: {final_bal:,.2f}", 0, 1)
    
    return pdf.output(dest='S').encode('latin-1')

pdf_data = to_pdf(result_df, final_balance_with_interest, total_yearly_interest)
st.download_button(
    label="📄 Download as PDF",
    data=pdf_data,
    file_name='PF_Statement.pdf',
    mime='application/pdf'
)
