#!/usr/bin/env python3
"""
Pipeline SEFAZ - Previsão ICMS-SP (v3 - Todos os Modelos)
Autor: Tiuito
Data: 2026-02-13

Pipeline com 5 modelos SARIMAX completos salvos individualmente.
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime
from calendar import monthrange
import warnings
import json
warnings.filterwarnings('ignore')

from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.stattools import adfuller


def dias_uteis_ano_mes(ano, mes):
    """Calcula dias úteis do mês."""
    dias_total = monthrange(ano, mes)[1]
    return sum(1 for dia in range(1, dias_total + 1) 
               if datetime(ano, mes, dia).weekday() < 5)


def baixar_dados():
    """Baixa todos os dados externos."""
    print("="*60)
    print("DOWNLOAD DE DADOS EXTERNOS")
    print("="*60)
    
    # IBC-BR
    print("\n📊 IBC-BR (BCB)...")
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.24363/dados?formato=json"
    resp = requests.get(url, timeout=30)
    ibc = pd.DataFrame(resp.json())
    ibc['data'] = pd.to_datetime(ibc['data'], format='%d/%m/%Y')
    ibc['ibc_br'] = ibc['valor'].astype(float)
    print(f"   ✓ {len(ibc)} registros até {ibc['data'].max().strftime('%m/%Y')}")
    
    # IGP-DI
    print("\n📊 IGP-DI (IPEA)...")
    url = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='IGP12_IGPDI12')"
    resp = requests.get(url, timeout=30)
    igp = pd.DataFrame(resp.json()['value'])
    igp['data'] = pd.to_datetime(igp['VALDATA'].str[:10])
    igp['igp_di'] = igp['VALVALOR']
    igp = igp[igp['data'] >= '2003-01-01'][['data', 'igp_di']]
    print(f"   ✓ {len(igp)} registros até {igp['data'].max().strftime('%m/%Y')}")
    
    # Focus
    print("\n📊 Expectativas Focus...")
    url = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais?$filter=DataReferencia%20eq%20'2026'&$orderby=Data%20desc&$top=100&$format=json"
    resp = requests.get(url, timeout=30)
    focus = pd.DataFrame(resp.json()['value'])
    exp = {
        'pib': focus[focus['Indicador'] == 'PIB Total']['Mediana'].values[0] / 100,
        'igpm': focus[focus['Indicador'] == 'IGP-M']['Mediana'].values[0] / 100
    }
    print(f"   ✓ PIB 2026: {exp['pib']*100:.2f}%")
    print(f"   ✓ IGP-M 2026: {exp['igpm']*100:.1f}%")
    
    return ibc[['data', 'ibc_br']], igp, exp


def preparar_base(ibc_df, igp_df, expectativas):
    """Cria base consolidada com projeções."""
    print("\n" + "="*60)
    print("PREPARAÇÃO DA BASE")
    print("="*60)
    
    dates = pd.date_range(start='2003-01-01', end='2026-12-01', freq='MS')
    df = pd.DataFrame({'data': dates})
    df['ano'] = df['data'].dt.year
    df['mes'] = df['data'].dt.month
    
    df = df.merge(ibc_df, on='data', how='left')
    df = df.merge(igp_df, on='data', how='left')
    
    df['dias_uteis'] = df.apply(lambda x: dias_uteis_ano_mes(x['ano'], x['mes']), axis=1)
    
    df['LS2008NOV'] = (((df['ano'] == 2008) & (df['mes'] >= 11)) | (df['ano'] > 2008)).astype(int)
    df['TC2020APR04'] = ((df['ano'] == 2020) & (df['mes'] >= 4) & (df['mes'] <= 7)).astype(int)
    df['TC2022OUT05'] = (((df['ano'] == 2022) & (df['mes'] >= 10)) | 
                         ((df['ano'] == 2023) & (df['mes'] <= 5))).astype(int)
    
    # Lags
    for col in ['ibc_br', 'igp_di', 'dias_uteis']:
        for lag in range(1, 5):
            df[f'{col}_lag{lag}'] = df[col].shift(lag)
    
    # Projeção IBC-BR
    print("\n📈 Projetando IBC-BR...")
    ibc_nov = df[df['data'] == '2025-11-01']['ibc_br'].values[0]
    growth = (1 + expectativas['pib']) ** (1/12) - 1
    for i, idx in enumerate(df[df['data'] >= '2025-12-01'].index):
        if pd.isna(df.loc[idx, 'ibc_br']):
            df.loc[idx, 'ibc_br'] = ibc_nov * ((1 + growth) ** (i + 1))
    
    # Projeção IGP-DI
    print("📈 Projetando IGP-DI...")
    igp_jan = df[df['data'] == '2026-01-01']['igp_di'].values[0]
    growth = (1 + expectativas['igpm']) ** (1/11) - 1
    for i, idx in enumerate(df[df['data'] >= '2026-02-01'].index):
        if pd.isna(df.loc[idx, 'igp_di']):
            df.loc[idx, 'igp_di'] = igp_jan * ((1 + growth) ** i)
    
    print(f"   ✓ Base: {len(df)} meses x {len(df.columns)} colunas")
    return df


def carregar_icms(df):
    """Carrega ICMS_SP da planilha SEFAZ."""
    print("\n📊 Carregando ICMS_SP...")
    try:
        import openpyxl
        wb = openpyxl.load_workbook('dados_sefaz.xlsx', data_only=True)
        ws = wb.active
        icms_data = []
        for row in ws.iter_rows(min_row=2, max_row=289, values_only=True):
            if row[0] and isinstance(row[0], datetime):
                icms_data.append({'data': row[0], 'icms_sp': row[1]})
        icms_df = pd.DataFrame(icms_data)
        df = df.merge(icms_df, on='data', how='left')
        n_valid = df['icms_sp'].notna().sum()
        print(f"   ✓ ICMS_SP: {n_valid} meses (até {df[df['icms_sp'].notna()]['data'].max().strftime('%m/%Y')})")
    except Exception as e:
        print(f"   ⚠️ Erro: {e}")
        df['icms_sp'] = np.nan
    return df


def ajustar_modelo(y, X, ordem, sazonal, nome):
    """Ajusta modelo SARIMAX com tratamento de NaN."""
    print(f"\n🔧 {nome}")
    print(f"   Ordem: {ordem}, Sazonal: {sazonal}")
    
    try:
        # Tratamento de NaN - MANTÉM apenas linhas completas
        mask = X.notna().all(axis=1) & y.notna()
        y_clean = y[mask]
        X_clean = X[mask]
        
        print(f"   Dados utilizados: {len(y_clean)} observações")
        
        model = SARIMAX(y_clean, exog=X_clean, order=ordem, seasonal_order=sazonal,
                        enforce_stationarity=False, enforce_invertibility=False)
        result = model.fit(disp=False)
        
        lb = acorr_ljungbox(result.resid, lags=12, return_df=True)
        lb_pval = lb['lb_pvalue'].iloc[-1]
        
        print(f"   ✓ AIC: {result.aic:.2f}")
        print(f"   ✓ Log-Likelihood: {result.llf:.2f}")
        print(f"   ✓ Ljung-Box (lag 12): p={lb_pval:.4f}")
        
        return result, mask
    except Exception as e:
        print(f"   ✗ Erro: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def main():
    """Pipeline principal."""
    print("="*60)
    print("PIPELINE SEFAZ - PREVISÃO ICMS-SP (5 MODELOS)")
    print("="*60)
    
    # 1. Dados
    ibc_df, igp_df, exp = baixar_dados()
    df = preparar_base(ibc_df, igp_df, exp)
    df = carregar_icms(df)
    
    # 2. Preparar dados para modelagem
    train = df[(df['data'] <= '2024-01-01') & df['icms_sp'].notna()].copy()
    y = np.log(train['icms_sp'])
    
    print("\n" + "="*60)
    print("AJUSTE DOS 5 MODELOS SARIMAX")
    print("="*60)
    
    modelos = {}
    mascaras = {}
    
    # Modelo 1: SARIMA(1,1,1) + Dummies
    X1 = train[['dias_uteis', 'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']]
    modelos['Modelo 1'], mascaras['Modelo 1'] = ajustar_modelo(
        y, X1, (1,1,1), (0,0,0,12), 
        "Modelo 1: SARIMA(1,1,1) + Dummies"
    )
    
    # Modelo 2: SARIMAX(3,1,0)(2,0,0) + IGP-DI lag1, IBC-BR lag1
    X2 = train[['igp_di_lag1', 'ibc_br_lag1', 'dias_uteis', 
                'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']]
    modelos['Modelo 2'], mascaras['Modelo 2'] = ajustar_modelo(
        y, X2, (3,1,0), (2,0,0,12),
        "Modelo 2: SARIMAX(3,1,0)(2,0,0) + IGP-DI/IBC-BR lag1"
    )
    
    # Modelo 3: SARIMAX(0,1,1)(0,1,1) + IGP-DI, IBC-BR, IBC-BR lag1
    X3 = train[['igp_di', 'ibc_br', 'ibc_br_lag1', 'dias_uteis',
                'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']]
    modelos['Modelo 3'], mascaras['Modelo 3'] = ajustar_modelo(
        y, X3, (0,1,1), (0,1,1,12),
        "Modelo 3: SARIMAX(0,1,1)(0,1,1) + IGP-DI/IBC-BR"
    )
    
    # Modelo 4: SARIMAX(0,1,1)(0,1,2) + IBC-BR, IBC-BR lag1 (sem inflação)
    X4 = train[['ibc_br', 'ibc_br_lag1', 'dias_uteis',
                'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']]
    modelos['Modelo 4'], mascaras['Modelo 4'] = ajustar_modelo(
        y, X4, (0,1,1), (0,1,2,12),
        "Modelo 4: SARIMAX(0,1,1)(0,1,2) + IBC-BR (sem inflação)"
    )
    
    # Modelo 5: SARIMAX(0,1,1)(0,1,2) + IGP-DI, IBC-BR, IBC-BR lag1 (sem dias úteis)
    X5 = train[['igp_di', 'ibc_br', 'ibc_br_lag1',
                'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']]
    modelos['Modelo 5'], mascaras['Modelo 5'] = ajustar_modelo(
        y, X5, (0,1,1), (0,1,2,12),
        "Modelo 5: SARIMAX(0,1,1)(0,1,2) + IGP-DI/IBC-BR (sem dias úteis)"
    )
    
    # 3. Projeções
    print("\n" + "="*60)
    print("PROJEÇÕES 2024-2026")
    print("="*60)
    
    future = df[df['data'] > '2024-01-01'].copy()
    previsoes = {'data': future['data'].values}
    
    for nome, modelo in modelos.items():
        if modelo is None:
            print(f"   ⚠️ {nome}: pulando (modelo não ajustado)")
            continue
        
        # Preparar X futuro conforme o modelo
        if nome == 'Modelo 1':
            X_fut = future[['dias_uteis', 'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']]
        elif nome == 'Modelo 2':
            X_fut = future[['igp_di_lag1', 'ibc_br_lag1', 'dias_uteis', 
                           'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']]
        elif nome == 'Modelo 3':
            X_fut = future[['igp_di', 'ibc_br', 'ibc_br_lag1', 'dias_uteis',
                           'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']]
        elif nome == 'Modelo 4':
            X_fut = future[['ibc_br', 'ibc_br_lag1', 'dias_uteis',
                           'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']]
        else:  # Modelo 5
            X_fut = future[['igp_di', 'ibc_br', 'ibc_br_lag1',
                           'LS2008NOV', 'TC2020APR04', 'TC2022OUT05']]
        
        # Prever
        forecast = modelo.get_forecast(steps=len(future), exog=X_fut)
        previsoes[nome] = np.exp(forecast.predicted_mean).values
        print(f"   ✓ {nome}: projeção gerada")
    
    prev_df = pd.DataFrame(previsoes)
    
    # Média dos modelos
    col_modelos = [c for c in prev_df.columns if c != 'data' and c.startswith('Modelo')]
    prev_df['Media'] = prev_df[col_modelos].mean(axis=1)
    
    # Totais anuais
    print("\n💰 Totais Anuais (Média dos modelos):")
    for ano in [2024, 2025, 2026]:
        total = prev_df[prev_df['data'].dt.year == ano]['Media'].sum()
        print(f"   {ano}: R$ {total/1e9:.2f} bilhões")
    
    # Salvar resultados detalhados
    print("\n📁 Salvando resultados...")
    
    # Previsões
    prev_df.to_csv('previsoes_todos_modelos.csv', index=False)
    print("   ✓ previsoes_todos_modelos.csv")
    
    # Base
    df.to_csv('base_final.csv', index=False)
    print("   ✓ base_final.csv")
    
    # Métricas dos modelos
    metricas = {}
    for nome, modelo in modelos.items():
        if modelo is not None:
            metricas[nome] = {
                'aic': float(modelo.aic),
                'bic': float(modelo.bic),
                'loglik': float(modelo.llf),
                'observacoes': int(modelo.nobs)
            }
    
    with open('metricas_modelos.json', 'w') as f:
        json.dump(metricas, f, indent=2)
    print("   ✓ metricas_modelos.json")
    
    print("\n" + "="*60)
    print("RESUMO DOS MODELOS")
    print("="*60)
    for nome, modelo in modelos.items():
        if modelo is not None:
            print(f"{nome}: AIC={modelo.aic:.2f}, LogLik={modelo.llf:.2f}")
    
    print("\n" + "="*60)
    print("PIPELINE CONCLUÍDO ✓")
    print("="*60)
    print(f"\n📊 {len([m for m in modelos.values() if m is not None])}/5 modelos ajustados com sucesso")


if __name__ == '__main__':
    main()
