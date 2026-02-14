# TN-02: Agregação de Incerteza via Simulação de Monte Carlo

**Data:** 13/02/2026
**Autor:** Agente SEFAZ-FIX-001 (Subagente)
**Contexto:** Refatoração do Pipeline de Previsão ICMS-SP

## 1. O Problema
O pipeline original em R calculava intervalos de confiança (IC) para os totais anuais somando as variâncias das previsões mensais, assumindo independência ou usando aproximações que subestimam a incerteza acumulada. Além disso, a média de modelos (Ensemble) não tinha um IC formalmente derivado da distribuição conjunta dos modelos.

No contexto de séries temporais com erros autocorrelacionados (AR/MA), a soma das previsões ($\sum \hat{y}_t$) tem variância que depende das covariâncias entre os erros futuros:
$$ Var(\sum y_t) = \sum Var(y_t) + 2\sum\sum Cov(y_t, y_{t-k}) $$
Ignorar os termos de covariância resulta em ICs "estreitos demais" para o ano fiscal.

## 2. Solução Adotada: Simulação de Monte Carlo

Utilizamos a funcionalidade `simulate` do `statsmodels` para gerar múltiplos "caminhos" futuros possíveis para a arrecadação.

### 2.1. Simulação Individual por Modelo
Para cada um dos 5 modelos SARIMAX ajustados:
1.  Geramos $N=1.000$ trajetórias futuras (paths).
2.  Cada trajetória incorpora:
    *   Incerteza dos parâmetros estimados (opcional, fixado neste MVP para focar na inovação).
    *   Choques estocásticos (ruído branco) amostrados da distribuição de erros do modelo ($\sigma^2$).
    *   Estrutura dinâmica (AR/MA) propagando os choques ao longo do tempo.

### 2.2. Construção do Ensemble Probabilístico
Para combinar os modelos preservando a incerteza:
1.  Não fazemos a média apenas das esperanças matemáticas (previsão pontual).
2.  Para cada simulação $k$ (de 1 a 1.000):
    $$ \text{Path}_{\text{Ensemble}, k}(t) = \frac{1}{5} \sum_{m=1}^{5} \text{Path}_{m, k}(t) $$
    *Assunção:* Assumimos que a simulação $k$ do Modelo A e a simulação $k$ do Modelo B correspondem ao "mesmo estado de natureza" (choque sistêmico). Isso é uma simplificação conservadora (perfeita correlação de choques) ou uma mistura de distribuições. Na prática, operamos como uma "Mixture Distribution" equiprovável.

### 2.3. Cálculo de Intervalos de Confiança (Agregados)
Com a matriz de simulações $[1000 \times \text{Horizonte}]$:
1.  **Mensal:** Calculamos os percentis 2.5%, 25%, 50%, 75%, 97.5% da distribuição transversal em cada mês $t$.
2.  **Anual (Agregação Temporal):**
    *   Para cada path $k$, somamos os valores mensais do ano: $\text{Total}_k = \sum_{m \in \text{Ano}} y_{m, k}$.
    *   Isso gera uma distribuição de 1.000 totais anuais.
    *   Os percentis dessa distribuição formam o IC do Total Anual.
    *   **Vantagem:** Captura automaticamente a autocorrelação. Se um choque em janeiro propaga para fevereiro via AR(1), a soma anual refletirá essa persistência, alargando o IC corretamente.

## 3. Interpretação
O resultado é um "Fan Chart" (Gráfico de Ventoinha) que mostra a dispersão de probabilidade da arrecadação, permitindo aos gestores visualizar não apenas o cenário base, mas os riscos de cauda (arrecadação muito baixa ou alta).
