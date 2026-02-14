# Backlog do Projeto Previsão ICMS-SP

Este documento registra o roadmap de evolução técnica e metodológica do pipeline.

## 🚀 Épicos (Prioridade Alta)

### E01: Framework de Validação Dinâmica (Time Series Cross-Validation)
**Objetivo:** Implementar um motor de backtesting robusto que avalie a performance dos modelos em múltiplas janelas temporais históricas, garantindo que a escolha dos modelos não seja viciada por um único período de teste.
- **Status:** Planejado
- **Ref:** `docs/technical-notes/TN-03-Framework-Validacao-Dinamica.md`
- **Tasks:**
  - [ ] Implementar motor de Rolling Window (janelas deslizantes).
  - [ ] Expandir zoo de modelos (VARMAX, Cointegração, variações SARIMAX).
  - [ ] Criar matriz de erros por horizonte de projeção (3, 6, 12, 24 meses).
  - [ ] Implementar ranking dinâmico e combinação ótima de modelos.

### E02: Reimplementação do Pipeline (Correção Crítica)
**Objetivo:** Sanar as falhas de paridade com o modelo original (Excel/R) e erros estatísticos identificados na auditoria.
- **Status:** Em Andamento
- **Ref:** `docs/audit-comparison-r-vs-python.md`
- **Tasks:**
  - [ ] Corrigir distribuição mensal sazonal do Focus (IBC-BR e IGP-DI).
  - [ ] Implementar simulação de Monte Carlo para cálculo correto de IC agregado.
  - [ ] Corrigir bugs de integração e validação Out-of-Sample.

---

## 💡 Melhorias Futuras (Icebox)

- **Dashboard Interativo:** Streamlit para visualização de cenários e sensibilidade.
- **Integração CI/CD:** GitHub Actions para rodar previsões mensalmente.
- **Suavização Denton-Cholette:** Implementar método formal para desagregação temporal do Focus.
