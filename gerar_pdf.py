#!/usr/bin/env python3
"""
Gerador de Relatório PDF - SEFAZ ICMS
"""

from fpdf import FPDF
import pandas as pd
import numpy as np
import json
from datetime import datetime


class PDFRelatorio(FPDF):
    def header(self):
        # Logo ou título
        self.set_font('Arial', 'B', 12)
        self.set_text_color(44, 62, 80)  # #2C3E50
        self.cell(0, 10, 'SEFAZ-SP - Previsão de Arrecadação ICMS', 0, 1, 'C')
        self.ln(2)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')


def gerar_relatorio_pdf():
    """Gera relatório PDF completo."""
    
    # Carregar dados
    prev = pd.read_csv('previsoes_todos_modelos.csv', parse_dates=['data'])
    with open('metricas_modelos.json') as f:
        metricas = json.load(f)
    
    pdf = PDFRelatorio()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Título principal
    pdf.set_font('Arial', 'B', 20)
    pdf.set_text_color(44, 62, 80)
    pdf.cell(0, 15, 'Relatório de Previsão ICMS-SP', 0, 1, 'C')
    
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, f'Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
    pdf.ln(10)
    
    # Resumo Executivo
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(52, 152, 219)  # #3498DB
    pdf.cell(0, 10, '1. Resumo Executivo', 0, 1)
    pdf.ln(2)
    
    pdf.set_font('Arial', '', 11)
    pdf.set_text_color(0, 0, 0)
    
    # Totais anuais
    for ano in [2024, 2025, 2026]:
        total = prev[prev['data'].dt.year == ano]['Media'].sum() / 1e9
        pdf.cell(50, 8, f'Previsão {ano}:', 0, 0)
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, f'R$ {total:.2f} bilhões', 0, 1)
        pdf.set_font('Arial', '', 11)
    
    pdf.ln(5)
    
    # Melhor modelo
    melhor = min(metricas.items(), key=lambda x: x[1]['aic'])
    pdf.cell(0, 8, f'Melhor modelo: {melhor[0]} (AIC = {melhor[1]["aic"]:.2f})', 0, 1)
    pdf.ln(10)
    
    # Métricas dos Modelos
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(52, 152, 219)
    pdf.cell(0, 10, '2. Métricas dos Modelos', 0, 1)
    pdf.ln(2)
    
    # Tabela de métricas
    pdf.set_fill_color(52, 152, 219)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 10)
    
    col_widths = [40, 30, 35, 35]
    headers = ['Modelo', 'AIC', 'Log-Likelihood', 'Observações']
    
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, h, 1, 0, 'C', True)
    pdf.ln()
    
    # Dados
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 10)
    
    for nome, met in metricas.items():
        pdf.cell(col_widths[0], 8, nome, 1, 0, 'L')
        pdf.cell(col_widths[1], 8, f"{met['aic']:.2f}", 1, 0, 'R')
        pdf.cell(col_widths[2], 8, f"{met['loglik']:.2f}", 1, 0, 'R')
        pdf.cell(col_widths[3], 8, str(met.get('observacoes', 252)), 1, 0, 'R')
        pdf.ln()
    
    pdf.ln(10)
    
    # Previsões Mensais
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(52, 152, 219)
    pdf.cell(0, 10, '3. Previsões Mensais 2025', 0, 1)
    pdf.ln(2)
    
    # Cabeçalho
    pdf.set_fill_color(52, 152, 219)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 9)
    
    col_widths = [25, 30, 30, 30, 30, 30]
    headers = ['Mês', 'Mod 1', 'Mod 2', 'Mod 3', 'Mod 4', 'Média']
    
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, 1, 0, 'C', True)
    pdf.ln()
    
    # Dados 2025
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', '', 8)
    
    prev_2025 = prev[prev['data'].dt.year == 2025].head(12)
    for _, row in prev_2025.iterrows():
        pdf.cell(col_widths[0], 6, row['data'].strftime('%m/%Y'), 1, 0, 'C')
        pdf.cell(col_widths[1], 6, f"{row['Modelo 1']/1e9:.2f}", 1, 0, 'R')
        pdf.cell(col_widths[2], 6, f"{row['Modelo 2']/1e9:.2f}", 1, 0, 'R')
        pdf.cell(col_widths[3], 6, f"{row['Modelo 3']/1e9:.2f}", 1, 0, 'R')
        pdf.cell(col_widths[4], 6, f"{row['Modelo 4']/1e9:.2f}", 1, 0, 'R')
        pdf.set_font('Arial', 'B', 8)
        pdf.cell(col_widths[5], 6, f"{row['Media']/1e9:.2f}", 1, 0, 'R')
        pdf.set_font('Arial', '', 8)
        pdf.ln()
    
    pdf.ln(10)
    
    # Gráficos
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(52, 152, 219)
    pdf.cell(0, 10, '4. Gráficos', 0, 1)
    pdf.ln(2)
    
    # Gráfico 1: Série histórica
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, 'Série Histórica e Previsões 2024-2026', 0, 1)
    pdf.image('grafico_serie_historica.png', x=10, y=None, w=190)
    pdf.ln(5)
    
    # Nova página para gráfico 2
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Comparação entre os 5 Modelos SARIMAX', 0, 1)
    pdf.image('grafico_comparacao_modelos.png', x=10, y=None, w=190)
    pdf.ln(5)
    
    # Nova página para gráfico 3
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Performance Anual por Modelo', 0, 1)
    pdf.image('grafico_performance_anual.png', x=10, y=None, w=190)
    pdf.ln(5)
    
    # Nova página para variáveis exógenas
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, 'Variáveis Exógenas do Modelo', 0, 1)
    pdf.image('grafico_variaveis_exogenas.png', x=10, y=None, w=190)
    pdf.ln(5)
    
    # Metodologia
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(52, 152, 219)
    pdf.cell(0, 10, '5. Metodologia', 0, 1)
    pdf.ln(2)
    
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(0, 0, 0)
    
    metodologia = [
        "Modelos: 5 especificações SARIMAX (replicando R)",
        "Variável dependente: log(ICMS_SP)",
        "Variáveis exógenas: IBC-BR, IGP-DI, dias úteis, dummies",
        "Período de treino: Jan/2003 a Jan/2024 (253 meses)",
        "Projeções: Fev/2024 a Dez/2026",
        "",
        "Fontes de dados:",
        "  - ICMS_SP: Sistema interno SEFAZ",
        "  - IBC-BR: Banco Central (API SGS)",
        "  - IGP-DI: IPEA Data",
        "  - Expectativas: Focus/BCB (PIB 1.8%, IGP-M 3.9% para 2026)"
    ]
    
    for linha in metodologia:
        pdf.cell(0, 6, linha, 0, 1)
    
    pdf.ln(10)
    
    # Intervalos de Confiança
    pdf.set_font('Arial', 'B', 14)
    pdf.set_text_color(52, 152, 219)
    pdf.cell(0, 10, '6. Intervalos de Confiança', 0, 1)
    pdf.ln(2)
    
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 6, 
        "Os intervalos de confianca foram calculados via Simulacao de Monte Carlo "
        "(1.000 caminhos por modelo). Para o agregado anual, somamos as trajetorias "
        "simuladas path-a-path antes de calcular os quantis, preservando a estrutura "
        "de correlacao temporal (AR/MA) e entre modelos.\n\n"
        "IC 95% = Quantis 2.5% e 97.5% da distribuicao agregada simulada.\n\n"
        "Este metodo captura tanto a incerteza dos parametros quanto a incerteza do modelo "
        "e a dependencia temporal."
    )
    
    # Salvar
    pdf.output('relatorio_previsao_icms.pdf')
    print("✓ Relatório PDF gerado: relatorio_previsao_icms.pdf")


if __name__ == '__main__':
    gerar_relatorio_pdf()
