# Previsão ICMS-SP

Pipeline automatizado de previsão de arrecadação ICMS para São Paulo.

## 📊 Resultados Preliminares

| Ano | Previsão ICMS |
|-----|---------------|
| 2024 | R$ 225,91 bilhões |
| 2025 | R$ 280,12 bilhões |
| 2026 | R$ 278,95 bilhões |

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/tiuitobot/previsao-icms-sp.git
cd previsao-icms-sp
```

### 2. Crie o ambiente virtual

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\\Scripts\\activate     # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

**Principais pacotes:**
- `statsmodels 0.14.6` — ARIMA, ARIMAX, testes econométricos ⭐
- `pandas 3.0.0` — Manipulação de dados
- `scikit-learn 1.8.0` — Métricas e ML
- `openpyxl 3.1.5` — Leitura de Excel

## 📁 Estrutura

```
previsao-icms-sp/
├── README.md                    # Este arquivo
├── requirements.txt             # Dependências Python
├── pipeline.py                  # Script principal
├── dados_sefaz.xlsx             # Dados SEFAZ
├── previsoes_icms_2024_2026.csv # Previsões detalhadas
└── relatorio_previsao_icms.html # Relatório HTML
```

## 🔧 Uso

```bash
source venv/bin/activate
python pipeline.py
```

## 📊 Metodologia

### Fontes de Dados

| Variável | Fonte |
|----------|-------|
| ICMS_SP | SEFAZ (interno) |
| IBC-BR | BCB (API SGS) |
| IGP-DI | IPEA Data |
| Expectativas | Focus/BCB |

### Modelo

- **Especificação:** ARX(1) — AutoRegressivo com variáveis exógenas
- **Variável dependente:** log(ICMS_SP)
- **MAPE:** 3,67%
- **R²:** 0,9900

## ⚠️ Limitações

1. ICMS_SP só até jan/2024
2. Modelo simplificado (ARX vs ARIMAX completo)
3. Projeções baseadas em expectativas de mercado

## 🔮 Próximos Passos

- [ ] Implementar SARIMAX completo com `statsmodels`
- [ ] Replicar os 5 modelos do Rmd original
- [ ] Testes de estacionariedade (ADF, KPSS)
- [ ] Diagnósticos de resíduos (Ljung-Box)

---
*Projeto SEFAZ-SP — 13/02/2026*
