# TN-01: Metodologia de Desagregação Temporal e Sazonalidade Exógena

**Data:** 13/02/2026
**Autor:** Agente SEFAZ-FIX-001 (Subagente)
**Contexto:** Refatoração do Pipeline de Previsão ICMS-SP

## 1. O Problema
O pipeline anterior projetava variáveis exógenas (IBC-BR e IGP-DI) utilizando taxas de crescimento uniforme compostas (`(1+taxa_anual)^(1/12) - 1`). Isso resultava em:
1.  **Perda de Sazonalidade no IBC-BR:** O índice de atividade econômica possui forte padrão sazonal (picos em março/outubro, vales em fevereiro/novembro). A projeção linear ignorava esse componente, prejudicando a capacidade dos modelos SARIMAX de capturar variações intra-anuais do ICMS explicadas pela atividade.
2.  **Ignorância das Expectativas de Curto Prazo no IGP-DI:** A inflação tem dinâmica volátil no curto prazo (choques de oferta, sazonalidade agrícola). Usar uma taxa média anual ignora o "path" de inflação esperado pelo mercado (Focus), que frequentemente difere da média geométrica.

## 2. Solução Adotada

### 2.1. IBC-BR: Sazonalidade Histórica Imposta
Como não temos acesso direto em tempo real às planilhas auxiliares de "Trajetória PIB" com quebras trimestrais do Focus, adotamos uma abordagem robusta de **Imposição de Perfil Sazonal Histórico**.

**Algoritmo:**
1.  **Perfil Sazonal:** Calculamos os Fatores Sazonais ($S_m$) do IBC-BR nos últimos 5 anos completos usando média móvel ou índices simples ($IBC_m / \text{MédiaAnual}$).
2.  **Meta Anual ($Y_{t+1}$):** Projetamos o valor anual do IBC-BR para o ano seguinte aplicando o crescimento do PIB (Focus) sobre o ano corrente.
    $$ \text{Total}_{\text{ano}} = \text{Total}_{\text{ano-1}} \times (1 + \Delta\text{PIB}_{\text{Focus}}) $$
3.  **Mensalização:** Distribuímos o total anual conforme os pesos sazonais:
    $$ \text{IBC}_{m, t+1} = \frac{\text{Total}_{\text{ano}}}{\sum S_m} \times S_m $$
4.  **Ajuste de Nível:** Garantimos que a "emenda" entre o último dado observado e o primeiro projetado não gere degraus artificiais, suavizando se necessário, mas priorizando a integral anual (meta do Focus).

### 2.2. IGP-DI: Expectativas Focus Mensais
Para a inflação, o Banco Central disponibiliza expectativas mensais ("Top 5" ou média de mercado) para os próximos meses.

**Algoritmo:**
1.  **Curto Prazo (Meses 1-12):** Utilizamos as projeções mensais explícitas do Focus para IGP-DI (ou IGP-M como proxy de alta correlação se IGP-DI indisponível na API pública imediata).
2.  **Longo Prazo:** Para meses além do horizonte mensal do Focus, convergimos para a meta anual ajustada pela sazonalidade histórica (similar ao IBC-BR) ou mantemos a média de longo prazo.
3.  **Consistência:** Verificamos se o acumulado das projeções mensais converge para a expectativa anual. Se houver discrepância, aplicamos um fator de correção proporcional ($\text{Fator} = \frac{1+\text{MetaAnual}}{\prod(1+\text{Mensal})}$).

## 3. Impacto Esperado
*   **Melhoria no Fit:** Modelos SARIMAX (especialmente Modelo 2 e 5 que usam exógenas contemporâneas) receberão inputs correlacionados com o ciclo real da economia.
*   **Redução de Viés:** Evita subestimar arrecadação em meses fortes (ex: Natal, datas comemorativas refletidas no comércio/IBC) e superestimar em meses fracos.
