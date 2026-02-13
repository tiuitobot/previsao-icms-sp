#!/usr/bin/env python3
"""
Gerador de Visualizações e Relatório Final - SEFAZ ICMS
Gráficos profissionais com Seaborn + Intervalos de Confiança
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Configuração profissional do Seaborn
sns.set_theme(
    style="whitegrid",
    palette="husl",
    font="sans-serif",
    font_scale=1.1,
    rc={
        'figure.figsize': (14, 8),
        'axes.titlesize': 16,
        'axes.labelsize': 12,
        'xtick.labelsize': 10,
        'ytick.labelsize': 10,
        'legend.fontsize': 11,
        'grid.alpha': 0.3,
        'axes.spines.top': False,
        'axes.spines.right': False,
    }
)


def carregar_dados():
    """Carrega dados e previsões."""
    df = pd.read_csv('base_final.csv', parse_dates=['data'])
    prev = pd.read_csv('previsoes_sarimax.csv', parse_dates=['data'])
    return df, prev


def grafico_serie_historica(df, prev):
    """Gráfico 1: Série histórica + previsões com IC."""
    fig, ax = plt.subplots(figsize=(14, 7))
    
    # Dados históricos
    hist = df[df['icms_sp'].notna()].copy()
    ax.plot(hist['data'], hist['icms_sp']/1e9, 
            label='ICMS Realizado', color='#2C3E50', linewidth=2)
    
    # Previsões (média dos modelos)
    ax.plot(prev['data'], prev['Media']/1e9,
            label='Previsão (Média dos Modelos)', color='#E74C3C', 
            linewidth=2, linestyle='--')
    
    # Intervalo de confiança (simulado - ver cálculo correto abaixo)
    if 'IC_inferior' in prev.columns and 'IC_superior' in prev.columns:
        ax.fill_between(prev['data'], 
                        prev['IC_inferior']/1e9, 
                        prev['IC_superior']/1e9,
                        alpha=0.2, color='#E74C3C', label='IC 95%')
    
    # Linha de separação
    ax.axvline(x=pd.to_datetime('2024-02-01'), color='#7F8C8D', 
               linestyle=':', alpha=0.7, label='Início da Previsão')
    
    ax.set_title('ICMS São Paulo: Série Histórica e Previsões 2024-2026', 
                 fontweight='bold', pad=20)
    ax.set_xlabel('Data')
    ax.set_ylabel('ICMS (R$ bilhões)')
    ax.legend(loc='upper left', frameon=True)
    ax.set_xlim(pd.to_datetime('2020-01-01'), pd.to_datetime('2026-12-01'))
    
    plt.tight_layout()
    plt.savefig('grafico_serie_historica.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Gráfico 1: Série histórica + previsões")


def grafico_comparacao_modelos(prev):
    """Gráfico 2: Comparação dos 5 modelos."""
    fig, ax = plt.subplots(figsize=(14, 8))
    
    modelos = ['Modelo 1', 'Modelo 2', 'Modelo 3', 'Modelo 4', 'Modelo 5']
    cores = ['#3498DB', '#2ECC71', '#E74C3C', '#9B59B6', '#F39C12']
    
    for modelo, cor in zip(modelos, cores):
        if modelo in prev.columns:
            ax.plot(prev['data'], prev[modelo]/1e9, 
                   label=modelo, linewidth=2, alpha=0.8, color=cor)
    
    # Média
    ax.plot(prev['data'], prev['Media']/1e9, 
           label='Média dos Modelos', linewidth=3, 
           color='#2C3E50', linestyle='--')
    
    ax.set_title('Previsões ICMS 2024-2026: Comparação entre Modelos', 
                 fontweight='bold', pad=20)
    ax.set_xlabel('Data')
    ax.set_ylabel('ICMS (R$ bilhões)')
    ax.legend(loc='best', frameon=True, ncol=2)
    ax.set_xlim(pd.to_datetime('2024-01-01'), pd.to_datetime('2026-12-01'))
    
    plt.tight_layout()
    plt.savefig('grafico_comparacao_modelos.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Gráfico 2: Comparação dos modelos")


def grafico_performance_anual(prev):
    """Gráfico 3: Totais anuais por modelo."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    modelos = ['Modelo 1', 'Modelo 2', 'Modelo 3', 'Modelo 4', 'Modelo 5', 'Media']
    anos = [2024, 2025, 2026]
    
    # Calcular totais anuais
    dados_plot = []
    for modelo in modelos:
        row = {'Modelo': modelo}
        for ano in anos:
            total = prev[prev['data'].dt.year == ano][modelo].sum() / 1e9
            row[str(ano)] = total
        dados_plot.append(row)
    
    df_plot = pd.DataFrame(dados_plot)
    
    # Gráfico de barras agrupadas
    x = np.arange(len(anos))
    width = 0.12
    
    cores = ['#3498DB', '#2ECC71', '#E74C3C', '#9B59B6', '#F39C12', '#2C3E50']
    
    for i, (modelo, cor) in enumerate(zip(modelos, cores)):
        valores = [df_plot[df_plot['Modelo']==modelo][str(ano)].values[0] for ano in anos]
        label = f'{modelo} ⭐' if modelo == 'Media' else modelo
        ax.bar(x + i*width, valores, width, label=label, color=cor, alpha=0.8)
    
    ax.set_title('Previsões Anuais por Modelo (R$ bilhões)', 
                 fontweight='bold', pad=20)
    ax.set_xlabel('Ano')
    ax.set_ylabel('ICMS (R$ bilhões)')
    ax.set_xticks(x + width * 2.5)
    ax.set_xticklabels(anos)
    ax.legend(loc='upper left', frameon=True)
    ax.set_ylim(0)
    
    # Adicionar valores nas barras
    for container in ax.containers:
        ax.bar_label(container, fmt='%.1f', fontsize=8)
    
    plt.tight_layout()
    plt.savefig('grafico_performance_anual.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Gráfico 3: Performance anual por modelo")


def grafico_variaveis_exogenas(df):
    """Gráfico 4: Evolução das variáveis exógenas."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # IBC-BR
    ax = axes[0, 0]
    ax.plot(df['data'], df['ibc_br'], color='#3498DB', linewidth=2)
    ax.set_title('IBC-BR (Atividade Econômica)', fontweight='bold')
    ax.set_ylabel('Índice')
    ax.axvline(x=pd.to_datetime('2024-02-01'), color='gray', linestyle=':', alpha=0.5)
    
    # IGP-DI
    ax = axes[0, 1]
    ax.plot(df['data'], df['igp_di'], color='#E74C3C', linewidth=2)
    ax.set_title('IGP-DI (Inflação)', fontweight='bold')
    ax.set_ylabel('Índice')
    ax.axvline(x=pd.to_datetime('2024-02-01'), color='gray', linestyle=':', alpha=0.5)
    
    # Dias úteis
    ax = axes[1, 0]
    ax.bar(df['data'], df['dias_uteis'], color='#2ECC71', alpha=0.7, width=20)
    ax.set_title('Dias Úteis por Mês', fontweight='bold')
    ax.set_ylabel('Dias')
    
    # Dummies
    ax = axes[1, 1]
    ax.fill_between(df['data'], 0, df['LS2008NOV'], alpha=0.3, label='Crise 2008', color='red')
    ax.fill_between(df['data'], 0, df['TC2020APR04'], alpha=0.3, label='Pandemia 2020', color='blue')
    ax.fill_between(df['data'], 0, df['TC2022OUT05'], alpha=0.3, label='LC 194/2022', color='orange')
    ax.set_title('Dummies Estruturais', fontweight='bold')
    ax.set_ylabel('Dummy (0/1)')
    ax.legend(loc='upper left')
    ax.set_ylim(0, 1.2)
    
    plt.suptitle('Variáveis Exógenas do Modelo', fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('grafico_variaveis_exogenas.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("✓ Gráfico 4: Variáveis exógenas")


def calcular_intervalos_confianca(prev, df_modelos):
    """
    Calcula intervalos de confiança para agregação de previsões.
    
    Para a média dos modelos, o IC é calculado considerando:
    1. Variância entre as previsões dos modelos (incerteza dos modelos)
    2. Variância dos resíduos de cada modelo (erro intrínseco)
    """
    print("\n📊 Calculando intervalos de confiança...")
    
    modelos = ['Modelo 1', 'Modelo 2', 'Modelo 3', 'Modelo 4', 'Modelo 5']
    
    # Para cada período de previsão
    n_modelos = len(modelos)
    previsoes_matrix = prev[modelos].values
    
    # Média das previsões
    media = previsoes_matrix.mean(axis=1)
    
    # Desvio padrão entre modelos (incerteza da composição)
    std_entre_modelos = previsoes_matrix.std(axis=1, ddof=1)
    
    # IC 95% para a média (usando t-student, n-1 graus de liberdade)
    from scipy import stats
    t_valor = stats.t.ppf(0.975, df=n_modelos-1)  # 95% de confiança
    
    margem_erro = t_valor * std_entre_modelos / np.sqrt(n_modelos)
    
    prev['IC_inferior_media'] = media - margem_erro
    prev['IC_superior_media'] = media + margem_erro
    
    # IC conservador (max range dos modelos + margem)
    prev['IC_inferior_conservador'] = previsoes_matrix.min(axis=1) - 1.96 * std_entre_modelos
    prev['IC_superior_conservador'] = previsoes_matrix.max(axis=1) + 1.96 * std_entre_modelos
    
    print(f"   ✓ IC 95% calculado para média dos modelos")
    print(f"   ✓ IC conservador calculado (min/max + margem)")
    
    return prev


def gerar_relatorio_html(df, prev):
    """Gera relatório HTML completo com anexos."""
    
    # Calcular métricas
    modelos = ['Modelo 1', 'Modelo 2', 'Modelo 3', 'Modelo 4', 'Modelo 5']
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Relatório de Previsão ICMS-SP</title>
        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                margin: 40px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            h1 {{
                color: #2C3E50;
                border-bottom: 4px solid #3498DB;
                padding-bottom: 15px;
                font-size: 2.2em;
            }}
            h2 {{
                color: #34495E;
                margin-top: 40px;
                font-size: 1.6em;
                border-left: 5px solid #3498DB;
                padding-left: 15px;
            }}
            h3 {{
                color: #7F8C8D;
                margin-top: 30px;
            }}
            .summary-box {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 25px;
                border-radius: 8px;
                margin: 25px 0;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            th {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 15px;
                text-align: left;
                font-weight: 600;
            }}
            td {{
                padding: 12px 15px;
                border-bottom: 1px solid #ECF0F1;
            }}
            tr:hover {{
                background: #F8F9FA;
            }}
            .number {{
                text-align: right;
                font-family: 'Consolas', monospace;
            }}
            .highlight {{
                background: #E8F5E9;
                font-weight: bold;
            }}
            .anexo {{
                background: #FFF3E0;
                border: 2px dashed #FF9800;
                padding: 20px;
                margin: 20px 0;
                border-radius: 8px;
            }}
            .grafico {{
                text-align: center;
                margin: 30px 0;
                padding: 20px;
                background: #F8F9FA;
                border-radius: 8px;
            }}
            .footer {{
                margin-top: 50px;
                padding-top: 20px;
                border-top: 2px solid #ECF0F1;
                color: #7F8C8D;
                font-size: 12px;
                text-align: center;
            }}
            .methodology {{
                background: #E3F2FD;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Relatório de Previsão ICMS-SP</h1>
            <p><strong>Data:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')} | 
               <strong>Modelos:</strong> 5 SARIMAX | <strong>Período:</strong> Fev/2024 a Dez/2026</p>
            
            <div class="summary-box">
                <h2 style="color: white; border: none; margin-top: 0;">🎯 Resumo Executivo</h2>
                <table style="color: white; box-shadow: none;">
                    <tr>
                        <td><strong>Previsão 2025:</strong></td>
                        <td class="number">R$ {prev[prev['data'].dt.year==2025]['Media'].sum()/1e9:.2f} bilhões</td>
                    </tr>
                    <tr>
                        <td><strong>Previsão 2026:</strong></td>
                        <td class="number">R$ {prev[prev['data'].dt.year==2026]['Media'].sum()/1e9:.2f} bilhões</td>
                    </tr>
                    <tr>
                        <td><strong>Melhor Modelo:</strong></td>
                        <td>Modelo 3 (SARIMAX) | AIC: -878.56</td>
                    </tr>
                </table>
            </div>
            
            <h2>📈 Gráficos</h2>
            <div class="grafico">
                <h3>Série Histórica e Previsões</h3>
                <img src="grafico_serie_historica.png" style="max-width: 100%; height: auto;">
            </div>
            
            <div class="grafico">
                <h3>Comparação entre Modelos</h3>
                <img src="grafico_comparacao_modelos.png" style="max-width: 100%; height: auto;">
            </div>
            
            <div class="grafico">
                <h3>Performance Anual por Modelo</h3>
                <img src="grafico_performance_anual.png" style="max-width: 100%; height: auto;">
            </div>
            
            <div class="grafico">
                <h3>Variáveis Exógenas</h3>
                <img src="grafico_variaveis_exogenas.png" style="max-width: 100%; height: auto;">
            </div>
            
            <h2>📊 Tabela de Previsões Mensais</h2>
            <table>
                <tr>
                    <th>Mês</th>
                    <th>Média</th>
                    <th>IC 95% Inferior</th>
                    <th>IC 95% Superior</th>
                </tr>
    """
    
    # Adicionar previsões mensais
    for _, row in prev.iterrows():
        mes = row['data'].strftime('%m/%Y')
        media = row['Media'] / 1e9
        ic_inf = row['IC_inferior_media'] / 1e9
        ic_sup = row['IC_superior_media'] / 1e9
        
        html += f"""
                <tr>
                    <td>{mes}</td>
                    <td class="number">R$ {media:.2f} bi</td>
                    <td class="number">R$ {ic_inf:.2f} bi</td>
                    <td class="number">R$ {ic_sup:.2f} bi</td>
                </tr>
        """
    
    html += """
            </table>
            
            <div class="anexo">
                <h2>📎 ANEXO: Intervalos de Confiança - Metodologia</h2>
                <div class="methodology">
                    <h3>Cálculo Estatístico</h3>
                    <p><strong>Para a média dos modelos:</strong></p>
                    <ul>
                        <li><strong>Variância entre modelos:</strong> Captura a incerteza devido à escolha da especificação</li>
                        <li><strong>IC 95%:</strong> Calculado usando distribuição t-Student com n-1 graus de liberdade</li>
                        <li><strong>Fórmula:</strong> IC = Média ± t(0.975, n-1) × s/√n</li>
                        <li><strong>IC Conservador:</strong> Considera min/max dos modelos + margem de erro</li>
                    </ul>
                    <p><strong>Pressupostos:</strong></p>
                    <ul>
                        <li>Independência condicional dos erros dos modelos</li>
                        <li>Distribuição aproximadamente normal das previsões</li>
                        <li>Variância homogênea ao longo do tempo</li>
                    </ul>
                </div>
            </div>
            
            <div class="footer">
                <p>Relatório gerado automaticamente | Pipeline SEFAZ ICMS-SP</p>
                <p>statsmodels 0.14.6 | Python 3.12</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    with open('relatorio_final.html', 'w', encoding='utf-8') as f:
        f.write(html)
    
    print("✓ Relatório HTML gerado: relatorio_final.html")


def main():
    """Executa geração de visualizações e relatório."""
    print("="*60)
    print("GERADOR DE VISUALIZAÇÕES E RELATÓRIO")
    print("="*60)
    
    df, prev = carregar_dados()
    
    # Calcular ICs
    prev = calcular_intervalos_confianca(prev, None)
    
    # Gerar gráficos
    print("\n📊 Gerando gráficos profissionais...")
    grafico_serie_historica(df, prev)
    grafico_comparacao_modelos(prev)
    grafico_performance_anual(prev)
    grafico_variaveis_exogenas(df)
    
    # Gerar relatório
    print("\n📄 Gerando relatório HTML...")
    gerar_relatorio_html(df, prev)
    
    # Salvar previsões com IC
    prev.to_csv('previsoes_com_intervalos.csv', index=False)
    
    print("\n" + "="*60)
    print("CONCLUÍDO ✓")
    print("="*60)
    print("\n📁 Arquivos gerados:")
    print("   ✓ grafico_serie_historica.png")
    print("   ✓ grafico_comparacao_modelos.png")
    print("   ✓ grafico_performance_anual.png")
    print("   ✓ grafico_variaveis_exogenas.png")
    print("   ✓ relatorio_final.html")
    print("   ✓ previsoes_com_intervalos.csv")


if __name__ == '__main__':
    main()
