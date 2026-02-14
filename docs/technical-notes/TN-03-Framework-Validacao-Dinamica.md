# Nota Técnica 03: Framework de Validação Dinâmica (Time Series Cross-Validation)

**Data:** 13/02/2026
**Contexto:** Evolução metodológica para seleção e combinação de modelos.

## 1. O Problema da Validação Estática

A abordagem atual seleciona modelos baseada em uma única janela de treino/teste. Isso é frágil em séries econômicas sujeitas a quebras estruturais (mudanças de regime). Um modelo ótimo em 2015-2019 pode falhar catastroficamente no pós-pandemia.

## 2. Proposta: Janelas Deslizantes (Rolling Windows)

Implementar um motor de backtesting que treina e testa modelos em $N$ janelas temporais sucessivas. 

**Motivação Teórica:**
1.  **Sensibilidade às Condições Iniciais:** O ponto de partida afeta a estimativa dos parâmetros. Testar múltiplos inícios garante robustez.
2.  **Tamanho da Amostra (n):** O aumento progressivo do número de observações testa a estabilidade assintótica dos estimadores.
3.  **Avaliação de Resiliência:** Mede a performance do modelo sob diferentes regimes econômicos (crises vs. expansão).

## 3. Metodologia de Avaliação

Para cada janela $j$, o modelo é treinado em $t_{0} \dots t_{end, j}$ e projeta $h$ passos à frente ($h=1, 3, 6, 12, 24$ meses). As variáveis exógenas observadas (ex-post) são utilizadas para isolar o erro do modelo SARIMAX do erro de projeção das exógenas.

**Matriz de Performance:**
Calcula-se o RMSE e MAE para cada horizonte $h$ acumulado (média dos erros nas janelas).

## 4. Expansão do Espaço de Modelos

Além dos SARIMAX atuais, o framework deve testar:
-   **Variações SARIMAX:** Seleção baseada em correlogramas (ACF/PACF) dinâmicos.
-   **ARIMAX Cointegrado:** Validar relações de longo prazo (Teste de Engle-Granger ou Johansen).
-   **VARMAX:** Modelagem vetorial para capturar feedback loops entre variáveis endógenas/exógenas.

## 5. Estratégia de Combinação (Ensemble)

Em vez de uma média simples fixa, o sistema deve sugerir combinações ótimas para cada horizonte:
-   Ranking de modelos individuais.
-   Combinações de pares e trios.
-   Seleção do "Campeão por Horizonte" (ex: Modelo A para curto prazo, Modelo B+C para longo prazo).

## 6. Referências
-   Hyndman, R.J., & Athanasopoulos, G. (2021). *Forecasting: Principles and Practice* (3rd ed).
-   Tashman, L. J. (2000). Out-of-sample tests of forecasting accuracy: an analysis and review.
