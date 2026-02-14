import pandas as pd
import openpyxl

try:
    print("\nChecking Variaveis_para_Previsão_260105.xlsx")
    wb = openpyxl.load_workbook('Variaveis_para_Previsão_260105.xlsx', data_only=True)
    ws = wb.active
    data = []
    for row in ws.iter_rows(values_only=True):
        data.append(row)
    
    df = pd.DataFrame(data[1:], columns=data[0])
    
    # Check date and ICMS
    first_col = df.columns[0]
    icms_col = [c for c in df.columns if 'icms' in str(c).lower()][0]
    
    valid_icms = df[df[icms_col].notna()]
    print(f"Total rows: {len(df)}")
    print(f"Valid ICMS rows: {len(valid_icms)}")
    print("Last 5 valid ICMS rows:")
    print(valid_icms[[first_col, icms_col]].tail(5))
    
except Exception as e:
    print(e)
