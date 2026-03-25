# Workers by Domain

Auto-generated. [[_index|← Back to catalog]]

## educacional
*Revisão acadêmica, avaliação pedagógica, análise de documentos educacionais*

### educacional.avaliacao
*Review de trabalhos, critérios avaliativos, rubrics, feedback*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[adversarial_reviewer]] | llm | rt-noopenclaw | $0.05 | Structured 17-point checklist review that challenges classif |
| [[priority_context_scout]] | llm | rt-noopenclaw | $0.01 | Identifies macro vectors and high-priority areas requiring r |
| [[report_compiler]] | deterministic | rt-noopenclaw | $0 | Assembles classified and tiered findings into professional H |
| [[scanner_adversarial]] | llm | rt-noopenclaw | $0.08 | Adversarial auditor that challenges primary scanner output u |
| [[scanner_generalist]] | llm | rt-noopenclaw | $0.06 | Two-phase document scanning: first applies a prescribed chec |
| [[temas_extraction]] | llm | rt-noopenclaw | $0.01 | Extracts topics and themes from documents with taxonomy alig |

## financeiro
*Análise financeira, mercado, investimentos, auditoria de empresas*

### financeiro.contabilidade
*DRE, balanço patrimonial, demonstrativos, indicadores contábeis*

*(no workers yet)*

### financeiro.due-diligence
*Análise de empresas, M&A, auditoria financeira, risk assessment*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[financial_analyzer]] | llm | due-diligence-pipeline | $0.05 | Analyzes DRE (income statement), balance sheets, and extract |
| [[risk_consolidator]] | deterministic | due-diligence-pipeline | $0 | Computes weighted risk scores from parallel financial, contr |

### financeiro.investimentos
*Renda fixa, variável, fundos, carteiras, alocação*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[fundos_data]] | deterministic | investimentos-br-2026 | $0 | Fetches fund AUM, returns, and flows from CVM open data. Cal |
| [[renda_fixa_data]] | deterministic | investimentos-br-2026 | $0 | Fetches NTN-B, LTN, LFT, NTN-F rates from Tesouro Direto/Tra |
| [[renda_variavel_data]] | deterministic | investimentos-br-2026 | $0 | Fetches Ibovespa, sector indices, P/L, dividend yield via yf |

### financeiro.macro
*Indicadores macroeconômicos, SELIC, IPCA, câmbio, PIB*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[macro_data]] | deterministic | investimentos-br-2026 | $0 | Fetches Selic, IPCA, cambio, Focus expectations from BCB SGS |

## generico
*Workers transversais, domain-agnostic — ferramentas reutilizáveis em qualquer pipeline*

### generico.classificacao
*Scoring, tiering, categorização, triagem de findings*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[confidence_tier_assigner]] | llm | rt-noopenclaw | $0.02 | Assigns operational confidence tiers (blindado/alta_confianc |
| [[finding_classifier]] | llm | rt-noopenclaw | $0.02 | Cross-validation classifier assigning semantic status (confi |

### generico.extracao
*Extração genérica de claims, entidades, temas, estruturas de qualquer documento*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[claim_extractor]] | llm | rt-noopenclaw | $0.03 | Builds a comprehensive claim_inventory from any document: te |
| [[theme_extractor]] | llm | rt-noopenclaw | $0.02 | Extracts the material's own thematic structure before analys |

### generico.ingestao
*PDF ingestion, OCR, document splitting, text normalization — preparação de qualquer documento para pipeline*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[document_splitter]] | hybrid | analise-autos | $0.02 | Splits large documents into blocks by boundary detection (de |
| [[pdf_ingester]] | deterministic | analise-autos | $0.02 | Extracts text from PDFs via PyMuPDF (digital) + Azure Docume |

### generico.orquestracao
*Merge de outputs, archiving, rendering, consolidação multi-stream com provenance*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[finding_consolidator]] | llm | rt-noopenclaw | $0.05 | Merges findings from multiple independent workers into dedup |
| [[generic_html_renderer]] | deterministic | pipeline-engine | $0 | Renders structured JSON data through a Jinja2 template into  |
| [[html_renderer]] | deterministic | analise-autos | $0 | Renders consolidated legal analysis into professional HTML u |
| [[json_ingester]] | deterministic | pipeline-engine | $0 | Reads JSON and CSV files from a data directory, parses them, |
| [[orchestrator_merge_helper]] | deterministic | rt-noopenclaw | $0 | Deterministic clustering and deduplication of findings by cl |
| [[report_assembler]] | deterministic | pipeline-engine | $0 | Reads all JSON output files from a pipeline run and merges t |
| [[request_interpreter]] | llm | pipeline-engine | $0.02 | Reads user request and pipeline config, produces interpretat |
| [[run_archiver]] | deterministic | rt-noopenclaw | $0 | Archives all run outputs to a timestamped directory with com |
| [[text_ingester]] | deterministic | pipeline-engine | $0 | Reads plain-text and Markdown files from a data directory an |

### generico.qualidade
*Adversarial review, regression tracking, quality assurance — padrões de qualidade reutilizáveis*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[regression_tracker]] | deterministic | rt-noopenclaw | $0 | Compares current run findings against a prior run. Flags fin |

### generico.verificacao
*Factcheck, validação de referências, consistência lógica, cross-validation, micro-verification*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[cross_validate]] | deterministic | investimentos-br-2026 | $0 | Checks LLM output numbers against source data from determini |
| [[factcheck_worker]] | deterministic | rt-noopenclaw | $0 | Performs horizontal fact-checking driven by claim inventory, |
| [[inferential_consistency_checker]] | llm | rt-noopenclaw | $0.04 | Detects reasoning leaps where conclusions exceed premises, u |
| [[micro_verifier]] | llm | rt-noopenclaw | $0.03 | Focused verification of high-severity findings. For each HIG |
| [[source_link_checker]] | deterministic | rt-noopenclaw | $0 | Validates URLs, normative references, and citation links fou |

## juridico
*Análise jurídica, processual, contratual, regulatória*

### juridico.ingestao
*OCR, extração de hints, detecção de procedimentos — preparação de documentos jurídicos para análise*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[hint_sheet_extractor]] | hybrid | analise-autos | $0.01 | Extracts structured factual signals from legal text via 20+  |
| [[procedure_detector]] | deterministic | analise-autos | $0 | Detects multiple procedural types in legal proceedings (inve |

### juridico.processual
*Autos, petições, decisões, claims, prazos, andamentos*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[chunk_consolidator]] | deterministic | analise-autos | $0 | Deduplicates and merges outputs from chunked parallel worker |
| [[claim_analyzer]] | llm | analise-autos | $0.06 | Analyzes legal claims, their structural dependencies, proced |
| [[decision_value_mapper]] | llm | analise-autos | $0.06 | Extracts judicial decisions, monetary values, corrections, a |
| [[document_chunker]] | deterministic | analise-autos | $0 | Classifies documents by procedural phase and groups pages in |
| [[evidence_timeline]] | llm | analise-autos | $0.06 | Extracts chronological events, evidence items, and witness r |
| [[party_status_mapper]] | llm | analise-autos | $0.06 | Extracts parties, lawyers, procedural roles, phase status, a |

### juridico.regulatorio
*Compliance, regulação setorial, normas, pareceres*

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[legal_analyzer]] | llm | due-diligence-pipeline | $0.05 | Analyzes lawsuits, legal certificates, contingent liabilitie |

## uncategorized

### uncategorized.geral

| Worker | Type | Origin | Cost | Description |
|---|---|---|---|---|
| [[analyze]] ↗ | deterministic | ? | $0 | Analyze input topics and produce structured findings. In pro |
| [[compile_brief]] ↗ | deterministic | ? | $0 | Compile research findings and fact-check results into a fina |
| [[compile_report]] ↗ | deterministic | ? | $0 | Compile all upstream analyses into a final structured report |
| [[fact_check]] ↗ | deterministic | ? | $0 | Verify key claims from the research step against known evide |
| [[load_input]] ↗ | deterministic | ? | $0 | Read and validate input data from the data directory |
| [[load_topics]] ↗ | deterministic | ? | $0 | Read and validate research topics from the data directory. P |
| [[research]] ↗ | deterministic | ? | $0 | Research each topic in depth, producing structured findings  |

