# Auditoria Comparativa: Pipeline R/Excel vs Python/Kimi

**Data:** 2026-02-13  
**Auditor:** Tiuito (Claude Opus 4.6)  
**Fontes:** `modelo_previsao_29_10.Rmd`, planilhas Excel (Variáveis, Trajetória PIB/Inflação, ICMS), `pipeline.py`

---

## 1. Tabela Comparativa Etapa-por-Etapa

| # | Etapa | R (Original) | Python (Kimi) | Status |
|---|-------|-------------|---------------|--------|
| 1 | **Fonte de dados — ICMS** | Lê de `Variaveis_para_Previsão_29_10.xlsx` col `icms_sp` (276 meses, jan/2003–dez/2025) | Tenta ler `dados_sefaz.xlsx` (253 meses, até jan/2024); em paralelo **baixa IBC-BR e IGP-DI de APIs** mas NÃO baixa ICMS | 🔴 CRÍTICO |
| 2 | **Fonte de dados — IBC-BR** | Pré-processado na planilha Excel com projeções sazonais (Focus via Trajetória PIB) | Baixa da API BCB (SGS 24363) — dados só até último realizado (~nov/2025) | 🟡 DIFERENTE |
| 3 | **Fonte de dados — IGP-DI** | Pré-processado na planilha Excel com projeções mensais (Focus via Trajetória IGP-DI) | Baixa da API IPEA — dados só até último realizado | 🟡 DIFERENTE |
| 4 | **Projeção IBC-BR futuro** | Distribuição mensal sazonal: Focus trimestral → participação mensal intra-trimestre (ARIMA ou histórico) → valores mensais que respeitam sazonalidade | Crescimento composto uniforme: `(1 + PIB_anual)^(1/12) - 1` aplicado linearmente | 🔴 CRÍTICO |
| 5 | **Projeção IGP-DI futuro** | Focus mensal (cada mês tem expectativa própria: 0.43%, 0.50%, 0.49%...) com ajuste para variação anual coincidir | Crescimento composto uniforme: `(1 + IGP-M_anual)^(1/11) - 1` | 🔴 CRÍTICO |
| 6 | **Variável dólar** | Presente na planilha (`dolar`) mas comentada no R (não usada nos modelos) | Não existe no pipeline | ✅ OK |
| 7 | **Dias úteis** | Da planilha Excel (valores pré-calculados para todo o período) | Calculados algoritmicamente (`weekday < 5`), sem considerar feriados | 🟡 DIFERENTE |
| 8 | **Lags criados** | Lag 1–4 para IBC-BR, IGP-DI e dias_uteis via `stats::lag(k=-1...-4)` | Lag 1–4 via `df.shift(lag)` — mesma lógica | ✅ OK |
| 9 | **Dummy LS2008NOV** | `1` de nov/2008 até o final da série | `1` se (ano==2008 e mês≥11) ou (ano>2008) | ✅ OK |
| 10 | **Dummy TC2020APR04** | `1` de abr/2020 a jul/2020 | `1` se ano==2020 e 4≤mês≤7 | ✅ OK |
| 11 | **Dummy TC2022OUT05** | `1` de out/2022 a mai/2023 | `1` se (ano==2022 e mês≥10) ou (ano==2023 e mês≤5) | ✅ OK |
| 12 | **Transformação log** | `lambda = 0` no Arima (= log-transform automático do forecast) | `np.log(train['icms_sp'])` manual | ✅ EQUIVALENTE |
| 13 | **Cutoff de treino** | `training_date2 = c(2025, 10)` — treina até out/2025 | `df['data'] <= '2024-01-01'` — treina até jan/2024 | 🔴 CRÍTICO |
| 14 | **Modelo 1** | `auto.arima()` com xreg=[dias_uteis, dummies], lambda=0. Ordem selecionada automaticamente | SARIMA(1,1,1)(0,0,0,12) fixo. Sem componente sazonal ARIMA | 🔴 CRÍTICO |
| 15 | **Modelo 2** | ARIMA(3,1,0)(2,0,0)[12] com xreg=[IGP-DI lag1, dias_uteis, IBC-BR lag1, dummies] | SARIMAX(3,1,0)(2,0,0,12) com mesmas exógenas | ✅ OK |
| 16 | **Modelo 3** | ARIMA(0,1,1)(0,1,1)[12] com xreg=[IGP-DI, IBC-BR lag1, IBC-BR, dias_uteis, dummies] | SARIMAX(0,1,1)(0,1,1,12) com mesmas exógenas | ✅ OK |
| 17 | **Modelo 4** | ARIMA(0,1,1)(0,1,2)[12] com xreg=[IBC-BR lag1, IBC-BR, dias_uteis, dummies] (sem inflação) | SARIMAX(0,1,1)(0,1,2,12) com mesmas exógenas | ✅ OK |
| 18 | **Modelo 5** | ARIMA(0,1,1)(0,1,2)[12] com xreg=[IGP-DI, IBC-BR lag1, IBC-BR, dummies] (sem dias_uteis) | SARIMAX(0,1,1)(0,1,2,12) com mesmas exógenas | ✅ OK |
| 19 | **Estimação** | ML (`method = "ML"`) com `include.mean = TRUE` | MLE padrão do statsmodels (equivalente) | ✅ OK |
| 20 | **Diagnósticos** | Ljung-Box (lag 24 ou 36), ACF/PACF, raízes do polinômio, coeftest (erros robustos HAC) | Ljung-Box (lag 12 apenas), ADF. Sem raízes, sem erros robustos | 🟡 MENOR |
| 21 | **Acurácia fora da amostra** | `forecast::accuracy()` com MAPE em training e test set | Não calculada | 🟡 FALTANDO |
| 22 | **Combinação de modelos** | Média aritmética simples dos 5 modelos (pesos = 1/5) | Média aritmética simples — mesmo método | ✅ OK |
| 23 | **Intervalos de confiança** | 50%, 75% e 95% por modelo → média ponderada dos ICs | Não calculados (apenas previsão pontual) | 🟡 FALTANDO |
| 24 | **Horizonte de previsão** | Nov/2025 a Dez/2026 (14 meses a partir do cutoff out/2025) | Fev/2024 a Dez/2026 (35 meses a partir do cutoff jan/2024) | 🔴 CRÍTICO |
| 25 | **Output** | Excel com previsões mensais + ICs, gráficos ggplot2 | CSV + JSON métricas + PDF com gráficos seaborn | ✅ OK (diferente formato) |

---

## 2. Ajustes Implícitos nas Planilhas que o Python NÃO Captura

### 2.1 🔴 Distribuição Mensal Sazonal do IBC-BR (proxy PIB)

A planilha `Trajetória PIB e Inflação_260105.xlsx` (aba PIB) contém um processo sofisticado de 5 etapas:

1. **Obtém variação trimestral** do Focus/BCB para o ano projetado
2. **Obtém variação anual** do Focus
3. **Aplica variações trimestrais** aos primeiros 3 trimestres
4. **Calcula o 4º trimestre** como resíduo para que o total anual bata com a expectativa Focus
5. **Distribui os trimestres em meses** usando participação intra-trimestre baseada em ARIMA ou histórico

**Resultado:** IBC-BR 2026 na planilha tem sazonalidade (varia de 104.8 a 116.6), refletindo o padrão mensal histórico. O Python gera uma tendência monotônica (107.0 a 108.8 na `dados_sefaz.xlsx`) ou com crescimento composto uniforme.

**Impacto:** Os modelos 2–5 usam IBC-BR como exógena. Com projeção plana, as previsões perdem sazonalidade na contribuição da atividade econômica.

### 2.2 🔴 Projeção Mensal do IGP-DI com Expectativas Focus Mensais

A planilha (aba IGP-DI) usa **expectativas Focus mensais individuais** (ex: jan=0.43%, fev=0.50%, mar=0.49%, abr=0.39%...) com ajuste final para garantir que a variação anual coincida com a expectativa Focus anual.

O Python usa uma taxa mensal uniforme derivada da expectativa anual: `(1 + 3.9457%)^(1/11) - 1 ≈ 0.32%/mês` para todos os meses.

**Impacto numérico verificado:** Para 2026, a diferença entre as projeções IGP-DI da planilha R vs `dados_sefaz.xlsx` é de ~3 a 6 pontos do índice. Isso afeta modelos 2, 3 e 5.

### 2.3 🔴 Dados ICMS mais recentes na planilha

A planilha `Variaveis_para_Previsão_260105.xlsx` contém ICMS até dez/2025 (276 meses), enquanto `dados_sefaz.xlsx` (usada pelo Python) só vai até jan/2024 (253 meses). São **23 meses a mais** de dados observados que o R usa para treinar.

### 2.4 🟡 Dias Úteis com Feriados

A planilha tem dias úteis pré-calculados que provavelmente incluem feriados nacionais e estaduais (SP). O Python calcula dias úteis contando apenas seg-sex, sem feriados. Diferença típica: 1–2 dias/mês.

### 2.5 🟡 Indicador Focus: PIB vs IGP-M vs IGP-DI

O R usa projeções Focus de **PIB** (para IBC-BR) e **IGP-DI** (para inflação). O Python busca Focus de **PIB** e **IGP-M** (não IGP-DI). São indicadores diferentes — IGP-M e IGP-DI têm períodos de coleta e ponderações distintos.

---

## 3. Gaps Críticos (O Que Falta no Python)

| Prioridade | Gap | Impacto |
|-----------|-----|---------|
| 🔴 P0 | **Cutoff de treino em jan/2024** em vez de out/2025 — perde 22 meses de dados | Modelos treinados com informação defasada; previsões desatualizadas |
| 🔴 P0 | **Projeção IBC-BR sem sazonalidade** — crescimento uniforme vs distribuição mensal sazonal | Modelos perdem sazonalidade na exógena principal; previsões mensais incorretas |
| 🔴 P0 | **Projeção IGP-DI sem variação mensal Focus** — taxa uniforme vs expectativas mensais | Menor impacto que IBC-BR, mas ainda distorce a dinâmica inflacionária |
| 🔴 P0 | **Modelo 1: auto.arima substituído por SARIMA fixo (1,1,1)(0,0,0,12)** | auto.arima pode selecionar ordem completamente diferente; sem componente sazonal AR/MA no Python |
| 🟡 P1 | **ICMS carregado de `dados_sefaz.xlsx`** (versão desatualizada) em vez da planilha principal | Dados observados mais recentes ausentes |
| 🟡 P1 | **Sem intervalos de confiança** (50%, 75%, 95%) | R produz bandas de IC para a média combinada; Python só produz previsão pontual |
| 🟡 P1 | **Sem acurácia fora da amostra (MAPE)** | R calcula MAPE por modelo; Python não mede qualidade preditiva |
| 🟡 P2 | **Dias úteis sem feriados** | Diferença pequena mas sistemática |
| 🟡 P2 | **Focus busca IGP-M em vez de IGP-DI** | Indicador errado para a projeção de inflação |
| 🟢 P3 | **Diagnósticos reduzidos** (Ljung-Box lag 12 vs 24/36; sem raízes; sem erros robustos HAC) | Não afeta previsão, mas reduz validação |

---

## 4. O Que o Python Faz Diferente (Melhor ou Pior)

### ✅ Melhor no Python
- **Reprodutibilidade:** APIs automatizam download de dados (IBC-BR, IGP-DI) — elimina trabalho manual
- **Relatório PDF:** Geração automática de relatório formatado com gráficos
- **Estrutura de código:** Pipeline linear, fácil de auditar e modificar
- **Versionamento:** Repo Git com histórico de mudanças

### ❌ Pior no Python
- **Perda total da calibração de projeções** — o trabalho mais sofisticado do pipeline R (distribuição mensal Focus) não foi reimplementado
- **Cutoff errado** — resultado final é baseado em dados 22 meses mais antigos
- **auto.arima removido** — seleção automática de ordem é feature central do Modelo 1
- **Sem ICs** — o R produz intervalos de confiança combinados; Python só previsão pontual
- **Sem validação** — MAPE e diagnósticos completos ausentes

### ⚠️ Diferente (neutro)
- **Biblioteca:** R `forecast` vs Python `statsmodels` — implementações diferentes do SARIMAX, podem ter diferenças numéricas na estimação ML
- **Formato de output:** Excel vs CSV/JSON — questão de preferência
- **Gráficos:** ggplot2 vs seaborn — ambos adequados

---

## 5. Recomendações Priorizadas

### P0 — Correções Bloqueantes (sem estas, pipeline Python é inutilizável)

1. **Atualizar cutoff de treino** para usar todos os dados ICMS disponíveis (ler da planilha atualizada, não de `dados_sefaz.xlsx` defasado)

2. **Reimplementar distribuição mensal sazonal do IBC-BR:**
   - Opção A (fiel ao R): Replicar o processo da aba PIB — Focus trimestral → participação mensal intra-trimestre → distribuição sazonal
   - Opção B (simplificada): Usar padrão sazonal do último ano observado como template para aplicar sobre o crescimento Focus anual

3. **Reimplementar projeção IGP-DI com variações mensais Focus:**
   - Buscar expectativas Focus mensais (não apenas anuais) via API BCB
   - Aplicar ajuste final para bater com expectativa anual

4. **Modelo 1: usar `pmdarima.auto_arima()`** em vez de ordem fixa (1,1,1)(0,0,0,12)

### P1 — Melhorias Importantes

5. **Adicionar intervalos de confiança** (50%, 75%, 95%) à previsão combinada

6. **Calcular MAPE** dentro e fora da amostra por modelo

7. **Corrigir indicador Focus:** buscar IGP-DI (não IGP-M) para projeção de inflação

8. **Ler dados ICMS da planilha oficial** (`Variaveis_para_Previsão_YYMMDD.xlsx`) em vez de `dados_sefaz.xlsx`

### P2 — Refinamentos

9. **Dias úteis com feriados:** usar `numpy.busday_count` com calendário de feriados BR/SP ou pacote `holidays`

10. **Diagnósticos completos:** Ljung-Box com lag 24/36, raízes do polinômio AR/MA, erros robustos HAC

### P3 — Nice-to-have

11. **Exportar previsões em Excel** (formato esperado pela equipe SEFAZ)

12. **Log de qual versão dos dados Focus foi usada** (data de consulta)

---

## Anexo: Verificação Numérica das Projeções

### IBC-BR 2026 — Planilha (sazonal) vs dados_sefaz.xlsx (uniforme)

| Mês | Planilha (sazonal) | dados_sefaz (uniforme) | Δ |
|-----|-------------------|----------------------|---|
| Jan | 104.85 | 107.04 | -2.20 |
| Mar | **116.58** | 107.36 | **+9.22** |
| Jul | **116.98** | 108.00 | **+8.98** |
| Out | 108.70 | 108.48 | +0.21 |

A planilha preserva picos sazonais (mar, jul) que o método uniforme achata completamente.

### IGP-DI 2026 — Planilha (Focus mensal ajustado) vs dados_sefaz.xlsx (uniforme)

| Mês | Planilha | dados_sefaz | Δ |
|-----|---------|-------------|---|
| Jan | 1175.85 | 1169.57 | +6.29 |
| Jun | 1194.94 | 1190.08 | +4.86 |
| Dez | 1218.25 | 1215.18 | +3.07 |

Diferença menor que IBC-BR, mas consistente (~0.3–0.5% do nível).

---

## Conclusão

O pipeline Python reimplementa corretamente a **estrutura dos modelos SARIMAX** (ordens 2–5, dummies, variáveis exógenas), mas **não captura o trabalho de preparação de dados** que é a parte mais intensiva e sofisticada do pipeline original. O R/Excel constrói projeções de variáveis exógenas usando distribuição mensal sazonal calibrada com expectativas Focus granulares — o Python substitui isso por crescimento composto uniforme, perdendo informação econômica relevante.

A combinação de cutoff de treino errado + projeções planas torna os resultados do Python **não comparáveis** aos do R na versão atual.
