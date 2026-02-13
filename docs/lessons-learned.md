# Lessons Learned - Pipeline SEFAZ ICMS

## 🎯 Overview

Este documento registra aprendizados, padrões e armadilhas identificados durante o desenvolvimento do pipeline de previsão ICMS para SEFAZ-SP.

---

## ✅ Sucessos

### 1. Replicação R → Python com statsmodels
- **Contexto:** Replicar 5 modelos ARIMAX do Rmd original em Python
- **Solução:** `statsmodels.tsa.statespace.sarimax.SARIMAX` com parâmetros equivalentes
- **Resultado:** Modelos idênticos em termos de especificação (AIC comparável)

### 2. Ingestão Automática de Dados
- **APIs integradas:** BCB (SGS), IPEA Data, Focus/BCB
- **Vantagem:** Dados sempre atualizados sem intervenção manual
- **Padrão:** Cache local + fallback para dados baixados

### 3. Relatório PDF Profissional
- **Biblioteca:** FPDF2 (fpdf2 >= 2.7.0)
- **Funcionalidades:** Múltiplas páginas, tabelas, imagens incorporadas
- **Output:** PDF único com toda a análise documentada

---

## ⚠️ Correcções e Workarounds

### 1. Tratamento de NaN em Variáveis Exógenas com Lags

**Problema:**
```python
# Modelos 2-5 falharam com erro:
# "exog contains inf or nans"
```

**Causa raiz:**
- Variáveis exógenas com lags (`ibc_br_lag1`, `igp_di_lag1`) geram NaN nas primeiras 4 observações
- SARIMAX não aceita NaN nas variáveis exógenas

**Solução implementada:**
```python
# Aplicar máscara booleana antes do fit
mask = X.notna().all(axis=1) & y.notna()
y_clean = y[mask]
X_clean = X[mask]

model = SARIMAX(y_clean, exog=X_clean, ...)
```

**Pattern para reutilizar:**
```python
def ajustar_modelo_sarimax(y, X, ordem, sazonal):
    mask = X.notna().all(axis=1) & y.notna()
    model = SARIMAX(y[mask], exog=X[mask], order=ordem, 
                    seasonal_order=sazonal, ...)
    return model.fit(disp=False)
```

### 2. Instabilidade de APIs Externas

**Problema:**
- API BCB retornou `JSONDecodeError` (resposta vazia) durante desenvolvimento
- IPEA Data ocasionalmente lento

**Solução:**
- Salvar dados brutos em CSV (`raw_ibc_br.csv`, `raw_igp_di.csv`)
- Fallback para dados locais quando API falha
- Para produção: implementar retry com exponential backoff

### 3. Encoding no PDF (FPDF2)

**Problema:**
- Caracteres acentuados (ã, õ, ç, ê) causam `UnicodeEncodeError`
- FPDF2 usa latin-1 por padrão para fontes core

**Soluções possíveis:**
1. **Rápida:** Remover acentos no texto (adotado neste projeto)
2. **Robusta:** Usar fonte Unicode (DejavuSans, etc.)

**Implementação rápida:**
```python
# Substituir caracteres acentuados
"confiança" → "confianca"
"média" → "media"
"número" → "numero"
```

---

## 📊 Insights Estatísticos

### 1. Agregação de Modelos

**Cenário:** 5 modelos SARIMAX com previsões diferentes

**Método adotado:**
- Média aritmética das previsões
- IC 95% via distribuição t-Student (n-1 graus de liberdade)

**Fórmula:**
```
IC_95% = Média ± t(0.975, 4) × s/√n

Onde:
- t(0.975, 4) = 2.776 (tabela t-Student)
- s = desvio padrão entre as 5 previsões
- n = 5 (número de modelos)
```

**Justificativa:** Captura incerteza devido à escolha de especificação do modelo

### 2. Comparação de Modelos

| Modelo | AIC | LogLik | Especificação |
|--------|-----|--------|---------------|
| Modelo 1 | -783.65 | 398.83 | SARIMA(1,1,1) + Dummies |
| Modelo 2 | -845.22 | 434.61 | SARIMAX(3,1,0)(2,0,0) + lags |
| Modelo 3 | **-878.56** | **449.28** | SARIMAX(0,1,1)(0,1,1) + variáveis |
| Modelo 4 | -817.33 | 418.66 | SARIMAX(0,1,1)(0,1,2) sem inflação |
| Modelo 5 | -813.13 | 416.57 | SARIMAX(0,1,1)(0,1,2) sem dias úteis |

**Conclusão:** Modelo 3 (mais completo) tem melhor ajuste (menor AIC)

### 3. Estacionariedade

**Teste ADF em log(ICMS):**
- Nível: não estacionário (p = 0.3889)
- 1ª diferença: estacionário (p = 0.0008) ✅

**Implicação:** Diferenciação (d=1) necessária nos modelos

---

## 🔧 Padrões Reutilizáveis

### 1. Estrutura de Pipeline Econométrico

```
pipeline_econometrico/
├── 01_download_dados.py      # Ingestão APIs
├── 02_preparacao_base.py     # Limpeza, lags, dummies
├── 03_modelagem.py           # Ajuste modelos
├── 04_previsoes.py           # Projeções futuras
├── 05_visualizacao.py        # Gráficos
└── 06_relatorio_pdf.py       # Output final
```

### 2. Configuração Seaborn Profissional

```python
import seaborn as sns

sns.set_theme(
    style="whitegrid",
    palette="husl",
    font="sans-serif",
    font_scale=1.1,
    rc={
        'figure.figsize': (14, 8),
        'axes.titlesize': 16,
        'axes.labelsize': 12,
        'axes.spines.top': False,
        'axes.spines.right': False,
    }
)
```

### 3. Tratamento de Timezones (IPEA Data)

```python
# IPEA retorna datetime com timezone
# Extrair apenas a data (string) e converter
df['data'] = pd.to_datetime(df['VALDATA'].str[:10])
```

---

## 🚀 Próximos Passos Sugeridos

### Curto prazo
- [ ] Implementar retry com exponential backoff para APIs
- [ ] Adicionar logs estruturados (logging module)
- [ ] Criar testes unitários para funções core

### Médio prazo
- [ ] GitHub Actions para execução mensal automatizada
- [ ] Alerta por email/Telegram quando novos dados disponíveis
- [ ] Dashboard web (Streamlit/Dash) para visualização interativa

### Longo prazo
- [ ] Implementar auto_arima (pmdarima) para seleção automática de ordem
- [ ] Modelos de Machine Learning (XGBoost, LSTM) para benchmark
- [ ] Backtesting com rolling window para validação robusta

---

## 📚 Referências

- **statsmodels:** https://www.statsmodels.org/stable/tsa.html
- **SARIMAX documentation:** https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.sarimax.SARIMAX.html
- **FPDF2:** https://py-pdf.github.io/fpdf2/
- **BCB API:** https://dadosabertos.bcb.gov.br/
- **IPEA Data:** http://www.ipeadata.gov.br/

---

*Documento criado em: 13/02/2026*
*Última atualização: 13/02/2026*
