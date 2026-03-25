# Workers by Type (Inheritance)

Auto-generated. [[_index|← Back to catalog]]

## [[_base_archiver]] — Archives run outputs with full provenance metadata for audit and reproducibility

- [[run_archiver]] — Archives all run outputs to a timestamped directory with com

## [[_base_claim_extractor]] — Extracts verifiable claims from documents with structural risk classification.

- [[claim_extractor]] — Builds a comprehensive claim_inventory from any document: te

## [[_base_classifier]] — Classifies and triages findings from multiple sources with confidence scoring.

- [[confidence_tier_assigner]] — Assigns operational confidence tiers (blindado/alta_confianc
- [[finding_classifier]] — Cross-validation classifier assigning semantic status (confi

## [[_base_consolidator]] — Merges outputs from N parallel workers into a single unified result with dedupli

- [[chunk_consolidator]] — Deduplicates and merges outputs from chunked parallel worker
- [[finding_consolidator]] — Merges findings from multiple independent workers into dedup
- [[orchestrator_merge_helper]] — Deterministic clustering and deduplication of findings by cl
- [[report_assembler]] — Reads all JSON output files from a pipeline run and merges t
- [[risk_consolidator]] — Computes weighted risk scores from parallel financial, contr

## [[_base_ingester]] — Reads input files, normalizes formats, and produces structured JSON for downstre

- [[document_chunker]] — Classifies documents by procedural phase and groups pages in
- [[document_splitter]] — Splits large documents into blocks by boundary detection (de
- [[fundos_data]] — Fetches fund AUM, returns, and flows from CVM open data. Cal
- [[hint_sheet_extractor]] — Extracts structured factual signals from legal text via 20+ 
- [[json_ingester]] — Reads JSON and CSV files from a data directory, parses them,
- [[macro_data]] — Fetches Selic, IPCA, cambio, Focus expectations from BCB SGS
- [[pdf_ingester]] — Extracts text from PDFs via PyMuPDF (digital) + Azure Docume
- [[procedure_detector]] — Detects multiple procedural types in legal proceedings (inve
- [[renda_fixa_data]] — Fetches NTN-B, LTN, LFT, NTN-F rates from Tesouro Direto/Tra
- [[renda_variavel_data]] — Fetches Ibovespa, sector indices, P/L, dividend yield via yf
- [[text_ingester]] — Reads plain-text and Markdown files from a data directory an

## [[_base_llm_analyzer]] — Receives structured data, applies a contract-bound LLM prompt, and produces stru

- [[adversarial_scanner]] — Abstract base for adversarial dual-track scanning. Create TW
- [[claim_analyzer]] — Analyzes legal claims, their structural dependencies, proced
- [[contract_analyzer]] — Abstract base for contract analysis workers. Do NOT use dire
- [[decision_value_mapper]] — Extracts judicial decisions, monetary values, corrections, a
- [[evidence_timeline]] — Extracts chronological events, evidence items, and witness r
- [[financial_analyzer]] — Analyzes DRE (income statement), balance sheets, and extract
- [[legal_analyzer]] — Analyzes lawsuits, legal certificates, contingent liabilitie
- [[party_status_mapper]] — Extracts parties, lawyers, procedural roles, phase status, a
- [[scanner_adversarial]] — Adversarial auditor that challenges primary scanner output u
- [[scanner_generalist]] — Two-phase document scanning: first applies a prescribed chec
- [[theme_extractor]] — Extracts the material's own thematic structure before analys

## [[_base_renderer]] — Renders structured JSON data through Jinja2 templates into HTML output.

- [[generic_html_renderer]] — Renders structured JSON data through a Jinja2 template into 
- [[html_renderer]] — Renders consolidated legal analysis into professional HTML u
- [[report_compiler]] — Assembles classified and tiered findings into professional H

## [[_base_reviewer]] — Adversarial review of upstream outputs to detect errors, biases, and unsupported

- [[adversarial_reviewer]] — Structured 17-point checklist review that challenges classif
- [[inferential_consistency_checker]] — Detects reasoning leaps where conclusions exceed premises, u

## [[_base_scout]] — Lightweight LLM triage that classifies and prioritizes input before deep analysi

- [[priority_context_scout]] — Identifies macro vectors and high-priority areas requiring r
- [[temas_extraction]] — Extracts topics and themes from documents with taxonomy alig

## [[_base_verifier]] — Mechanical verification and quality gate that validates outputs against claims a

- [[cross_validate]] — Checks LLM output numbers against source data from determini
- [[factcheck_worker]] — Performs horizontal fact-checking driven by claim inventory,
- [[micro_verifier]] — Focused verification of high-severity findings. For each HIG
- [[regression_tracker]] — Compares current run findings against a prior run. Flags fin
- [[source_link_checker]] — Validates URLs, normative references, and citation links fou

## [[adversarial_scanner]] — Abstract base for adversarial dual-track scanning. Create TWO concrete scanners 

- *(no concrete implementations yet)*

## [[contract_analyzer]] — Abstract base for contract analysis workers. Do NOT use directly — decompose int

- *(no concrete implementations yet)*

