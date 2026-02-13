#!/usr/bin/env python3
"""
Pipeline SEFAZ - Previsão ICMS-SP
Autor: Tiuito
Data: 2026-02-13

Pipeline automatizado de previsão de arrecadação ICMS para São Paulo.
Fontes: BCB (IBC-BR), IPEA (IGP-DI), Focus (expectativas), SEFAZ (ICMS_SP)
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime
from calendar import monthrange
import warnings
warnings.filterwarnings('ignore')


def dias_uteis_ano_mes(ano, mes):
    """Calcula dias úteis do mês (segunda a sexta)."""
    dias_total = monthrange(ano, mes)[1]
    uteis = sum(1 for dia in range(1, dias_total + 1) 
                if datetime(ano, mes, dia).weekday() < 5)
    return uteis


def baixar_ibc_br():
    """Baixa série IBC-BR do BCB (código 24363)."""
    print("📊 Baixando IBC-BR (BCB)...")
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.24363/dados?formato=json"
    resp = requests.get(url, timeout=30)
    data = resp.json()
    df = pd.DataFrame(data)
    df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
    df['valor'] = df['valor'].astype(float)
    df = df.rename(columns={'valor': 'ibc_br'})
    print(f"   ✓ {len(df)} registros ({df['data'].min().strftime('%m/%Y')} a {df['data'].max().strftime('%m/%Y')})")
    return df


def baixar_igp_di():
    """Baixa série IGP-DI do IPEA Data."""
    print("📊 Baixando IGP-DI (IPEA)...")
    url = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='IGP12_IGPDI12')"
    resp = requests.get(url, timeout=30)
    data = resp.json()['value']
    df = pd.DataFrame(data)
    df['data'] = pd.to_datetime(df['VALDATA'].str[:10])
    df['igp_di'] = df['VALVALOR']
    df = df[['data', 'igp_di']]
    print(f"   ✓ {len(df)} registros ({df['data'].min().strftime('%m/%Y')} a {df['data'].max().strftime('%m/%Y')})")
    return df


def baixar_focus():
    """Baixa expectativas Focus para 2026."""
    print("📊 Baixando Expectativas Focus (BCB)...")
    url = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais?$filter=DataReferencia%20eq%20'2026'&$orderby=Data%20desc&$top=100&$format=json"
    resp = requests.get(url, timeout=30)
    data = resp.json()['value']
    df = pd.DataFrame(data)
    
    # Extrair expectativas relevantes
    pib = df[df['Indicador'] == 'PIB Total']['Mediana'].values[0]
    igpm = df[df['Indicador'] == 'IGP-M']['Mediana'].values[0]
    
    print(f"   ✓ PIB 2026: {pib}%")
    print(f"   ✓ IGP-M 2026: {igpm}%")
    
    return {'pib_2026': pib / 100, 'igpm_2026': igpm / 100}


def criar_base_consolidada(ibc_df, igp_df, expectativas):
    """Cria base temporal completa com projeções."""
    print("\n📊 Criando base consolidada...")
    
    # Criar série temporal (2003-2026)
    dates = pd.date_range(start='2003-01-01', end='2026-12-01', freq='MS')
    df = pd.DataFrame({'data': dates})
    df['ano'] = df['data'].dt.year
    df['mes'] = df['data'].dt.month
    
    # Merge dados externos
    df = df.merge(ibc_df, on='data', how='left')
    igp_df = igp_df[igp_df['data'] >= '2003-01-01']
    df = df.merge(igp_df, on='data', how='left')
    
    # Dias úteis
    df['dias_uteis'] = df.apply(lambda x: dias_uteis_ano_mes(x['ano'], x['mes']), axis=1)
    
    # Dummies estruturais
    df['LS2008NOV'] = (((df['ano'] == 2008) & (df['mes'] >= 11)) | (df['ano'] > 2008)).astype(int)
    df['TC2020APR04'] = ((df['ano'] == 2020) & (df['mes'] >= 4) & (df['mes'] <= 7)).astype(int)
    df['TC2022OUT05'] = (((df['ano'] == 2022) & (df['mes'] >= 10)) | 
                          ((df['ano'] == 2023) & (df['mes'] <= 5))).astype(int)
    
    # Projeção IBC-BR (2025-2026)
    print("   📈 Projetando IBC-BR...")
    ibc_nov_2025 = df[df['data'] == '2025-11-01']['ibc_br'].values[0]
    growth_ibc = (1 + expectativas['pib_2026']) ** (1/12) - 1
    for i, idx in enumerate(df[df['data'] >= '2025-12-01'].index):
        if pd.isna(df.loc[idx, 'ibc_br']):
            df.loc[idx, 'ibc_br'] = ibc_nov_2025 * ((1 + growth_ibc) ** (i + 1))
    
    # Projeção IGP-DI (2026)
    print("   📈 Projetando IGP-DI...")
    igp_jan_2026 = df[df['data'] == '2026-01-01']['igp_di'].values[0]
    growth_igp = (1 + expectativas['igpm_2026']) ** (1/11) - 1
    for i, idx in enumerate(df[df['data'] >= '2026-02-01'].index):
        if pd.isna(df.loc[idx, 'igp_di']):
            df.loc[idx, 'igp_di'] = igp_jan_2026 * ((1 + growth_igp) ** i)
    
    print(f"   ✓ Base criada: {len(df)} meses")
    return df


def criar_lags(df):
    """Cria lags e diferenciações."""
    print("\n📊 Criando lags...")
    
    # Lags (1-4 períodos)
    for lag in range(1, 5):
        df[f'ibc_br_lag{lag}'] = df['ibc_br'].shift(lag)
        df[f'igp_di_lag{lag}'] = df['igp_di'].shift(lag)
        df[f'dias_uteis_lag{lag}'] = df['dias_uteis'].shift(lag)
    
    # Logs e diferenças
    df['ibc_br_log'] = np.log(df['ibc_br'])
    df['igp_di_log'] = np.log(df['igp_di'])
    df['ibc_br_diff'] = df['ibc_br_log'].diff()
    df['igp_di_diff'] = df['igp_di_log'].diff()
    
    print(f"   ✓ {len(df.columns)} colunas criadas")
    return df


def modelo_arx(df):
    """Modelo ARX(1) simplificado."""
    print("\n📊 Ajustando modelo ARX(1)...")
    
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_absolute_percentage_error, r2_score
    
    # Dados de treino (até último ICMS disponível)
    train = df[df['data'] <= '2024-01-01'].copy()
    train = train.dropna(subset=['icms_sp'])
    
    # Criar lag do ICMS
    train['icms_sp_log'] = np.log(train['icms_sp'])
    train['icms_sp_log_lag1'] = train['icms_sp_log'].shift(1)
    train = train.dropna()
    
    y = train['icms_sp_log'].values
    X = train[['icms_sp_log_lag1', 'ibc_br', 'igp_di', 'dias_uteis',
               'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']].values
    
    # Ajustar modelo
    model = LinearRegression()
    model.fit(X, y)
    
    # Métricas
    y_pred = model.predict(X)
    mape = mean_absolute_percentage_error(np.exp(y), np.exp(y_pred)) * 100
    r2 = r2_score(y, y_pred)
    
    print(f"   ✓ MAPE: {mape:.2f}%")
    print(f"   ✓ R²: {r2:.4f}")
    
    return model, train['icms_sp'].iloc[-1]


def projetar(model, df, icms_last):
    """Projeta ICMS para 2024-2026."""
    print("\n📊 Projetando ICMS 2024-2026...")
    
    future = df[df['data'] > '2024-01-01'].sort_values('data')
    previsoes = []
    icms_current_log = np.log(icms_last)
    
    for _, row in future.iterrows():
        X = np.array([[icms_current_log, row['ibc_br'], row['igp_di'], 
                      row['dias_uteis'], row['LS2008NOV'], 
                      row['TC2020APR04'], row['TC2022OUT05']]])
        
        icms_next_log = model.predict(X)[0]
        icms_next = np.exp(icms_next_log)
        
        previsoes.append({
            'data': row['data'],
            'icms_previsto': icms_next
        })
        icms_current_log = icms_next_log
    
    prev_df = pd.DataFrame(previsoes)
    
    # Totais anuais
    print("\n💰 Totais Anuais:")
    for ano in [2024, 2025, 2026]:
        total = prev_df[prev_df['data'].dt.year == ano]['icms_previsto'].sum()
        print(f"   {ano}: R$ {total/1e9:.2f} bilhões")
    
    return prev_df


def main():
    """Executa pipeline completo."""
    print("="*60)
    print("PIPELINE SEFAZ - PREVISÃO ICMS-SP")
    print("="*60)
    
    # 1. Download dados externos
    ibc_df = baixar_ibc_br()
    igp_df = baixar_igp_di()
    expectativas = baixar_focus()
    
    # 2. Criar base consolidada
    df = criar_base_consolidada(ibc_df, igp_df, expectativas)
    df = criar_lags(df)
    
    # 3. Integrar ICMS_SP (se disponível)
    try:
        import openpyxl
        wb = openpyxl.load_workbook('Variaveis_para_Previsão_260105.xlsx', data_only=True)
        ws = wb.active
        icms_data = []
        for row in ws.iter_rows(min_row=2, max_row=289, values_only=True):
            if row[0] and isinstance(row[0], type(ws['A2'].value)):
                icms_data.append({'data': row[0], 'icms_sp': row[1]})
        icms_df = pd.DataFrame(icms_data)
        df = df.merge(icms_df, on='data', how='left')
        print(f"\n📊 ICMS_SP integrado: {df['icms_sp'].notna().sum()} meses disponíveis")
    except Exception as e:
        print(f"\n⚠️ ICMS_SP não disponível: {e}")
        df['icms_sp'] = np.nan
    
    # 4. Modelo e projeção
    model, icms_last = modelo_arx(df)
    prev_df = projetar(model, df, icms_last)
    
    # 5. Salvar resultados
    df.to_csv('base_final.csv', index=False)
    prev_df.to_csv('previsoes_icms.csv', index=False)
    
    print("\n" + "="*60)
    print("PIPELINE CONCLUÍDO ✓")
    print("="*60)
    print("\n📁 Arquivos gerados:")
    print("   ✓ base_final.csv")
    print("   ✓ previsoes_icms.csv")


if __name__ == '__main__':
    main()
